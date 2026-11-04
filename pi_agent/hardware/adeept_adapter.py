"""
Adeept RaspTank V4 Hardware Adapter.
Interfaces with Adeept's Robot HAT, DC track motors, servos, and camera.
"""

import os
import sys
import glob
import time
import cv2

# Look for Adeept RaspTank server directory in common locations
ADEEPT_SEARCH_PATHS = [
    os.path.expanduser("~/adeept_rasptank2/server"),
    os.path.expanduser("~/adeept_rasptank/server"),
    os.path.expanduser("~/rasptank/server"),
    "/home/pi/adeept_rasptank2/server",
    "/home/pi/adeept_rasptank/server"
]

for p in ADEEPT_SEARCH_PATHS:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# Try importing Adeept modules
adeept_move = None
adeept_lights = None
adeept_servo = None

try:
    import move as adeept_move
    adeept_move.setup()
    print("[AdeeptAdapter] Successfully imported and initialized Adeept 'move' module!")
except Exception as e:
    print(f"[AdeeptAdapter] Notice: Native Adeept move module not found or failed to load: {e}")

try:
    import robotLight as adeept_lights
    adeept_lights.setup()
except Exception:
    pass

class AdeeptTankAdapter:
    def __init__(self, config=None):
        self.config = config or {}
        self.cap = None
        self._init_camera()
        self.left_speed = 0
        self.right_speed = 0

    def _init_camera(self):
        device_idx = self.config.get("camera", {}).get("device_index", 0)
        w = self.config.get("camera", {}).get("width", 640)
        h = self.config.get("camera", {}).get("height", 480)
        fps = self.config.get("camera", {}).get("fps", 25)

        try:
            self.cap = cv2.VideoCapture(device_idx)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
            self.cap.set(cv2.CAP_PROP_FPS, fps)
            if not self.cap.isOpened():
                print(f"[AdeeptAdapter] Warning: Camera index {device_idx} could not be opened.")
        except Exception as e:
            print(f"[AdeeptAdapter] Camera init error: {e}")

    def get_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame
        return None

    def set_motors(self, left_speed, right_speed):
        """
        left_speed, right_speed: integers from -100 to +100
        Negative is reverse, positive is forward.
        """
        self.left_speed = max(-100, min(100, int(left_speed)))
        self.right_speed = max(-100, min(100, int(right_speed)))

        if adeept_move:
            try:
                # Adeept move module logic
                # Left track
                left_dir = 1 if self.left_speed >= 0 else -1
                left_pwr = abs(self.left_speed)
                # Right track
                right_dir = 1 if self.right_speed >= 0 else -1
                right_pwr = abs(self.right_speed)

                if hasattr(adeept_move, 'motor_left') and hasattr(adeept_move, 'motor_right'):
                    adeept_move.motor_left(1, left_dir, left_pwr)
                    adeept_move.motor_right(1, right_dir, right_pwr)
                elif hasattr(adeept_move, 'motor_run'):
                    # Some versions have motor_run(direction, speed)
                    if left_pwr == 0 and right_pwr == 0:
                        adeept_move.motorStop()
                    elif self.left_speed > 0 and self.right_speed > 0:
                        adeept_move.forward(max(left_pwr, right_pwr))
                    elif self.left_speed < 0 and self.right_speed < 0:
                        adeept_move.backward(max(left_pwr, right_pwr))
                    elif self.left_speed < self.right_speed:
                        adeept_move.left(abs(self.right_speed))
                    else:
                        adeept_move.right(abs(self.left_speed))
            except Exception as e:
                print(f"[AdeeptAdapter] Motor drive error: {e}")

    def stop_motors(self):
        self.left_speed = 0
        self.right_speed = 0
        if adeept_move:
            try:
                if hasattr(adeept_move, 'motorStop'):
                    adeept_move.motorStop()
                elif hasattr(adeept_move, 'move'):
                    adeept_move.move(0, 'no', 'no')
            except Exception as e:
                print(f"[AdeeptAdapter] Motor stop error: {e}")

    def set_lights(self, state: bool):
        if adeept_lights:
            try:
                if state:
                    if hasattr(adeept_lights, 'both_on'):
                        adeept_lights.both_on()
                    elif hasattr(adeept_lights, 'setColor'):
                        adeept_lights.setColor(255, 255, 255)
                else:
                    if hasattr(adeept_lights, 'both_off'):
                        adeept_lights.both_off()
                    elif hasattr(adeept_lights, 'setColor'):
                        adeept_lights.setColor(0, 0, 0)
            except Exception as e:
                print(f"[AdeeptAdapter] Lights error: {e}")

    def set_camera_tilt(self, direction: str):
        # Can trigger Adeept servo movement if installed
        pass

    def get_telemetry(self):
        """Read Pi CPU temperature and hardware stats."""
        temp = None
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp = round(int(f.read().strip()) / 1000.0, 1)
        except Exception:
            pass

        return {
            "cpu_temp": temp,
            "mock": False
        }

    def cleanup(self):
        self.stop_motors()
        if self.cap:
            self.cap.release()

