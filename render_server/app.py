#!/usr/bin/env python3
"""
Render Relay Server for Raspberry Pi Tank Tele-Operation.
Coordinates the camera stream and controller inputs between the Tank (Pi in Netherlands)
and 3 remote operators using WebSockets.
"""

import os
import sys
import json
import time
import asyncio
import logging
from aiohttp import web, WSMsgType

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tank_relay")

# Environment / Config
PORT = int(os.environ.get("PORT", 8080))
TANK_SECRET = os.environ.get("TANK_SECRET", "super-secret-tank-key-1234")
ACCESS_PASSWORD = os.environ.get("ACCESS_PASSWORD", "")  # Optional room PIN for the 3 friends

# State
tank_connection = None
clients = {}  # ws -> {"id": str, "name": str, "joined_at": float}
active_driver_id = None
driver_queue = []  # list of client_ids waiting for the wheel
latest_telemetry = {
    "status": "offline",
    "cpu_temp": None,
    "battery": None,
    "distance_cm": None,
    "fps": 0,
    "latency_ms": 0,
    "last_seen": 0
}

routes = web.RouteTableDef()

async def broadcast_to_clients(data, is_binary=False):
    """Broadcast data (binary frame or JSON string) to all connected browser clients."""
    if not clients:
        return
    stale_clients = []
    for client_ws in list(clients.keys()):
        try:
            if client_ws.closed:
                stale_clients.append(client_ws)
                continue
            if is_binary:
                await client_ws.send_bytes(data)
            else:
                await client_ws.send_str(data)
        except Exception as e:
            logger.debug(f"Error sending to client: {e}")
            stale_clients.append(client_ws)

    for dead_ws in stale_clients:
        if dead_ws in clients:
            del clients[dead_ws]

async def sync_state():
    """Send current roster, driver info, and tank status to all clients."""
    global active_driver_id
    user_list = [
        {
            "id": info["id"],
            "name": info["name"],
            "is_driver": (info["id"] == active_driver_id)
        }
        for info in clients.values()
    ]

    msg = json.dumps({
        "type": "state_update",
        "tank_connected": (tank_connection is not None and not tank_connection.closed),
        "active_driver": active_driver_id,
        "users": user_list,
        "queue_count": len(driver_queue),
        "telemetry": latest_telemetry
    })
    await broadcast_to_clients(msg)

@routes.get("/api/health")
async def health_check(request):
    """Health endpoint for Render monitoring."""
    return web.json_response({
        "status": "ok",
        "tank_online": tank_connection is not None and not tank_connection.closed,
        "connected_clients": len(clients),
        "active_driver": active_driver_id
    })

