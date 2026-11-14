import os
import time
import json
import logging
import asyncio
from datetime import datetime
from aiohttp import web
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("FridayDashboard")

# Web Dashboard HTML Template with Cyberpunk/Stark Industries F.R.I.D.A.Y. HUD
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>F.R.I.D.A.Y. • Central Command & Neural Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #070b14;
            --bg-card: rgba(13, 22, 41, 0.75);
            --border-card: rgba(0, 240, 255, 0.25);
            --cyan-glow: #00f0ff;
            --amber-glow: #ffb703;
            --red-glow: #ff0055;
            --green-glow: #00ff88;
            --text-main: #e2f1ff;
            --text-dim: #7f9eb2;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            background-color: var(--bg-primary);
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(0, 240, 255, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(255, 183, 3, 0.05) 0%, transparent 40%),
                linear-gradient(rgba(7, 11, 20, 0.95), rgba(7, 11, 20, 0.95));
            color: var(--text-main);
            font-family: 'Rajdhani', sans-serif;
            min-height: 100vh;
            padding: 24px;
        }

        .hud-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border-card);
            padding-bottom: 20px;
            margin-bottom: 30px;
        }

        .hud-title-wrap {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .hud-logo {
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: radial-gradient(circle, #00f0ff 0%, #004466 100%);
            box-shadow: 0 0 20px var(--cyan-glow);
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: 'Orbitron', sans-serif;
            font-weight: 900;
            font-size: 20px;
            color: #070b14;
        }

        .hud-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 26px;
            font-weight: 900;
            letter-spacing: 2px;
            color: #fff;
            text-shadow: 0 0 10px rgba(0, 240, 255, 0.6);
        }

        .hud-subtitle {
            font-size: 14px;
            color: var(--cyan-glow);
            letter-spacing: 1px;
            text-transform: uppercase;
        }

        .hud-status-badge {
            display: flex;
            align-items: center;
            gap: 10px;
            background: rgba(0, 255, 136, 0.1);
            border: 1px solid var(--green-glow);
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 700;
            letter-spacing: 1.5px;
            color: var(--green-glow);
            box-shadow: 0 0 15px rgba(0, 255, 136, 0.2);
        }

        .pulse-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--green-glow);
            box-shadow: 0 0 10px var(--green-glow);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); opacity: 0.7; }
            50% { transform: scale(1.2); opacity: 1; }
            100% { transform: scale(0.95); opacity: 0.7; }
        }

        .grid-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(12px);
            position: relative;
            overflow: hidden;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            transition: transform 0.2s, border-color 0.2s;
        }

        .card:hover {
            transform: translateY(-2px);
            border-color: var(--cyan-glow);
        }

        .card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--cyan-glow);
            box-shadow: 0 0 10px var(--cyan-glow);
        }

        .card-label {
            font-size: 13px;
            color: var(--text-dim);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 6px;
        }

        .card-value {
            font-family: 'Orbitron', sans-serif;
            font-size: 28px;
            font-weight: 700;
            color: #ffffff;
            text-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
        }

        .card-subtext {
            font-size: 12px;
            color: var(--cyan-glow);
            margin-top: 6px;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .section-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 18px;
            letter-spacing: 1.5px;
            color: #fff;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .section-title::before {
            content: '//';
            color: var(--cyan-glow);
        }

        .btn {
            background: rgba(0, 240, 255, 0.15);
            border: 1px solid var(--cyan-glow);
            color: #fff;
            padding: 8px 16px;
            border-radius: 6px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 1px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn:hover {
            background: var(--cyan-glow);
            color: #070b14;
            box-shadow: 0 0 15px var(--cyan-glow);
        }

        .btn-danger {
            background: rgba(255, 0, 85, 0.15);
            border-color: var(--red-glow);
            color: #ff99bb;
        }

        .btn-danger:hover {
            background: var(--red-glow);
            color: #fff;
            box-shadow: 0 0 15px var(--red-glow);
        }

        .btn-warn {
            background: rgba(255, 183, 3, 0.15);
            border-color: var(--amber-glow);
            color: #ffe699;
        }

        .btn-warn:hover {
            background: var(--amber-glow);
            color: #070b14;
            box-shadow: 0 0 15px var(--amber-glow);
        }

        .table-wrap {
            overflow-x: auto;
            border-radius: 12px;
            border: 1px solid var(--border-card);
            background: var(--bg-card);
            margin-bottom: 30px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 15px;
            text-align: left;
        }

        th {
            background: rgba(0, 240, 255, 0.08);
            color: var(--cyan-glow);
            padding: 14px 18px;
            font-family: 'Orbitron', sans-serif;
            font-size: 12px;
            letter-spacing: 1px;
            text-transform: uppercase;
            border-bottom: 1px solid var(--border-card);
        }

        td {
            padding: 14px 18px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            color: var(--text-main);
        }

        tr:hover {
            background: rgba(0, 240, 255, 0.04);
        }

        .badge-type {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
        }

        .badge-group { background: rgba(0, 240, 255, 0.15); color: var(--cyan-glow); border: 1px solid rgba(0, 240, 255, 0.3); }
        .badge-channel { background: rgba(255, 183, 3, 0.15); color: var(--amber-glow); border: 1px solid rgba(255, 183, 3, 0.3); }
        .badge-user { background: rgba(0, 255, 136, 0.15); color: var(--green-glow); border: 1px solid rgba(0, 255, 136, 0.3); }

        .broadcast-panel {
            background: var(--bg-card);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 30px;
        }

        .form-row {
            display: flex;
            gap: 16px;
            margin-top: 14px;
        }

        input, textarea, select {
            background: rgba(7, 11, 20, 0.8);
            border: 1px solid var(--border-card);
            border-radius: 6px;
            color: #fff;
            padding: 10px 14px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 15px;
            outline: none;
            transition: border-color 0.2s;
        }

        input:focus, textarea:focus, select:focus {
            border-color: var(--cyan-glow);
            box-shadow: 0 0 10px rgba(0, 240, 255, 0.2);
        }

        textarea {
            flex: 1;
            resize: vertical;
            min-height: 50px;
        }

        #action-status {
            margin-top: 10px;
            font-weight: 700;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="hud-header">
        <div class="hud-title-wrap">
            <div class="hud-logo">⚡</div>
            <div>
                <div class="hud-title">F.R.I.D.A.Y. DASHBOARD</div>
                <div class="hud-subtitle">STARK TACTICAL AI • REAL-TIME BOT COMMAND & TWO-WAY SYNC</div>
            </div>
        </div>
        <div class="hud-status-badge">
            <div class="pulse-dot"></div>
            <span>ONLINE • 24/7 ACTIVE</span>
        </div>
    </div>

    <!-- Live Metrics Grid -->
    <div class="grid-stats">
        <div class="card">
            <div class="card-label">Total Users</div>
            <div class="card-value" id="stat-users">--</div>
            <div class="card-subtext">Direct Subscribers</div>
        </div>
        <div class="card">
            <div class="card-label">Active Groups</div>
            <div class="card-value" id="stat-groups">--</div>
            <div class="card-subtext">Connected Communities</div>
        </div>
        <div class="card">
            <div class="card-label">Broadcast Channels</div>
            <div class="card-value" id="stat-channels">--</div>
            <div class="card-subtext">Managed Feeds</div>
        </div>
        <div class="card">
            <div class="card-label">Server Memory</div>
            <div class="card-value" id="stat-memory">-- MB</div>
            <div class="card-subtext">RAM Footprint</div>
        </div>
        <div class="card">
            <div class="card-label">Bot Uptime</div>
            <div class="card-value" id="stat-uptime">--</div>
            <div class="card-subtext">Continuous Operational</div>
        </div>
    </div>

    <!-- Live Broadcast Console -->
    <div class="broadcast-panel">
        <div class="section-title">GLOBAL BROADCAST TRANSMITTER</div>
        <div class="form-row">
            <select id="broadcast-target">
                <option value="all">Broadcast to All (Groups & Users)</option>
                <option value="groups">Groups Only</option>
                <option value="users">Direct Users Only</option>
                <option value="channels">Channels Only</option>
            </select>
            <textarea id="broadcast-text" placeholder="Type announcement message to dispatch live from F.R.I.D.A.Y..."></textarea>
            <button class="btn" onclick="sendBroadcast()">TRANSMIT</button>
        </div>
        <div id="action-status"></div>
    </div>

    <!-- Interactive Chats & Groups Sync Table -->
    <div class="section-header">
        <div class="section-title">CONNECTED CHATS & COMMUNITIES (LIVE TWO-WAY SYNC)</div>
        <button class="btn" onclick="loadData()">REFRESH DATA</button>
    </div>

    <div class="table-wrap">
        <table>
            <thead>
                <tr>
                    <th>Type</th>
                    <th>Chat Title / User</th>
                    <th>Chat ID</th>
                    <th>Tracked Members</th>
                    <th>Status</th>
                    <th>Remote Actions</th>
                </tr>
            </thead>
            <tbody id="chats-tbody">
                <tr><td colspan="6" style="text-align: center;">Loading neural telemetry...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        async function loadData() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('stat-users').innerText = data.total_users;
                document.getElementById('stat-groups').innerText = data.total_groups;
                document.getElementById('stat-channels').innerText = data.total_channels;
                document.getElementById('stat-memory').innerText = data.memory_mb + ' MB';
                document.getElementById('stat-uptime').innerText = data.uptime;

                const chatsRes = await fetch('/api/chats');
                const chats = await chatsRes.json();
                const tbody = document.getElementById('chats-tbody');
                tbody.innerHTML = '';

                if (chats.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;">No chats registered yet.</td></tr>';
                    return;
                }

                chats.forEach(c => {
                    const tr = document.createElement('tr');
                    let badgeClass = 'badge-user';
                    if (c.type === 'group') badgeClass = 'badge-group';
                    if (c.type === 'channel') badgeClass = 'badge-channel';

                    let actionsHtml = '';
                    if (c.type === 'group') {
                        actionsHtml = `
                            <button class="btn btn-danger" onclick="triggerAction('leave', '${c.id}', '${c.title}')">Leave Group</button>
                            <button class="btn btn-warn" onclick="triggerAction('toggle_pause', '${c.id}', '${c.title}')">${c.is_paused ? 'Resume' : 'Pause'}</button>
                            <button class="btn" onclick="triggerAction('remove', '${c.id}', '${c.title}')">Remove Entry</button>
                        `;
                    } else {
                        actionsHtml = `
                            <button class="btn btn-danger" onclick="triggerAction('remove', '${c.id}', '${c.title}')">Remove User</button>
                        `;
                    }

                    tr.innerHTML = `
                        <td><span class="badge-type ${badgeClass}">${c.type}</span></td>
                        <td><strong>${escapeHtml(c.title)}</strong></td>
                        <td><code>${c.id}</code></td>
                        <td>${c.member_count}</td>
                        <td><span style="color:${c.is_paused ? '#ffb703' : '#00ff88'}">${c.is_paused ? 'PAUSED' : 'ACTIVE'}</span></td>
                        <td style="display:flex; gap:8px;">${actionsHtml}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } catch (err) {
                console.error(err);
            }
        }

        async function triggerAction(action, chatId, title) {
            if (action === 'leave' && !confirm(`Confirm command: Make F.R.I.D.A.Y. immediately leave group '${title}'?`)) {
                return;
            }
            if (action === 'remove' && !confirm(`Remove '${title}' from database?`)) {
                return;
            }

            try {
                const res = await fetch('/api/action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action, chat_id: chatId})
                });
                const result = await res.json();
                const statusDiv = document.getElementById('action-status');
                if (result.success) {
                    statusDiv.style.color = '#00ff88';
                    statusDiv.innerText = `[SUCCESS] ${result.message}`;
                } else {
                    statusDiv.style.color = '#ff0055';
                    statusDiv.innerText = `[ERROR] ${result.error}`;
                }
                setTimeout(loadData, 800);
            } catch (e) {
                alert('Action failed: ' + e);
            }
        }

        async function sendBroadcast() {
            const target = document.getElementById('broadcast-target').value;
            const text = document.getElementById('broadcast-text').value.trim();
            if (!text) {
                alert('Please enter broadcast message text.');
                return;
            }

            if (!confirm(`Transmit broadcast to target: ${target.toUpperCase()}?`)) return;

            try {
                const res = await fetch('/api/action', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({action: 'broadcast', target, text})
                });
                const result = await res.json();
                const statusDiv = document.getElementById('action-status');
                if (result.success) {
                    statusDiv.style.color = '#00ff88';
                    statusDiv.innerText = `[BROADCAST SENT] Dispatched to ${result.dispatched} chats!`;
                    document.getElementById('broadcast-text').value = '';
                } else {
                    statusDiv.style.color = '#ff0055';
                    statusDiv.innerText = `[ERROR] ${result.error}`;
                }
            } catch (e) {
                alert('Broadcast failed: ' + e);
            }
        }

        function escapeHtml(text) {
            return (text || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        loadData();
        setInterval(loadData, 10000); // Live poll every 10s
    </script>
</body>
</html>
"""

START_TIME = time.time()

class FridayWebDashboard:
    """
    Asynchronous web server running concurrently with Telegram bot.
    Enables live web monitoring and two-way control (leave groups, remove users, broadcast).
    """
    def __init__(self, bot_app=None, chats_file_path=None, group_paused_dict=None):
        self.bot_app = bot_app
        self.chats_file = chats_file_path
        self.group_paused = group_paused_dict or {}
        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/", self.handle_index)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/api/stats", self.handle_get_stats)
        self.app.router.add_get("/api/chats", self.handle_get_chats)
        self.app.router.add_post("/api/action", self.handle_post_action)

    def _load_data(self) -> dict:
        if self.chats_file and os.path.exists(self.chats_file):
            try:
                with open(self.chats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"groups": {}, "channels": {}, "users": {}, "group_members": {}}

    def _save_data(self, data: dict):
        if self.chats_file:
            try:
                with open(self.chats_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logger.error(f"Failed to save chats from web dashboard: {e}")

    async def handle_index(self, request):
        return web.Response(text=DASHBOARD_HTML, content_type="text/html")

    async def handle_health(self, request):
        return web.json_response({"status": "healthy", "service": "Friday-AI", "timestamp": time.time()})

    async def handle_get_stats(self, request):
        data = self._load_data()
        uptime_sec = int(time.time() - START_TIME)
        hrs = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        uptime_str = f"{hrs}h {mins}m"

        mem_mb = 45.0
        if psutil:
            try:
                process = psutil.Process()
                mem_mb = round(process.memory_info().rss / (1024 * 1024), 1)
            except Exception:
                pass

        stats = {
            "total_users": len(data.get("users", {})),
            "total_groups": len(data.get("groups", {})),
            "total_channels": len(data.get("channels", {})),
            "uptime": uptime_str,
            "memory_mb": mem_mb,
            "owner_id": data.get("owner_id"),
        }
        return web.json_response(stats)

    async def handle_get_chats(self, request):
        data = self._load_data()
        chats_list = []

        for cid, info in data.get("groups", {}).items():
            members_count = len(data.get("group_members", {}).get(cid, {}))
            chats_list.append({
                "id": cid,
                "title": info.get("title", f"Group {cid}"),
                "type": "group",
                "member_count": members_count or "Active",
                "is_paused": self.group_paused.get(int(cid), False) if str(cid).lstrip("-").isdigit() else False,
            })

        for cid, info in data.get("channels", {}).items():
            chats_list.append({
                "id": cid,
                "title": info.get("title", f"Channel {cid}"),
                "type": "channel",
                "member_count": "--",
                "is_paused": False,
            })

        for cid, info in data.get("users", {}).items():
            name = info.get("name", "User")
            uname = f" (@{info.get('username')})" if info.get("username") else ""
            chats_list.append({
                "id": cid,
                "title": f"{name}{uname}",
                "type": "user",
                "member_count": "--",
                "is_paused": False,
            })

        return web.json_response(chats_list)

    async def handle_post_action(self, request):
        try:
            payload = await request.json()
        except Exception:
            return web.json_response({"success": False, "error": "Invalid JSON"}, status=400)

        action = payload.get("action")
        chat_id_raw = payload.get("chat_id")
        data = self._load_data()

        # 1. Broadcast action
        if action == "broadcast":
            target = payload.get("target", "all")
            text = payload.get("text", "").strip()
            if not text or not self.bot_app:
                return web.json_response({"success": False, "error": "Missing broadcast text or bot client"}, status=400)

            recipients = []
            if target in ["all", "groups"]:
                recipients.extend(data.get("groups", {}).keys())
            if target in ["all", "users"]:
                recipients.extend(data.get("users", {}).keys())
            if target in ["all", "channels"]:
                recipients.extend(data.get("channels", {}).keys())

            success_count = 0
            for cid in recipients:
                try:
                    await self.bot_app.bot.send_message(chat_id=int(cid), text=text)
                    success_count += 1
                    await asyncio.sleep(0.04)  # Rate limiting protection
                except Exception as e:
                    logger.warning(f"Broadcast failed for {cid}: {e}")

            return web.json_response({"success": True, "dispatched": success_count})

        # 2. Leave Group action
        if action == "leave":
            try:
                cid = int(chat_id_raw)
                if self.bot_app:
                    await self.bot_app.bot.leave_chat(chat_id=cid)
                # Remove from database
                data.get("groups", {}).pop(str(cid), None)
                data.get("group_members", {}).pop(str(cid), None)
                self._save_data(data)
                return web.json_response({"success": True, "message": f"Successfully departed group {cid}."})
            except Exception as e:
                return web.json_response({"success": False, "error": str(e)}, status=500)

        # 3. Toggle Pause action
        if action == "toggle_pause":
            try:
                cid = int(chat_id_raw)
                curr = self.group_paused.get(cid, False)
                self.group_paused[cid] = not curr
                state_str = "PAUSED" if self.group_paused[cid] else "RESUMED"
                return web.json_response({"success": True, "message": f"Group {cid} is now {state_str}."})
            except Exception as e:
                return web.json_response({"success": False, "error": str(e)}, status=500)

        # 4. Remove / Delete Chat from DB
        if action == "remove":
            cid_str = str(chat_id_raw)
            data.get("groups", {}).pop(cid_str, None)
            data.get("channels", {}).pop(cid_str, None)
            data.get("users", {}).pop(cid_str, None)
            data.get("group_members", {}).pop(cid_str, None)
            self._save_data(data)
            return web.json_response({"success": True, "message": f"Removed entry {cid_str} from database."})

        return web.json_response({"success": False, "error": "Unknown action"}, status=400)

    async def start(self, host: str = "0.0.0.0", port: int = 8080):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, host, port)
        await site.start()
        logger.info(f"⚡ F.R.I.D.A.Y. Central Web Dashboard running at http://{host}:{port}/")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()
            logger.info("F.R.I.D.A.Y. Web Dashboard stopped.")
