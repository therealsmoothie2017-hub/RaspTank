/**
 * Main Cockpit Application Controller
 * Coordinates WebSockets, UI, Audio Cues, Keyboard Fallback, and Driver Queue.
 */

// Sound Synthesizer via Web Audio API (Zero external MP3 dependencies)
class SoundFX {
  constructor() {
    this.ctx = null;
  }

  ensureContext() {
    if (!this.ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) this.ctx = new AudioCtx();
    }
    if (this.ctx && this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
  }

  playBeep(freq = 880, duration = 0.08, type = 'sine') {
    try {
      this.ensureContext();
      if (!this.ctx) return;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
      gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.start();
      osc.stop(this.ctx.currentTime + duration);
    } catch (e) {}
  }

  playTakeWheel() {
    this.playBeep(523.25, 0.08); // C5
    setTimeout(() => this.playBeep(659.25, 0.08), 80);  // E5
    setTimeout(() => this.playBeep(783.99, 0.15), 160); // G5
  }

  playHorn() {
    this.playBeep(330, 0.25, 'sawtooth');
  }

  playAlert() {
    this.playBeep(220, 0.2, 'square');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const sfx = new SoundFX();
  const videoRenderer = new VideoStreamRenderer('stream-canvas', 'stream-placeholder', 'stat-fps');

  // State
  let ws = null;
  let clientId = null;
  let myName = '';
  let activeDriverId = null;
  let isDriver = false;
  let headlightOn = false;
  let pingInterval = null;
  let lastDrivePacket = { left: 0, right: 0 };
  let driveSendTimer = null;

  // DOM Elements
  const modal = document.getElementById('login-modal');
  const joinForm = document.getElementById('join-form');
  const usernameInput = document.getElementById('username-input');
  const passwordInput = document.getElementById('password-input');
  const tankStatusPill = document.getElementById('tank-status-pill');
  const driverNameEl = document.getElementById('current-driver-name');
  const btnTakeWheel = document.getElementById('btn-take-wheel');
  const crewList = document.getElementById('crew-list');
  const userCountEl = document.getElementById('user-count');
  const statPing = document.getElementById('stat-ping');
  const statTemp = document.getElementById('stat-temp');
  const btnLight = document.getElementById('btn-light');
  const btnHorn = document.getElementById('btn-horn');
  const btnEStop = document.getElementById('btn-e-stop');
  const sliderSpeed = document.getElementById('slider-speed');
  const speedLabel = document.getElementById('speed-label');
  const sliderDeadzone = document.getElementById('slider-deadzone');
  const deadzoneLabel = document.getElementById('deadzone-label');
  const banner = document.getElementById('announcement-banner');

  function showBanner(text, timeout = 2500) {
    banner.textContent = text;
    banner.classList.add('show');
    setTimeout(() => banner.classList.remove('show'), timeout);
  }

  // --- GAMEPAD MANAGER INITIALIZATION ---
  const gamepad = new GamepadManager({
    deadzone: parseFloat(sliderDeadzone.value) / 100,
    maxSpeed: parseFloat(sliderSpeed.value) / 100,
    mode: 'arcade',
    onButtonDown: (action) => {
      sfx.playBeep(1200, 0.04);
      if (action === 'Y_TRIANGLE') {
        toggleWheel();
      } else if (action === 'B_CIRCLE') {
        emergencyStop();
      } else if (action === 'X_SQUARE') {
        toggleLight();
      } else if (action === 'A_CROSS') {
        triggerHorn();
      } else if (action === 'DPAD_UP') {
        sendCameraTilt('up');
      } else if (action === 'DPAD_DOWN') {
        sendCameraTilt('down');
      }
    },
    onDriveInput: (input) => {
      if (!isDriver) return;
      // Send drive packet at throttled rate (max 30Hz)
      lastDrivePacket = input;
    }
  });

  // Slider Listeners
  sliderSpeed.addEventListener('input', (e) => {
    const val = e.target.value;
    speedLabel.textContent = `${val}%`;
    gamepad.maxSpeed = parseFloat(val) / 100;
  });

  sliderDeadzone.addEventListener('input', (e) => {
    const val = e.target.value;
    deadzoneLabel.textContent = `${val}%`;
    gamepad.deadzone = parseFloat(val) / 100;
  });

  // Drive Mode Toggles
  document.querySelectorAll('input[name="drive-mode"]').forEach((radio) => {
    radio.parentElement.addEventListener('click', () => {
      document.querySelectorAll('.toggle-btn').forEach(btn => btn.classList.remove('active'));
      radio.parentElement.classList.add('active');
      gamepad.mode = radio.value;
    });
  });

  // --- DRIVE PACKET DISPATCH LOOP ---
  // Sends control packets to the tank 25 times per second
  setInterval(() => {
    if (isDriver && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'control',
        left: lastDrivePacket.left || 0,
        right: lastDrivePacket.right || 0,
        camPan: lastDrivePacket.camPan || 0,
        camTilt: lastDrivePacket.camTilt || 0,
        timestamp: Date.now()
      }));
    }
  }, 40);

  // --- ACTIONS ---
  function toggleWheel() {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    if (isDriver) {
      ws.send(JSON.stringify({ type: 'pass_wheel' }));
      sfx.playBeep(400, 0.1);
    } else {
      ws.send(JSON.stringify({ type: 'take_wheel' }));
      sfx.playTakeWheel();
      gamepad.rumble(0.6, 200);
    }
  }

  function emergencyStop() {
    sfx.playAlert();
    gamepad.rumble(1.0, 300);
    lastDrivePacket = { left: 0, right: 0 };
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'action', action: 'e_stop' }));
    }
    showBanner("🚨 EMERGENCY STOP TRIGGERED!");
  }

  function toggleLight() {
    headlightOn = !headlightOn;
    btnLight.classList.toggle('active', headlightOn);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'action', action: 'lights', state: headlightOn }));
    }
  }

  function triggerHorn() {
    sfx.playHorn();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'action', action: 'horn' }));
    }
  }

  function sendCameraTilt(dir) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'action', action: 'cam_tilt', direction: dir }));
    }
  }

  btnTakeWheel.addEventListener('click', toggleWheel);
  btnEStop.addEventListener('click', emergencyStop);
  btnLight.addEventListener('click', toggleLight);
  btnHorn.addEventListener('click', triggerHorn);
  document.getElementById('cam-up').addEventListener('click', () => sendCameraTilt('up'));
  document.getElementById('cam-center').addEventListener('click', () => sendCameraTilt('center'));
  document.getElementById('cam-down').addEventListener('click', () => sendCameraTilt('down'));

  // --- KEYBOARD FALLBACK (WASD / Arrows) ---
  const activeKeys = {};
  window.addEventListener('keydown', (e) => {
    if (modal && !modal.classList.contains('hidden')) return;
    activeKeys[e.code] = true;

    if (e.code === 'Space') {
      e.preventDefault();
      emergencyStop();
    } else if (e.code === 'KeyY') {
      toggleWheel();
    } else if (e.code === 'KeyL') {
      toggleLight();
    } else if (e.code === 'KeyH') {
      triggerHorn();
    }
    updateKeyboardDrive();
  });

  window.addEventListener('keyup', (e) => {
    activeKeys[e.code] = false;
    updateKeyboardDrive();
  });

  function updateKeyboardDrive() {
    if (gamepad.connectedIndex !== null) return; // If gamepad is active, prefer gamepad
    if (!isDriver) return;

    let fwd = 0;
    let turn = 0;
    if (activeKeys['KeyW'] || activeKeys['ArrowUp']) fwd += 1;
    if (activeKeys['KeyS'] || activeKeys['ArrowDown']) fwd -= 1;
    if (activeKeys['KeyA'] || activeKeys['ArrowLeft']) turn -= 1;
    if (activeKeys['KeyD'] || activeKeys['ArrowRight']) turn += 1;

    const speed = gamepad.maxSpeed;
    let left = (fwd + turn) * speed;
    let right = (fwd - turn) * speed;
    const maxVal = Math.max(Math.abs(left), Math.abs(right), 1.0);

    lastDrivePacket = {
      left: Math.round((left / maxVal) * 100),
      right: Math.round((right / maxVal) * 100)
    };
  }

  // --- WEBSOCKET CONNECTION ---
  function connectWebSocket(username, password) {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws?role=client&name=${encodeURIComponent(username)}&token=${encodeURIComponent(password)}`;

    ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      console.log("Connected to Tank Relay Server!");
      modal.classList.add('hidden');
      sfx.playTakeWheel();

      // Start ping loop
      pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping', time: performance.now() }));
        }
      }, 1500);
    };

    ws.onmessage = (event) => {
      // Binary data = Video Frame from Raspberry Pi
      if (event.data instanceof ArrayBuffer) {
        videoRenderer.renderFrame(event.data);
        return;
      }

      // JSON Telemetry & State Updates
      try {
        const msg = json = JSON.parse(event.data);
        handleServerMessage(msg);
      } catch (err) {
        console.error("Message parse error:", err);
      }
    };

    ws.onclose = () => {
      console.warn("Disconnected from server");
      clearInterval(pingInterval);
      tankStatusPill.textContent = "DISCONNECTED";
      tankStatusPill.className = "sub";
      videoRenderer.setOnline(false);
      showBanner("⚠️ Connection to server lost. Reconnecting in 3s...");
      setTimeout(() => connectWebSocket(username, password), 3000);
    };

    ws.onerror = (e) => {
      console.error("WebSocket error:", e);
    };
  }

  function handleServerMessage(msg) {
    if (msg.type === 'welcome') {
      clientId = msg.client_id;
      myName = msg.your_name;
    } else if (msg.type === 'pong') {
      const rtt = Math.round(performance.now() - msg.time);
      statPing.textContent = `${rtt} ms`;
    } else if (msg.type === 'announcement') {
      showBanner(msg.text);
    } else if (msg.type === 'state_update') {
      updateState(msg);
    } else if (msg.type === 'telemetry') {
      if (msg.data.cpu_temp) statTemp.textContent = `${msg.data.cpu_temp}°C`;
    } else if (msg.type === 'error') {
      alert(msg.message);
      modal.classList.remove('hidden');
    }
  }

  function updateState(state) {
    // Tank Online Status
    if (state.tank_connected) {
      tankStatusPill.textContent = "ONLINE (NETHERLANDS)";
      tankStatusPill.className = "sub online";
    } else {
      tankStatusPill.textContent = "TANK OFFLINE";
      tankStatusPill.className = "sub";
    }

    // Active Driver
    activeDriverId = state.active_driver;
    isDriver = (activeDriverId === clientId);

    const activeUser = state.users.find(u => u.id === activeDriverId);
    if (activeUser) {
      driverNameEl.textContent = activeUser.name + (isDriver ? " (YOU)" : "");
      driverNameEl.className = isDriver ? "pilot-name you" : "pilot-name";
    } else {
      driverNameEl.textContent = "None";
      driverNameEl.className = "pilot-name";
    }

    if (isDriver) {
      btnTakeWheel.classList.add('driving');
      btnTakeWheel.innerHTML = '<span class="btn-icon">👑</span><span class="btn-text">PASS WHEEL [Y]</span>';
    } else {
      btnTakeWheel.classList.remove('driving');
      btnTakeWheel.innerHTML = '<span class="btn-icon">🎮</span><span class="btn-text">TAKE WHEEL [Y / △]</span>';
    }

    // Crew Roster
    userCountEl.textContent = state.users.length;
    crewList.innerHTML = '';
    state.users.forEach(u => {
      const li = document.createElement('li');
      li.className = u.is_driver ? 'crew-item driver' : 'crew-item';
      li.innerHTML = `
        <span class="crew-name">${u.name} ${u.id === clientId ? '<strong>(You)</strong>' : ''}</span>
        <span class="crew-role">${u.is_driver ? '👑 DRIVING' : '👀 CO-PILOT'}</span>
      `;
      crewList.appendChild(li);
    });
  }

  // --- LOGIN SUBMIT ---
  joinForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const name = usernameInput.value.trim() || 'Driver';
    const pass = passwordInput.value.trim();
    connectWebSocket(name, pass);
  });
});

