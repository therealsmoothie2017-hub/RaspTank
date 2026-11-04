"""
Adeept RaspTank V4 Hardware Adapter.
Directly interfaces with Adeept's native PCA9685 Motor driver and Camera modules.
"""

import os
import sys
import time

# Auto-add Adeept web directory to Python path
for p in ["/home/addy/adeept_rasptank2/web", os.path.expanduser("~/adeept_rasptank2/web")]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# Initialize Adeept Motor Hardware
adeept_move = None
try:
    import move as adeept_move
    adeept_move.setup()
    print("[AdeeptAdapter] SUCCESS: Adeept PCA9685 Motor driver initialized!")
except Exception as e:
    print(f"[AdeeptAdapter] Motor setup notice: {e}")

# Initialize Adeept Native Camera Module
adeept_cam = None
try:
    from camera_opencv import Camera
    adeept_cam = Camera()
    print("[AdeeptAdapter] SUCCESS: Adeept Native Camera (libcamera) initialized!")
except Exception as e:
    print(f"[AdeeptAdapter] Camera setup notice: {e}")


class AdeeptTankAdapter:
    def __init__(self, config=None):
        self.config = config or {}
        self.cam = adeept_cam
        self.left_speed = 0
        self.right_speed = 0

    def get_jpeg_bytes(self, quality=65):
        """Fetches live camera frame directly from Adeept's camera thread."""
        if self.cam:
            try:
                frame_bytes = self.cam.get_frame()
                if frame_bytes:
                    return frame_bytes
            except Exception as e:
                pass
        return None

    def get_frame(self):
        return None

    def set_motors(self, left_speed, right_speed):
        """
        Controls Left (Motor 1) and Right (Motor 2) tracks using Adeept's Motor function.
        left_speed, right_speed: integers from -100 to 100.
        """
        self.left_speed = max(-100, min(100, int(left_speed)))
        self.right_speed = max(-100, min(100, int(right_speed)))

        if not adeept_move:
            return

        try:
            if self.left_speed == 0 and self.right_speed == 0:
                if hasattr(adeept_move, 'motorStop'):
                    adeept_move.motorStop()
                return

            m1_dir = getattr(adeept_move, 'M1_Direction', 1)
            m2_dir = getattr(adeept_move, 'M2_Direction', 1)

            # Left Track: Motor 1
            if self.left_speed > 0:
                adeept_move.Motor(1, m1_dir, abs(self.left_speed))
            elif self.left_speed < 0:
                adeept_move.Motor(1, -m1_dir, abs(self.left_speed))
            else:
                adeept_move.Motor(1, m1_dir, 0)

            # Right Track: Motor 2
            if self.right_speed > 0:
                adeept_move.Motor(2, m2_dir, abs(self.right_speed))
            elif self.right_speed < 0:
                adeept_move.Motor(2, -m2_dir, abs(self.right_speed))
            else:
                adeept_move.Motor(2, m2_dir, 0)

        except Exception as e:
            print(f"[AdeeptAdapter] Motor drive error: {e}")

    def stop_motors(self):
        self.left_speed = 0
        self.right_speed = 0
        if adeept_move:
            try:
                adeept_move.motorStop()
            except Exception:
                pass

    def set_lights(self, state: bool):
        pass

    def set_camera_tilt(self, direction: str):
        pass

    def get_telemetry(self):
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
