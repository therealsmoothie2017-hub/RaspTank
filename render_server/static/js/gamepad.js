/**
 * Gamepad API Manager for Xbox and PlayStation Controllers
 * Supports standard mapping, deadzones, rumble, custom button rebinds, and visualizer.
 */

const DEFAULT_BINDINGS = {
  take_wheel: { index: 3, label: 'Y / △' },
  e_stop: { index: 1, label: 'B / ○' },
  lights: { index: 2, label: 'X / □' },
  horn: { index: 0, label: 'A / ✕' },
  cam_up: { index: 12, label: 'D-Pad Up' },
  cam_down: { index: 13, label: 'D-Pad Down' },
  cam_center: { index: 11, label: 'R-Stick Click' }
};

function getButtonLabel(btnIndex, gpId = '') {
  const isPS = /sony|playstation|dualshock|dualsense/i.test(gpId);
  const labels = {
    0: isPS ? '✕ (Cross)' : 'A Button',
    1: isPS ? '○ (Circle)' : 'B Button',
    2: isPS ? '□ (Square)' : 'X Button',
    3: isPS ? '△ (Triangle)' : 'Y Button',
    4: isPS ? 'L1 Bumper' : 'LB Bumper',
    5: isPS ? 'R1 Bumper' : 'RB Bumper',
    6: isPS ? 'L2 Trigger' : 'LT Trigger',
    7: isPS ? 'R2 Trigger' : 'RT Trigger',
    8: isPS ? 'Share / Select' : 'View / Back',
    9: isPS ? 'Options / Start' : 'Menu / Start',
    10: 'L-Stick Click',
    11: 'R-Stick Click',
    12: 'D-Pad Up',
    13: 'D-Pad Down',
    14: 'D-Pad Left',
    15: 'D-Pad Right',
    16: isPS ? 'PS Home' : 'Xbox Home'
  };
  return labels[btnIndex] || `Button ${btnIndex}`;
}

class GamepadManager {
  constructor(options = {}) {
    this.deadzone = options.deadzone || 0.12;
    this.maxSpeed = options.maxSpeed || 0.8;
    this.mode = options.mode || 'arcade'; // 'arcade' or 'tank'
    this.invertThrottle = localStorage.getItem('rasptank_invert_y') === 'true';
    this.invertSteer = localStorage.getItem('rasptank_invert_x') === 'true';
    this.connectedIndex = null;
    this.prevButtons = {};
    this.listeningAction = null;
    this.onRebindComplete = null;
    this.bindings = this.loadBindings();

    this.onButtonDown = options.onButtonDown || (() => {});
    this.onDriveInput = options.onDriveInput || (() => {});
    this.onStatusChange = options.onStatusChange || (() => {});

    // Visualizer DOM elements
    this.statusEl = document.getElementById('gamepad-status');
    this.leftStickNub = document.getElementById('stick-left-nub');
    this.rightStickNub = document.getElementById('stick-right-nub');
    this.ltFill = document.getElementById('trig-lt-fill');
    this.rtFill = document.getElementById('trig-rt-fill');
    this.vectorIndicator = document.getElementById('vector-indicator');

    this.initListeners();
    this.startPollLoop();
  }

  loadBindings() {
    try {
      const saved = localStorage.getItem('rasptank_bindings');
      if (saved) {
        return Object.assign({}, DEFAULT_BINDINGS, JSON.parse(saved));
      }
    } catch (e) {}
    return Object.assign({}, DEFAULT_BINDINGS);
  }

  saveBindings() {
    try {
      localStorage.setItem('rasptank_bindings', JSON.stringify(this.bindings));
    } catch (e) {}
  }

  resetBindings() {
    this.bindings = Object.assign({}, DEFAULT_BINDINGS);
    this.saveBindings();
    return this.bindings;
  }

  startListening(actionName, callback) {
    this.listeningAction = actionName;
    this.onRebindComplete = callback;
  }

  cancelListening() {
    this.listeningAction = null;
    this.onRebindComplete = null;
  }

  initListeners() {
    window.addEventListener('gamepadconnected', (e) => {
      console.log(`Gamepad connected at index ${e.gamepad.index}: ${e.gamepad.id}`);
      this.connectedIndex = e.gamepad.index;
      this.updateStatusUI(true, e.gamepad.id);
      this.rumble(0.3, 150);
      this.onStatusChange(true, e.gamepad.id);
    });

    window.addEventListener('gamepaddisconnected', (e) => {
      if (this.connectedIndex === e.gamepad.index) {
        console.log(`Gamepad disconnected from index ${e.gamepad.index}`);
        this.connectedIndex = null;
        this.updateStatusUI(false);
        this.onStatusChange(false, null);
      }
    });
  }

  updateStatusUI(connected, id = '') {
    if (!this.statusEl) return;
    if (connected) {
      const isXbox = /xbox|x-box/i.test(id);
      const isPS = /sony|playstation|dualshock|dualsense/i.test(id);
      let label = 'CONTROLLER DETECTED';
      if (isXbox) label = '🎮 XBOX CONTROLLER';
      else if (isPS) label = '🎮 PLAYSTATION PAD';
      this.statusEl.textContent = label;
      this.statusEl.className = 'gamepad-badge connected';
    } else {
      this.statusEl.textContent = 'NO CONTROLLER DETECTED';
      this.statusEl.className = 'gamepad-badge disconnected';
    }
  }

