"""
server.py — Web Control Dashboard for AutoApply Bot

Run:  python server.py
Open: http://localhost:8080

Provides a beautiful dark-themed dashboard with:
  • Start / Stop buttons
  • Live log streaming
  • Application statistics
  • Platform selection
"""

import os
import csv
import threading
import logging
from datetime import datetime
from flask import Flask, jsonify, request

from bot_state import state, DashboardLogHandler, StopRequestedException

app = Flask(__name__)

# ── Attach dashboard log handler to the bot's logger ─────────
def _attach_log_handler():
    bot_logger = logging.getLogger("JobAgent")
    # Avoid duplicate handlers on reload
    for h in bot_logger.handlers[:]:
        if isinstance(h, DashboardLogHandler):
            bot_logger.removeHandler(h)
    handler = DashboardLogHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    bot_logger.addHandler(handler)

_attach_log_handler()


# ── Bot runner (runs in background thread) ───────────────────
def _run_bot(platform=None):
    """Import and run the agent in a background thread."""
    try:
        state.running = True
        state.started_at = datetime.now()
        state.last_status = "running"
        state.add_log(f"▶ Bot started — platform: {platform or 'all'}", "INFO")

        from main import run_agent
        run_agent(platform_filter=platform)

        if state.should_stop():
            state.last_status = "stopped"
            state.add_log("⏹ Bot stopped by user", "WARNING")
        else:
            state.last_status = "completed"
            state.add_log("✅ Bot finished successfully", "INFO")

    except StopRequestedException:
        state.last_status = "stopped"
        state.add_log("⏹ Bot stopped by user", "WARNING")
    except Exception as e:
        state.last_status = "error"
        state.add_log(f"❌ Bot error: {e}", "ERROR")
    finally:
        state.running = False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  API ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.route("/api/start", methods=["POST"])
