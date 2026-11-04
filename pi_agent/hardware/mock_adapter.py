"""
Mock Hardware Adapter for testing without physical Raspberry Pi hardware.
Works on Windows, macOS, or Linux using either OpenCV or Pillow.
"""

import time
import math
import io

try:
    import cv2
    import numpy as np
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class MockHardwareAdapter:
    def __init__(self, config=None):
        self.config = config or {}
        self.left_speed = 0
        self.right_speed = 0
        self.headlight = False
        self.cam_tilt = 0
        self.cap = None
        self._init_camera()

    def _init_camera(self):
        if HAS_CV2:
            device_idx = self.config.get("camera", {}).get("device_index", 0)
            try:
                self.cap = cv2.VideoCapture(device_idx)
                if not self.cap.isOpened():
                    self.cap = None
            except Exception:
                self.cap = None

    def get_jpeg_bytes(self, quality=65):
        """Generates synthetic JPEG bytes directly or captures from webcam."""
        # If webcam is available via CV2
        if HAS_CV2 and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
                success, buf = cv2.imencode('.jpg', frame, encode_param)
                if success:
                    return buf.tobytes()

        # Synthetic tactical cockpit frame using PIL or CV2
        w, h = 640, 480
        if HAS_PIL:
            img = Image.new("RGB", (w, h), color=(15, 20, 28))
            draw = ImageDraw.Draw(img)

            # Grid lines
            for x in range(0, w, 40):
                draw.line([(x, 0), (x, h)], fill=(30, 40, 55), width=1)
            for y in range(0, h, 40):
                draw.line([(0, y), (w, y)], fill=(30, 40, 55), width=1)

            t = time.time()
            cx, cy = w // 2, h // 2
            # Animated radar sweep
            angle = (t * 2) % (2 * math.pi)
            rx = int(cx + 80 * math.cos(angle))
            ry = int(cy + 80 * math.sin(angle))
            draw.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], outline=(0, 200, 255), width=1)
            draw.line([(cx, cy), (rx, ry)], fill=(0, 240, 255), width=2)

            # Reticle Center
            draw.line([(cx - 15, cy), (cx + 15, cy)], fill=(0, 255, 136), width=2)
            draw.line([(cx, cy - 15), (cx, cy + 15)], fill=(0, 255, 136), width=2)

            # Text
            draw.text((20, 20), "SIMULATED TANK CAM (NETHERLANDS)", fill=(0, 240, 255))
            draw.text((20, 50), f"MOTORS: L={self.left_speed:+04d}% | R={self.right_speed:+04d}%", fill=(255, 255, 255))
            draw.text((20, 75), f"HEADLIGHT: {'ON' if self.headlight else 'OFF'} | TILT: {self.cam_tilt}", fill=(255, 170, 0))
            draw.text((20, 440), f"TIMESTAMP: {time.strftime('%H:%M:%S')}", fill=(180, 180, 180))

            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality)
            return buf.getvalue()

        return None

    def get_frame(self):
        """For compatibility with OpenCV pipeline."""
        if HAS_CV2 and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret and frame is not None:
                return frame
        return None

    def set_motors(self, left_speed, right_speed):
        old_l, old_r = self.left_speed, self.right_speed
        self.left_speed = max(-100, min(100, int(left_speed)))
        self.right_speed = max(-100, min(100, int(right_speed)))
        if old_l != self.left_speed or old_r != self.right_speed:
            print(f"[MockHardware] Motors: Left={self.left_speed:+04d}% | Right={self.right_speed:+04d}%")

    def stop_motors(self):
        self.left_speed = 0
        self.right_speed = 0

    def set_lights(self, state: bool):
        self.headlight = state

    def set_camera_tilt(self, direction: str):
        if direction == 'up':
            self.cam_tilt = min(45, self.cam_tilt + 5)
        elif direction == 'down':
            self.cam_tilt = max(-45, self.cam_tilt - 5)
        elif direction == 'center':
            self.cam_tilt = 0

    def get_telemetry(self):
        return {
            "cpu_temp": 42.5,
            "battery": 8.1,
            "distance_cm": 55.0,
            "mock": True
        }

    def cleanup(self):
        if self.cap:
            self.cap.release()

