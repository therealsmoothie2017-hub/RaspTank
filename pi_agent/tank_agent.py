#!/usr/bin/env python3
"""
RaspTank Agent - Runs on the Raspberry Pi in the Netherlands.
Connects outbound to the Render.com relay server via secure WebSockets.
Streams live camera video and executes Xbox/PS controller commands with watchdog safety.
"""

import os
import sys
import json
import time
import asyncio
import logging
import argparse

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import websockets
except ImportError:
    print("Error: 'websockets' library is missing. Run: pip install websockets")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tank_agent")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def is_ws_open(ws):
    if ws is None:
        return False
    state = getattr(ws, "state", None)
    if state is not None:
        return getattr(state, "name", "") == "OPEN" or str(state).endswith("OPEN") or state == 1
    return not getattr(ws, "closed", True)

class TankAgent:
    def __init__(self, config, is_mock=False):
        self.config = config
        self.server_url = config.get("server_url", "wss://your-tank-relay.onrender.com/ws")
        self.tank_secret = config.get("tank_secret", "super-secret-tank-key-1234")
        self.watchdog_timeout = float(config.get("watchdog_timeout_sec", 0.35))
        self.jpeg_quality = int(config.get("camera", {}).get("jpeg_quality", 65))
        self.target_fps = int(config.get("camera", {}).get("fps", 25))

        self.last_command_time = 0
        self.is_running = True
        self.ws = None
        self.fps_counter = 0
        self.current_fps = 0
        self.last_fps_calc = time.time()

        # Initialize Hardware
        self.is_mock = is_mock
        if not self.is_mock:
            # Check if running on real Raspberry Pi
            is_rpi = os.path.exists("/proc/device-tree/model") or os.path.exists("/sys/firmware/devicetree/base/model")
            if not is_rpi:
                logger.warning("Not running on physical Raspberry Pi - switching to MOCK adapter.")
                self.is_mock = True

        if self.is_mock:
            from hardware.mock_adapter import MockHardwareAdapter
            self.hw = MockHardwareAdapter(config)
            logger.info("Initialized MOCK Hardware Adapter (Virtual Mode).")
        else:
            from hardware.adeept_adapter import AdeeptTankAdapter
            self.hw = AdeeptTankAdapter(config)
            logger.info("Initialized ADEEPT RASP-TANK Hardware Adapter.")

    async def watchdog_loop(self):
        """Emergency Watchdog: Immediately cuts motor power if internet lags or drops."""
        while self.is_running:
            await asyncio.sleep(0.08)
            now = time.time()
            if self.last_command_time > 0 and (now - self.last_command_time) > self.watchdog_timeout:
                # Watchdog tripped: stop motors
                self.hw.stop_motors()
                self.last_command_time = 0

    async def video_stream_loop(self):
        """Captures frames from camera and transmits binary JPEGs over WebSocket."""
        frame_interval = 1.0 / max(1, self.target_fps)

        while self.is_running:
            loop_start = time.time()

            if is_ws_open(self.ws):
                try:
                    jpeg_bytes = None
                    if hasattr(self.hw, 'get_jpeg_bytes'):
                        jpeg_bytes = self.hw.get_jpeg_bytes(self.jpeg_quality)
                    elif hasattr(self.hw, 'get_frame'):
                        frame = self.hw.get_frame()
                        if frame is not None and cv2:
                            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
                            success, buffer = cv2.imencode('.jpg', frame, encode_param)
                            if success:
                                jpeg_bytes = buffer.tobytes()

                    if jpeg_bytes:
                        await self.ws.send(jpeg_bytes)

                        # Calculate FPS
                        self.fps_counter += 1
                        if time.time() - self.last_fps_calc >= 1.0:
                            self.current_fps = self.fps_counter
                            self.fps_counter = 0
                            self.last_fps_calc = time.time()
                except Exception as e:
                    logger.debug(f"Video frame send error: {e}")

            # Pace to target FPS
            elapsed = time.time() - loop_start
            sleep_time = max(0.005, frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

    async def telemetry_loop(self):
        """Periodically sends battery, CPU temp, and status to Render."""
        while self.is_running:
            await asyncio.sleep(2.0)
            if is_ws_open(self.ws):
                try:
                    telemetry = self.hw.get_telemetry()
                    telemetry["fps"] = self.current_fps
                    await self.ws.send(json.dumps({
                        "type": "telemetry",
                        "data": telemetry
                    }))
                except Exception as e:
                    logger.debug(f"Telemetry send error: {e}")

    async def command_receiver_loop(self):
        """Listens for driving commands from Render and applies them to hardware."""
        while self.is_running:
            if not is_ws_open(self.ws):
                await asyncio.sleep(0.2)
                continue

            try:
                async for message in self.ws:
                    if isinstance(message, str):
                        try:
                            msg = json.loads(message)
                            m_type = msg.get("type")

                            if m_type == "control":
                                # Motor speeds: left (-100..100), right (-100..100)
                                left = msg.get("left", 0)
                                right = msg.get("right", 0)
                                self.hw.set_motors(left, right)
                                self.last_command_time = time.time()

                            elif m_type == "action":
                                action = msg.get("action")
                                if action == "e_stop":
                                    logger.warning("Emergency Stop command received!")
                                    self.hw.stop_motors()
                                    self.last_command_time = 0
                                elif action == "lights":
                                    self.hw.set_lights(msg.get("state", False))
                                elif action == "cam_tilt":
                                    self.hw.set_camera_tilt(msg.get("direction", "center"))
                        except json.JSONDecodeError:
                            pass
            except websockets.ConnectionClosed:
                logger.warning("WebSocket connection dropped.")
                self.hw.stop_motors()
                break
            except Exception as e:
                logger.error(f"Error in command receiver: {e}")
                self.hw.stop_motors()
                break

    async def run(self):
        # Build full URL with role=tank and token
        delim = "&" if "?" in self.server_url else "?"
        ws_endpoint = f"{self.server_url}{delim}role=tank&token={self.tank_secret}"

        # Start watchdog
        asyncio.create_task(self.watchdog_loop())

        while self.is_running:
            logger.info(f"Connecting to Render Relay Server: {self.server_url} ...")
            try:
                # High ping interval and ping timeout for reliable long-haul connections
                async with websockets.connect(
                    ws_endpoint,
                    ping_interval=15,
                    ping_timeout=20,
                    max_size=16*1024*1024
                ) as ws:
                    self.ws = ws
                    logger.info(">>> Successfully CONNECTED to Render Cloud Relay! <<<")

                    # Run workers concurrently
                    tasks = [
                        asyncio.create_task(self.video_stream_loop()),
                        asyncio.create_task(self.telemetry_loop()),
                        asyncio.create_task(self.command_receiver_loop())
                    ]

                    # Wait until connection breaks
                    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    for t in done:
                        if t.exception():
                            logger.error(f"Task exited with error: {t.exception()}", exc_info=t.exception())
                        else:
                            logger.info(f"Task finished normally: {t}")
                    for t in pending:
                        t.cancel()

            except Exception as e:
                logger.warning(f"Connection failed or lost: {e}. Retrying in 4 seconds...")
                self.hw.stop_motors()

            await asyncio.sleep(4.0)

    def stop(self):
        self.is_running = False
        self.hw.stop_motors()
        self.hw.cleanup()

def main():
    parser = argparse.ArgumentParser(description="RaspTank Outbound Cloud Agent")
    parser.add_argument("--config", default=CONFIG_FILE, help="Path to config.json")
    parser.add_argument("--server", help="Override Render server URL (e.g. wss://my-app.onrender.com/ws)")
    parser.add_argument("--secret", help="Override tank secret token")
    parser.add_argument("--mock", action="store_true", help="Force mock hardware mode (for PC testing)")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.server:
        config["server_url"] = args.server
    if args.secret:
        config["tank_secret"] = args.secret

    agent = TankAgent(config, is_mock=args.mock)
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Stopping agent...")
        agent.stop()

if __name__ == "__main__":
    main()
