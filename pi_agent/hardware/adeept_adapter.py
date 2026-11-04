"""
Adeept RaspTank V4 Hardware Adapter.
Interfaces with Adeept's Robot HAT, DC track motors, servos, and camera.
"""

import os
import sys
import glob
import time
import cv2

# Look for Adeept RaspTank directory
ADEEPT_SEARCH_PATHS = [
    "/home/addy/adeept_rasptank2/web",
    "/home/addy/adeept_rasptank2/server",
    "/home/addy/rasptank/web",
    "/home/addy/rasptank/server",
    os.path.expanduser("~/adeept_rasptank2/web"),
    os.path.expanduser("~/adeept_rasptank2/server"),
    os.path.expanduser("~/rasptank/web"),
    os.path.expanduser("~/rasptank/server"),
    "/home/pi/adeept_rasptank2/web",
    "/home/pi/adeept_rasptank2/server"
]

# Dynamically find any folder containing Adeept's move.py in /home or user's home directory
search_roots = ["/home", os.path.expanduser("~")]
try:
    for s_root in search_roots:
        if os.path.isdir(s_root):
            for root, dirs, files in os.walk(s_root):
                if "move.py" in files and "pi_agent" not in root and "hardware" not in root:
                    if root not in ADEEPT_SEARCH_PATHS:
                        ADEEPT_SEARCH_PATHS.insert(0, root)
                        print(f"[AdeeptAdapter] Found Adeept module directory at: {root}")
                        break
except Exception as e:
    print(f"[AdeeptAdapter] Search notice: {e}")

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

        # 1. First attempt: Direct V4L2 with MJPEG (prevents GStreamer memory error)
        if hasattr(cv2, 'CAP_V4L2'):
            try:
                cap = cv2.VideoCapture(device_idx, cv2.CAP_V4L2)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                    cap.set(cv2.CAP_PROP_FPS, fps)
                    ret, test_frame = cap.read()
                    if ret and test_frame is not None:
                        self.cap = cap
                        print(f"[AdeeptAdapter] Camera initialized via V4L2 MJPEG on index {device_idx}!")
                        return
                    cap.release()
            except Exception as e:
                print(f"[AdeeptAdapter] V4L2 probe: {e}")

        # 2. Second attempt: Standard OpenCV capture
        try:
            cap = cv2.VideoCapture(device_idx)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, w)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, h)
                ret, test_frame = cap.read()
                if ret and test_frame is not None:
                    self.cap = cap
                    print(f"[AdeeptAdapter] Camera initialized via standard backend on index {device_idx}!")
                    return
                cap.release()
        except Exception as e:
            print(f"[AdeeptAdapter] Standard backend error: {e}")

        print("[AdeeptAdapter] WARNING: Camera could not be opened. If busy, run: sudo fuser -k /dev/video0")

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
                # 1. Standard Adeept RaspTank2 move.move(speed, 'forward'/'backward'/'no', 'left'/'right'/'no')
                if hasattr(adeept_move, 'move'):
                    if self.left_speed == 0 and self.right_speed == 0:
                        if hasattr(adeept_move, 'motorStop'):
                            adeept_move.motorStop()
                        else:
                            adeept_move.move(0, 'no', 'no')
                    elif self.left_speed > 0 and self.right_speed > 0:
                        speed = max(self.left_speed, self.right_speed)
                        adeept_move.move(speed, 'forward', 'no')
                    elif self.left_speed < 0 and self.right_speed < 0:
                        speed = max(abs(self.left_speed), abs(self.right_speed))
                        adeept_move.move(speed, 'backward', 'no')
                    elif self.left_speed < self.right_speed:
                        speed = max(abs(self.left_speed), abs(self.right_speed))
                        adeept_move.move(speed, 'no', 'left')
                    else:
                        speed = max(abs(self.left_speed), abs(self.right_speed))
                        adeept_move.move(speed, 'no', 'right')

                # 2. Dual-motor driver adeept_move.motor_left / motor_right
                elif hasattr(adeept_move, 'motor_left') and hasattr(adeept_move, 'motor_right'):
                    left_dir = 1 if self.left_speed >= 0 else -1
                    right_dir = 1 if self.right_speed >= 0 else -1
                    adeept_move.motor_left(1, left_dir, abs(self.left_speed))
                    adeept_move.motor_right(1, right_dir, abs(self.right_speed))

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

