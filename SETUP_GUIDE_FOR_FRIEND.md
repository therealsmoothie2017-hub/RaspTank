# 🤖 RaspTank Tele-Op Agent: Installation Guide for the Netherlands

This guide is for installing the cloud tele-operation agent on your Adeept RaspTank Raspberry Pi so your friends can control it and stream the camera feed via the browser.

---

## 📋 Requirements Before You Start
- The Raspberry Pi is connected to your local Wi-Fi.
- You have SSH access enabled.
- Your friend's Render Cloud URL (e.g., `wss://your-app.onrender.com/ws`).
- Your shared secret key (`TANK_SECRET`).

---

## Step 1: SSH into your Raspberry Pi

Open a Terminal (macOS/Linux) or PowerShell / Command Prompt (Windows) on your computer and connect to the Pi:

```bash
ssh pi@raspberrypi.local
```
*(Replace `pi` with your username and `raspberrypi.local` with your Pi's local IP address if needed, e.g. `ssh pi@192.168.1.50`).*

---

## Step 2: Download / Clone the Agent

Clone the repository to your Pi's home directory:

```bash
cd ~
git clone https://github.com/therealsmoothie2017-hub/RaspTank.git
cd RaspTank/pi_agent
```

*(Note: If the repository is private, you can instead download the zip or copy the `pi_agent` folder directly from your friend).*

---

## Step 3: Run the Auto-Installer

Make the install script executable and run it:

```bash
chmod +x install.sh
./install.sh
```

**What this does automatically:**
- Installs necessary libraries (`python3-opencv`, `python3-numpy`, `websockets`).
- Configures a background system service (`tank-agent.service`) so the tank starts up automatically on boot without needing SSH in the future.

---

## Step 4: Configure your Connection

Open `config.json` with a text editor:

```bash
nano config.json
```

Edit the file to match the Render app URL and secret key provided by your friend:

```json
{
  "server_url": "wss://YOUR_RENDER_APP_NAME.onrender.com/ws",
  "tank_secret": "YOUR_TANK_SECRET_HERE",
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

> **Important**:
> - Make sure the URL starts with **`wss://`** (secure WebSocket) and ends with **`/ws`**.
> - Press `CTRL + O`, then `Enter` to save, and `CTRL + X` to exit `nano`.

---

## Step 5: Test the Tank Interactively

Before running it as a background service, test it manually in your terminal:

```bash
python3 tank_agent.py
```

You should see output similar to:
```text
[INFO] Initialized ADEEPT RASP-TANK Hardware Adapter.
[INFO] Connecting to Render Relay Server: wss://YOUR_APP.onrender.com/ws ...
[INFO] >>> Successfully CONNECTED to Render Cloud Relay! <<<
```

- Have your friend open the web cockpit in their browser.
- Verify that the camera feed appears and controller movements spin the tracks.
- Press `CTRL + C` in the terminal to stop the manual test.

---

## Step 6: Enable & Start the Background Service

Now start the background service so the tank connects automatically whenever it is turned on:

```bash
sudo systemctl start tank-agent
```

Check that it's running properly:

```bash
sudo systemctl status tank-agent
```

*(Press `Q` to exit the status view).*

---

## 🛠 Useful Management Commands

- **View Live Logs**:
  ```bash
  sudo journalctl -u tank-agent -f
  ```
- **Restart the Agent**:
  ```bash
  sudo systemctl restart tank-agent
  ```
- **Stop the Agent**:
  ```bash
  sudo systemctl stop tank-agent
  ```