  applyDeadzone(val) {
    if (Math.abs(val) < this.deadzone) return 0;
    const sign = Math.sign(val);
    return sign * ((Math.abs(val) - this.deadzone) / (1 - this.deadzone));
  }

  rumble(magnitude = 0.5, durationMs = 150) {
    if (this.connectedIndex === null) return;
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    const gp = gamepads[this.connectedIndex];
    if (gp && gp.vibrationActuator) {
      gp.vibrationActuator.playEffect('dual-rumble', {
        startDelay: 0,
        duration: durationMs,
        weakMagnitude: magnitude,
        strongMagnitude: magnitude
      }).catch(() => {});
    }
  }

  startPollLoop() {
    const poll = () => {
      this.update();
      requestAnimationFrame(poll);
    };
    requestAnimationFrame(poll);
  }

  update() {
    if (this.connectedIndex === null) {
      const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
      for (let i = 0; i < gamepads.length; i++) {
        if (gamepads[i]) {
          this.connectedIndex = i;
          this.updateStatusUI(true, gamepads[i].id);
          break;
        }
      }
      return;
    }

    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    const gp = gamepads[this.connectedIndex];
    if (!gp) return;

    // --- REBIND CAPTURE MODE ---
    if (this.listeningAction) {
      for (let i = 0; i < gp.buttons.length; i++) {
        const btn = gp.buttons[i];
        if (btn && (btn.pressed || btn.value > 0.5)) {
          const label = getButtonLabel(i, gp.id);
          this.bindings[this.listeningAction] = { index: i, label: label };
          this.saveBindings();
          const action = this.listeningAction;
          const cb = this.onRebindComplete;
          this.listeningAction = null;
          this.onRebindComplete = null;
          this.rumble(0.5, 120);
          if (cb) cb(action, label, i);
          return;
        }
      }
    }

    // Axes: Standard Gamepad Layout
    const rawLx = gp.axes[0] || 0;
    const rawLy = gp.axes[1] || 0;
    const rawRx = gp.axes[2] || 0;
    const rawRy = gp.axes[3] || 0;

    const lx = this.applyDeadzone(rawLx);
    const ly = this.applyDeadzone(rawLy);
    const rx = this.applyDeadzone(rawRx);
    const ry = this.applyDeadzone(rawRy);

    const lt = gp.buttons[6] ? gp.buttons[6].value : 0;
    const rt = gp.buttons[7] ? gp.buttons[7].value : 0;

    // Update Visualizer
    if (this.leftStickNub) {
      this.leftStickNub.style.transform = `translate(${lx * 16}px, ${ly * 16}px)`;
    }
    if (this.rightStickNub) {
      this.rightStickNub.style.transform = `translate(${rx * 16}px, ${ry * 16}px)`;
    }
    if (this.ltFill) this.ltFill.style.height = `${Math.round(lt * 100)}%`;
    if (this.rtFill) this.rtFill.style.height = `${Math.round(rt * 100)}%`;
    if (this.vectorIndicator) {
      this.vectorIndicator.style.transform = `translate(${lx * 50}px, ${ly * 50}px)`;
    }

    // Dynamic Edge Detection for All Bindings
    for (const [actionName, binding] of Object.entries(this.bindings)) {
      const idx = binding.index;
      const isDown = gp.buttons[idx] && (gp.buttons[idx].pressed || gp.buttons[idx].value > 0.5);
      const wasDown = this.prevButtons[idx] || false;
      if (isDown && !wasDown) {
        this.onButtonDown(actionName, idx);
        this.rumble(0.2, 80);
      }
      this.prevButtons[idx] = isDown;
    }

    // Motor Calculations
    let leftSpeed = 0;
    let rightSpeed = 0;

    if (this.mode === 'arcade') {
      let throttle = -ly;
      if (this.invertThrottle) throttle = -throttle;

      if (rt > 0.05 || lt > 0.05) {
        throttle = (rt - lt);
        if (this.invertThrottle) throttle = -throttle;
      }

      let steer = (Math.abs(rx) > Math.abs(lx)) ? rx : lx;
      if (this.invertSteer) steer = -steer;

      let left = throttle + steer;
      let right = throttle - steer;

      const maxVal = Math.max(Math.abs(left), Math.abs(right), 1.0);
      left = (left / maxVal) * this.maxSpeed;
      right = (right / maxVal) * this.maxSpeed;

      leftSpeed = Math.round(left * 100);
      rightSpeed = Math.round(right * 100);
    } else {
      let left = -ly * this.maxSpeed;
      let right = -ry * this.maxSpeed;

      if (this.invertThrottle) {
        left = -left;
        right = -right;
      }
      if (this.invertSteer) {
        const temp = left;
        left = right;
        right = temp;
      }

      leftSpeed = Math.round(left * 100);
      rightSpeed = Math.round(right * 100);
    }

    let camTilt = 0;
    let camPan = 0;
    if (this.mode === 'arcade') {
      camPan = Math.round(rx * 100);
      camTilt = Math.round(-ry * 100);
    }

    this.onDriveInput({
      left: leftSpeed,
      right: rightSpeed,
      camPan: camPan,
      camTilt: camTilt
    });
  }
}

window.GamepadManager = GamepadManager;