def api_start():
    if state.running:
        return jsonify({"error": "Bot is already running"}), 400

    state.reset()
    state.clear_logs()

    data = request.get_json(silent=True) or {}
    platform = data.get("platform")  # None = all platforms

    thread = threading.Thread(target=_run_bot, args=(platform,), daemon=True)
    thread.start()
    state.thread = thread

    return jsonify({"status": "started", "platform": platform or "all"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    if not state.running:
        return jsonify({"error": "Bot is not running"}), 400

    state.request_stop()
    return jsonify({"status": "stopping"})


@app.route("/api/status")
def api_status():
    # Application stats from CSV
    stats = {"total": 0, "today": 0, "applied": 0, "failed": 0}
    try:
        csv_path = "applications.csv"
        if os.path.exists(csv_path):
            today_str = datetime.now().strftime("%Y-%m-%d")
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats["total"] += 1
                    if row.get("status") == "Applied":
                        stats["applied"] += 1
                    elif row.get("status") in ("Failed", "Error"):
                        stats["failed"] += 1
                    if row.get("date", "").startswith(today_str):
                        stats["today"] += 1
    except Exception:
        pass

    return jsonify({
        "running": state.running,
        "status": state.last_status,
        "started_at": state.started_at.isoformat() if state.started_at else None,
        "stats": stats,
    })


@app.route("/api/logs")
def api_logs():
    since = request.args.get("since", 0, type=int)
    return jsonify({
        "logs": state.get_logs(since),
        "total": len(state.logs),
    })


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DASHBOARD HTML
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoApply — Control Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  /* ── Reset & Base ─────────────────────────────── */
  *, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
  html { font-size: 15px; }
  body {
    font-family: 'Inter', -apple-system, sans-serif;
    background: #06060f;
    color: #e4e4f0;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* ── Animated Background ──────────────────────── */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background:
      radial-gradient(ellipse 80% 60% at 20% 10%, rgba(99,102,241,.12) 0%, transparent 60%),
      radial-gradient(ellipse 60% 50% at 80% 80%, rgba(236,72,153,.08) 0%, transparent 60%),
      radial-gradient(ellipse 50% 40% at 50% 50%, rgba(16,185,129,.06) 0%, transparent 50%);
    z-index: 0;
    pointer-events: none;
  }

  /* ── Layout ───────────────────────────────────── */
  .app { position:relative; z-index:1; max-width:940px; margin:0 auto; padding:32px 20px 60px; }

  /* ── Header ───────────────────────────────────── */
  .header { text-align:center; margin-bottom:36px; }
  .header h1 {
    font-size: 2.4rem; font-weight: 800;
    background: linear-gradient(135deg, #818cf8, #c084fc, #f472b6);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
    letter-spacing: -1px;
  }
  .header p { color:#8888a8; margin-top:6px; font-size:.92rem; }

  /* ── Status Badge ─────────────────────────────── */
  .status-bar {
    display:flex; align-items:center; justify-content:center;
    gap:10px; margin-bottom:32px;
  }
  .status-dot {
    width:12px; height:12px; border-radius:50%;
    background:#4b5563;
    transition: background .3s, box-shadow .3s;
  }
  .status-dot.running { background:#34d399; box-shadow: 0 0 12px #34d39966; animation: pulse 1.5s ease infinite; }
  .status-dot.stopping { background:#fbbf24; box-shadow: 0 0 12px #fbbf2466; animation: pulse 1s ease infinite; }
  .status-dot.error { background:#f87171; box-shadow: 0 0 12px #f8717166; }
  .status-dot.completed { background:#60a5fa; box-shadow: 0 0 12px #60a5fa66; }
  .status-text { font-size: .95rem; font-weight: 500; color: #c4c4dc; text-transform: capitalize; }

  @keyframes pulse {
    0%, 100% { opacity:1; transform:scale(1); }
    50% { opacity:.5; transform:scale(1.3); }
  }

  /* ── Glass Panel ──────────────────────────────── */
  .panel {
    background: rgba(255,255,255,.04);
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 16px;
    backdrop-filter: blur(16px);
    padding: 24px;
    margin-bottom: 20px;
    transition: border-color .3s;
  }
  .panel:hover { border-color: rgba(255,255,255,.14); }
  .panel-title {
    font-size: .78rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: 1.5px;
    color: #7878a0; margin-bottom: 16px;
  }

  /* ── Controls ─────────────────────────────────── */
  .controls { display:flex; gap:12px; align-items:stretch; flex-wrap:wrap; }
  .controls .left { display:flex; gap:12px; flex:1; min-width:200px; }
  .controls .right { display:flex; align-items:center; }

  .btn {
    flex:1; padding: 14px 28px;
    border: none; border-radius: 12px;
    font-family: inherit; font-size: 1rem; font-weight: 600;
    cursor: pointer; transition: all .2s;
    display:flex; align-items:center; justify-content:center; gap:8px;
    min-width:120px;
  }
  .btn:disabled { opacity:.35; cursor:not-allowed; transform:none !important; }
  .btn:not(:disabled):hover { transform: translateY(-2px); }
  .btn:not(:disabled):active { transform: translateY(0); }

  .btn-start {
    background: linear-gradient(135deg, #10b981, #34d399);
    color: #022c22;
    box-shadow: 0 4px 20px rgba(16,185,129,.25);
  }
  .btn-start:not(:disabled):hover { box-shadow: 0 6px 28px rgba(16,185,129,.35); }

  .btn-stop {
    background: linear-gradient(135deg, #ef4444, #f87171);
    color: #fff;
    box-shadow: 0 4px 20px rgba(239,68,68,.25);
  }
  .btn-stop:not(:disabled):hover { box-shadow: 0 6px 28px rgba(239,68,68,.35); }

  /* ── Platform Select ──────────────────────────── */
  .platform-select {
    background: rgba(255,255,255,.06);
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 10px;
    color: #e4e4f0;
    padding: 12px 16px;
    font-family: inherit; font-size: .9rem;
    cursor: pointer; outline:none;
    min-width: 180px;
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%238888a8' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 14px center;
  }
  .platform-select option { background: #1a1a2e; color: #e4e4f0; }

  /* ── Stats Grid ───────────────────────────────── */
  .stats-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(130px, 1fr)); gap:12px; }
  .stat-card {
    background: rgba(255,255,255,.03);
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 14px;
    padding: 18px 16px;
    text-align: center;
    transition: border-color .3s, transform .2s;
  }
  .stat-card:hover { border-color: rgba(255,255,255,.15); transform: translateY(-2px); }
  .stat-value {
    font-size: 2rem; font-weight: 700;
    background: linear-gradient(135deg, #818cf8, #c084fc);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }
  .stat-card:nth-child(2) .stat-value {
    background: linear-gradient(135deg, #34d399, #6ee7b7);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }
  .stat-card:nth-child(3) .stat-value {
    background: linear-gradient(135deg, #60a5fa, #93c5fd);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }
  .stat-card:nth-child(4) .stat-value {
    background: linear-gradient(135deg, #fbbf24, #fcd34d);
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }
  .stat-label { font-size:.75rem; color:#7878a0; margin-top:4px; text-transform:uppercase; letter-spacing:1px; }

  /* ── Log Viewer ───────────────────────────────── */
  .log-viewer {
    background: rgba(0,0,0,.35);
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 12px;
    height: 380px;
    overflow-y: auto;
    padding: 16px;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: .82rem;
    line-height: 1.7;
    scroll-behavior: smooth;
  }
  .log-viewer::-webkit-scrollbar { width: 6px; }
  .log-viewer::-webkit-scrollbar-track { background: transparent; }
  .log-viewer::-webkit-scrollbar-thumb { background: rgba(255,255,255,.12); border-radius:3px; }

  .log-line { padding: 2px 0; word-break:break-all; }
  .log-line .time { color: #5b5b80; margin-right: 8px; }
  .log-line.INFO  .msg { color: #c4c4dc; }
  .log-line.DEBUG .msg { color: #6b6b8a; }
  .log-line.WARNING .msg { color: #fbbf24; }
  .log-line.ERROR .msg { color: #f87171; }

  .log-empty {
    height:100%; display:flex; align-items:center; justify-content:center;
    color:#4b4b6a; font-size:.9rem; font-family:'Inter',sans-serif;
  }

  /* ── Footer ───────────────────────────────────── */
  .footer { text-align:center; margin-top:32px; color:#4b4b6a; font-size:.78rem; }

  /* ── Responsive ───────────────────────────────── */
  @media (max-width:600px) {
    .header h1 { font-size:1.8rem; }
    .controls .left { flex-direction:column; }
    .stats-grid { grid-template-columns: repeat(2,1fr); }
    .log-viewer { height:280px; }
  }
</style>
</head>
<body>
<div class="app">

  <!-- Header -->
  <div class="header">
    <h1>AutoApply</h1>
    <p>Job Application Bot — Control Dashboard</p>
  </div>

  <!-- Status -->
  <div class="status-bar">
    <div class="status-dot" id="statusDot"></div>
    <span class="status-text" id="statusText">Idle</span>
  </div>

  <!-- Controls -->
  <div class="panel">
    <div class="panel-title">Controls</div>
    <div class="controls">
      <div class="left">
        <button class="btn btn-start" id="startBtn" onclick="startBot()">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6,3 20,12 6,21"/></svg>
          Start
        </button>
        <button class="btn btn-stop" id="stopBtn" onclick="stopBot()" disabled>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
          Stop
        </button>
      </div>
      <div class="right">
        <select class="platform-select" id="platformSelect">
          <option value="">All Platforms</option>
          <option value="internshala">Internshala</option>
          <option value="linkedin">LinkedIn</option>
          <option value="indeed">Indeed</option>
        </select>
      </div>
    </div>
  </div>

  <!-- Stats -->
  <div class="panel">
    <div class="panel-title">Statistics</div>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value" id="statTotal">0</div>
        <div class="stat-label">Total</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" id="statApplied">0</div>
        <div class="stat-label">Applied</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" id="statToday">0</div>
        <div class="stat-label">Today</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" id="statFailed">0</div>
        <div class="stat-label">Failed</div>
      </div>
    </div>
  </div>

  <!-- Logs -->
  <div class="panel">
    <div class="panel-title">Live Logs</div>
    <div class="log-viewer" id="logViewer">
      <div class="log-empty" id="logEmpty">Click <strong style="margin:0 4px;">Start</strong> to begin applying…</div>
    </div>
  </div>

  <div class="footer">AutoApply Dashboard &middot; Logs refresh every second</div>
</div>

<script>
  // ── State ─────────────────────────────────────
  let logOffset = 0;
  let isRunning = false;

  // ── DOM refs ──────────────────────────────────
  const $start    = document.getElementById('startBtn');
  const $stop     = document.getElementById('stopBtn');
  const $platform = document.getElementById('platformSelect');
  const $dot      = document.getElementById('statusDot');
  const $text     = document.getElementById('statusText');
  const $logView  = document.getElementById('logViewer');
  const $logEmpty = document.getElementById('logEmpty');

  // ── API helpers ───────────────────────────────
  async function api(path, opts = {}) {
    const res = await fetch(path, opts);
    return res.json();
  }

  // ── Start ─────────────────────────────────────
  async function startBot() {
    const platform = $platform.value || null;
    try {
      $start.disabled = true;
      const body = platform ? { platform } : {};
      await api('/api/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      logOffset = 0;
      $logView.innerHTML = '';
      $logEmpty?.remove();
    } catch (e) {
      $start.disabled = false;
      console.error(e);
    }
  }

  // ── Stop ──────────────────────────────────────
  async function stopBot() {
    try {
      $stop.disabled = true;
      await api('/api/stop', { method: 'POST' });
    } catch (e) {
      console.error(e);
    }
  }

  // ── Poll status ───────────────────────────────
  async function pollStatus() {
    try {
      const data = await api('/api/status');
      isRunning = data.running;

      // Buttons
      $start.disabled = isRunning;
      $stop.disabled  = !isRunning;
      $platform.disabled = isRunning;

      // Status badge
      $dot.className = 'status-dot ' + data.status;
      $text.textContent = data.status;

      // Stats
      document.getElementById('statTotal').textContent   = data.stats.total;
      document.getElementById('statApplied').textContent  = data.stats.applied;
      document.getElementById('statToday').textContent    = data.stats.today;
      document.getElementById('statFailed').textContent   = data.stats.failed;
    } catch (e) { /* ignore */ }
  }

  // ── Poll logs ─────────────────────────────────
  async function pollLogs() {
    try {
      const data = await api(`/api/logs?since=${logOffset}`);
      if (data.logs.length > 0) {
        if ($logEmpty) $logEmpty.remove();

        for (const log of data.logs) {
          const div = document.createElement('div');
          div.className = 'log-line ' + log.level;
          div.innerHTML = `<span class="time">${log.time}</span><span class="msg">${escapeHtml(log.message)}</span>`;
          $logView.appendChild(div);
        }
        logOffset = data.total;

        // Auto-scroll
        $logView.scrollTop = $logView.scrollHeight;
      }
    } catch (e) { /* ignore */ }
  }

  function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }

  // ── Polling loops ─────────────────────────────
  setInterval(pollStatus, 2000);
  setInterval(pollLogs, 1000);
  pollStatus();
</script>
</body>
</html>
"""


@app.route("/")
def dashboard():
    return DASHBOARD_HTML


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ENTRY POINT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"\n  *  AutoApply Dashboard -> http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