@routes.get("/ws")
async def websocket_handler(request):
    global tank_connection, active_driver_id, latest_telemetry

    ws = web.WebSocketResponse(heartbeat=15.0, max_msg_size=16*1024*1024)
    await ws.prepare(request)

    role = request.query.get("role", "client")
    token = request.query.get("token", "")
    username = request.query.get("name", "Operator")[:16].strip() or "Operator"

    # --- TANK CONNECTION ---
    if role == "tank":
        if token != TANK_SECRET:
            logger.warning(f"Unauthorized tank connection attempt with token: {token}")
            await ws.send_json({"type": "error", "message": "Invalid TANK_SECRET"})
            await ws.close(code=4401, message=b"Unauthorized")
            return ws

        logger.info(">>> Tank in Netherlands CONNECTED! <<<")
        tank_connection = ws
        latest_telemetry["status"] = "online"
        latest_telemetry["last_seen"] = time.time()
        await sync_state()

        try:
            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    # Video frame: fast broadcast to all browser viewers
                    await broadcast_to_clients(msg.data, is_binary=True)
                elif msg.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                        p_type = payload.get("type")
                        if p_type == "telemetry":
                            latest_telemetry.update(payload.get("data", {}))
                            latest_telemetry["status"] = "online"
                            latest_telemetry["last_seen"] = time.time()
                            # Forward telemetry to clients
                            await broadcast_to_clients(json.dumps({
                                "type": "telemetry",
                                "data": latest_telemetry
                            }))
                        elif p_type == "pong":
                            pass
                    except json.JSONDecodeError:
                        pass
                elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                    break
        finally:
            logger.warning("<<< Tank in Netherlands DISCONNECTED >>>")
            if tank_connection is ws:
                tank_connection = None
            latest_telemetry["status"] = "offline"
            await sync_state()

        return ws

    # --- BROWSER OPERATOR CONNECTION ---
    client_id = f"user_{int(time.time()*1000) % 100000}_{len(clients)+1}"
    
    # Check access PIN if configured
    if ACCESS_PASSWORD and token != ACCESS_PASSWORD:
        logger.warning(f"Client {username} rejected due to invalid password PIN")
        await ws.send_json({"type": "error", "message": "Incorrect room password"})
        await ws.close(code=4403, message=b"Forbidden")
        return ws

    # Max 4 Operators in roster
    if len(clients) >= 4:
        logger.warning(f"Client {username} rejected: Roster full ({len(clients)}/4)")
        await ws.send_json({"type": "error", "message": "Cockpit roster is full (Maximum 4 crew members)"})
        await ws.close(code=4429, message=b"Room Full")
        return ws

    clients[ws] = {
        "id": client_id,
        "name": username,
        "joined_at": time.time()
    }
    logger.info(f"Client joined: {username} ({client_id}). Total: {len(clients)}")

    # If no one is currently driving, auto-assign first user or wait for claim
    if active_driver_id is None:
        active_driver_id = client_id

    await ws.send_json({
        "type": "welcome",
        "client_id": client_id,
        "your_name": username,
        "active_driver": active_driver_id,
        "telemetry": latest_telemetry
    })
    await sync_state()

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    payload = json.loads(msg.data)
                    action = payload.get("type")

                    # Driver Turn Handshake: "take_wheel"
                    if action == "take_wheel":
                        active_driver_id = client_id
                        logger.info(f"Driver wheel claimed by {username} ({client_id})")
                        await sync_state()
                        await broadcast_to_clients(json.dumps({
                            "type": "announcement",
                            "text": f"{username} took the wheel!"
                        }))

                    # Driver Turn Handshake: "pass_wheel"
                    elif action == "pass_wheel":
                        if active_driver_id == client_id:
                            # Pass to next available user
                            other_ids = [c["id"] for c in clients.values() if c["id"] != client_id]
                            active_driver_id = other_ids[0] if other_ids else None
                            logger.info(f"{username} passed the wheel. Next: {active_driver_id}")
                            await sync_state()
                            await broadcast_to_clients(json.dumps({
                                "type": "announcement",
                                "text": f"{username} passed the wheel."
                            }))

                    # Tank Control Commands (only active driver allowed to send!)
                    elif action == "control":
                        if active_driver_id == client_id:
                            if tank_connection and not tank_connection.closed:
                                # Relay joystick / button commands to tank
                                await tank_connection.send_str(msg.data)
                        else:
                            # Non-driver tried to steer: ignore or notify
                            pass

                    # Horn / Flashlights / Emergency Stop can be triggered
                    elif action == "action":
                        if active_driver_id == client_id or payload.get("action") == "e_stop":
                            if tank_connection and not tank_connection.closed:
                                await tank_connection.send_str(msg.data)

                    # Latency Ping-Pong
                    elif action == "ping":
                        client_time = payload.get("time", 0)
                        await ws.send_json({"type": "pong", "time": client_time, "server_time": time.time()})

                except json.JSONDecodeError:
                    pass
            elif msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                break
    finally:
        logger.info(f"Client disconnected: {username} ({client_id})")
        if ws in clients:
            del clients[ws]

        # If driver left, assign to another friend
        if active_driver_id == client_id:
            active_driver_id = next(iter(clients.values()))["id"] if clients else None
            logger.info(f"Wheel passed to next friend: {active_driver_id}")

        await sync_state()

    return ws

def create_app():
    app = web.Application()
    app.add_routes(routes)

    # Static UI directory
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(static_dir):
        app.router.add_static("/static/", path=static_dir, name="static")

        async def index(request):
            return web.FileResponse(os.path.join(static_dir, "index.html"))

        app.router.add_get("/", index)

    return app

if __name__ == "__main__":
    app = create_app()
    logger.info(f"Starting Tank Relay Server on port {PORT}...")
    web.run_app(app, host="0.0.0.0", port=PORT)
