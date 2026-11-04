/**
 * Gamepad API Manager for Xbox and PlayStation Controllers
 * Supports standard mapping, deadzones, rumble, and stick visualizer.
 */
class GamepadManager {
  constructor(options = {}) {
    this.deadzone = options.deadzone || 0.12;
    this.maxSpeed = options.maxSpeed || 0.8;
    this.mode = options.mode || 'arcade'; // 'arcade' or 'tank'
    this.connectedIndex = null;
    this.prevButtons = {};
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
    // Rescale linearly outside deadzone
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
      // Check if any controller is available if not yet bound
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

    // Standard Gamepad Axes:
    // Axis 0: Left Stick X (-1.0 Left to +1.0 Right)
    // Axis 1: Left Stick Y (-1.0 Up to +1.0 Down)
    // Axis 2: Right Stick X
    // Axis 3: Right Stick Y
    const rawLx = gp.axes[0] || 0;
    const rawLy = gp.axes[1] || 0;
    const rawRx = gp.axes[2] || 0;
    const rawRy = gp.axes[3] || 0;

    const lx = this.applyDeadzone(rawLx);
    const ly = this.applyDeadzone(rawLy);
    const rx = this.applyDeadzone(rawRx);
    const ry = this.applyDeadzone(rawRy);

    // Triggers: Standard Button 6 (LT/L2) and Button 7 (RT/R2)
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

    // Check button click edges (0: A/Cross, 1: B/Circle, 2: X/Square, 3: Y/Triangle)
    const checkEdge = (btnIndex, actionName) => {
      const isDown = gp.buttons[btnIndex] && gp.buttons[btnIndex].pressed;
      const wasDown = this.prevButtons[btnIndex] || false;
      if (isDown && !wasDown) {
        this.onButtonDown(actionName, btnIndex);
        this.rumble(0.2, 80);
      }
      this.prevButtons[btnIndex] = isDown;
    };

    checkEdge(0, 'A_CROSS');       // Horn / Select
    checkEdge(1, 'B_CIRCLE');      // Brake / E-Stop
    checkEdge(2, 'X_SQUARE');      // Lights toggle
    checkEdge(3, 'Y_TRIANGLE');    // Take Wheel / Pass Wheel
    checkEdge(12, 'DPAD_UP');      // Camera Up
    checkEdge(13, 'DPAD_DOWN');    // Camera Down
    checkEdge(14, 'DPAD_LEFT');    // Camera Left
    checkEdge(15, 'DPAD_RIGHT');   // Camera Right

    // Calculate Motor Speeds (-100 to +100)
    let leftSpeed = 0;
    let rightSpeed = 0;

    if (this.mode === 'arcade') {
      // Throttle from Left Stick Y (negative is forward) or RT/LT
      let throttle = -ly;
      // Alternative: Triggers can drive (RT forward, LT reverse)
      if (rt > 0.05 || lt > 0.05) {
        throttle = (rt - lt);
      }

      // Steering from Left Stick X or Right Stick X
      let steer = (Math.abs(rx) > Math.abs(lx)) ? rx : lx;

      // Differential drive mixing
      let left = throttle + steer;
      let right = throttle - steer;

      // Normalize if exceeding [-1, 1]
      const maxVal = Math.max(Math.abs(left), Math.abs(right), 1.0);
      left = (left / maxVal) * this.maxSpeed;
      right = (right / maxVal) * this.maxSpeed;

      leftSpeed = Math.round(left * 100);
      rightSpeed = Math.round(right * 100);
    } else {
      // Dual-Stick Tank Mode (Left stick drives left track, Right stick drives right track)
      const left = -ly * this.maxSpeed;
      const right = -ry * this.maxSpeed;
      leftSpeed = Math.round(left * 100);
      rightSpeed = Math.round(right * 100);
    }

    // Camera Pan/Tilt from Right Stick (in arcade mode)
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

