/**
 * High-Performance Low-Latency Canvas Video Stream Receiver
 */
class VideoStreamRenderer {
  constructor(canvasId, placeholderId, fpsElId) {
    this.canvas = document.getElementById(canvasId);
    this.ctx = this.canvas.getContext('2d');
    this.placeholder = document.getElementById(placeholderId);
    this.fpsEl = document.getElementById(fpsElId);

    this.frameCount = 0;
    this.lastFpsUpdate = performance.now();
    this.lastFrameTime = 0;
    this.isRendering = false;

    // Check for stale stream watchdog
    setInterval(() => {
      const now = performance.now();
      if (this.lastFrameTime > 0 && now - this.lastFrameTime > 2500) {
        this.setOnline(false);
      }
    }, 1000);
  }

  setOnline(isOnline) {
    if (this.placeholder) {
      if (isOnline) {
        this.placeholder.classList.remove('active');
      } else {
        this.placeholder.classList.add('active');
        if (this.fpsEl) this.fpsEl.textContent = '--';
      }
    }
  }

  async renderFrame(arrayBuffer) {
    this.lastFrameTime = performance.now();
    this.setOnline(true);

    try {
      const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
      // createImageBitmap is hardware accelerated and non-blocking
      const bitmap = await createImageBitmap(blob);

      // Match canvas dimensions to frame if needed
      if (this.canvas.width !== bitmap.width || this.canvas.height !== bitmap.height) {
        this.canvas.width = bitmap.width;
        this.canvas.height = bitmap.height;
      }

      this.ctx.drawImage(bitmap, 0, 0);
      bitmap.close();

      // FPS Calculation
      this.frameCount++;
      const now = performance.now();
      if (now - this.lastFpsUpdate >= 1000) {
        const fps = Math.round((this.frameCount * 1000) / (now - this.lastFpsUpdate));
        if (this.fpsEl) this.fpsEl.textContent = `${fps}`;
        this.frameCount = 0;
        this.lastFpsUpdate = now;
      }
    } catch (err) {
      console.warn("Frame render error:", err);
    }
  }
}

window.VideoStreamRenderer = VideoStreamRenderer;

