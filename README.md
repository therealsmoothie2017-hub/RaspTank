# 🛰️ RaspTank Global Tele-Op Cockpit

A cloud-relayed, ultra-low latency tele-operation system enabling **you and 2 friends** anywhere in the world to connect **Xbox or PlayStation controllers** directly in your web browsers and drive an **Adeept RaspTank (Raspberry Pi)** located in the Netherlands, complete with live camera streaming and driver-turn coordination.

---

## ⚡ Key Highlights

- **Zero Port Forwarding Needed**: The Raspberry Pi in the Netherlands establishes an *outbound* secure WebSocket connection to your Render.com cloud server. Works seamlessly through home firewalls and CGNAT.
- **Xbox & PlayStation Native Support**: Uses the HTML5 Gamepad API with analog trigger control, smooth deadzone filtering, haptic rumble feedback, and live cockpit visualizers.
- **Multi-Driver Co-Op System**: Built specifically for 3 friends. All 3 can watch the live camera stream simultaneously. One holds the "Driver" seat while the others can spectate, sound the horn, control lights, or request to **"Take The Wheel"** (`Y` / `△`).
- **Safety Watchdog**: If someone closes their laptop or network packets lag for >350ms, the Raspberry Pi hardware watchdog automatically cuts motor power immediately to prevent runaway crashes.
- **Render.com Free Tier Friendly**: Single lightweight asynchronous event loop (`aiohttp`) that uses minimal memory and boots in under 2 seconds.

---

## 🏗️ Architecture

```
[ Friend 1 (USA) ]  ─── Gamepad API ──┐
[ Friend 2 (UK)  ]  ─── Gamepad API ──┼──> [ Render.com Cloud Relay ] <── Outbound WSS ── [ Raspberry Pi Tank ]
[ Friend 3 (NL)  ]  ─── Gamepad API ──┘     (Frankfurt Server / WSS)                       (The Netherlands)
                                                      │                                            │
                                            Broadcasts Video Frames                        Captures Video &
                                            & Synchronizes Drivers                         Executes Motor PWM
```

---

## 🎮 Controller Layout & Keybindings

| Function | Xbox Controller | PlayStation Pad | Keyboard Fallback |
| :--- | :--- | :--- | :--- |
| **Throttle / Steer** | Left Stick (Arcade) or LT/RT | Left Stick or L2/R2 | `W` `A` `S` `D` / Arrows |
| **Tank Dual-Track Drive** | L-Stick (Left) / R-Stick (Right) | L-Stick (Left) / R-Stick (Right) | — |
| **Take / Pass Wheel** | **`Y`** Button | **`△` (Triangle)** Button | `Y` Key |
| **Emergency Stop** | **`B`** Button | **`○` (Circle)** Button | `Spacebar` |
| **Headlights Toggle** | **`X`** Button | **`□` (Square)** Button | `L` Key |
| **Horn / Honk** | **`A`** Button | **`✕` (Cross)** Button | `H` Key |
| **Camera Tilt** | D-Pad Up / Down | D-Pad Up / Down | UI Buttons |

---

## 🚀 Quick Setup Guide

### Part 1: Deploy the Relay Server to Render.com (5 Minutes)

1. **Push this folder to a GitHub repository**:
   ```bash
   git init
   git add .
   git commit -m "RaspTank tele-op cloud relay"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/rasptank-teleop.git
   git push -u origin main
   ```
2. Log into [Render.com](https://render.com) and click **New +** → **Web Service**.
3. Select your GitHub repository.
4. Set the following options:
   - **Root Directory**: `render_server`
   - **Environment**: `Python 3`
   - **Region**: `Frankfurt (EU Central)` *(closest to Netherlands for lowest ping)*
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python app.py`
5. Under **Environment Variables**, add:
   - `TANK_SECRET`: Choose a strong password (e.g. `tank-super-secret-9988`)
   - `ACCESS_PASSWORD`: Optional room PIN for you and your 2 friends (e.g. `tank123`)
6. Click **Deploy Web Service**. Render will assign you a live HTTPS URL:
   `https://your-tank-relay.onrender.com`

---

### Part 2: Setup on the Raspberry Pi in the Netherlands

Send the `pi_agent` folder to your friend in the Netherlands (or have them clone the repo):

1. **Open a terminal on the Raspberry Pi** and navigate into the `pi_agent` folder:
   ```bash
   cd rasptank-teleop/pi_agent
   ```
2. **Run the 1-step installer script**:
   ```bash
   chmod +x install.sh
   ./install.sh
   ```
3. **Configure your Render server URL**:
   Open `config.json`:
   ```bash
   nano config.json
   ```
   Update the `server_url` and `tank_secret`:
   ```json
   {
     "server_url": "wss://your-tank-relay.onrender.com/ws",
     "tank_secret": "tank-super-secret-9988",
     "camera": {
       "device_index": 0,
       "width": 640,
       "height": 480,
       "fps": 25,
       "jpeg_quality": 65
     },
     "watchdog_timeout_sec": 0.35
   }
   ```
4. **Start the background service**:
   ```bash
   sudo systemctl start tank-agent
   sudo systemctl status tank-agent
   ```
   *The tank will now automatically reconnect upon boot whenever WiFi is available!*

---

### Part 3: Driving the Tank with Friends

1. Share your Render URL (`https://your-tank-relay.onrender.com`) with your 2 friends.
2. Plug an **Xbox** or **PlayStation** controller into your PC via USB or pair via Bluetooth.
3. Open the webpage in Chrome, Edge, or Firefox.
4. Enter your call-sign (e.g. `James`) and press **Enter Cockpit**.
5. Press any button on your controller to activate it. You'll see the sticks and triggers animate on the diagnostic panel.
6. Click **"Take Wheel"** (or press **`Y` / `Triangle`**) to drive!

---

## 🧪 Local Testing / Mock Mode (Without Physical Hardware)

You can test the entire cockpit on your own PC right now:

1. **Start the local server**:
   ```bash
   python render_server/app.py
   ```
2. **Start the mock tank agent** (in a second terminal):
   ```bash
   python pi_agent/tank_agent.py --mock --server ws://localhost:8080/ws
   ```
3. Open [http://localhost:8080](http://localhost:8080) in your browser.
4. You will see an animated simulated cockpit radar, telemetry, and live motor speed readouts responding to your controller!

