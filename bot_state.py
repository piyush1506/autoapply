"""
bot_state.py — Shared state between the web dashboard and the bot engine.

Provides a thread-safe stop flag and in-memory log buffer so the
Flask dashboard can start / stop the bot and stream its output.
"""

import threading
import logging
from datetime import datetime


class StopRequestedException(BaseException):
    """Raised when the user requests the bot to stop."""
    pass


class BotState:
    """Singleton-ish container for the bot's runtime state."""

    def __init__(self):
        self.running = False
        self.stop_event = threading.Event()
        self.thread = None
        self.logs: list[dict] = []
        self.started_at: datetime | None = None
        self.last_status = "idle"      # idle | running | stopping | completed | error
        self.latest_frame: bytes | None = None
        self.current_page = None
        self._lock = threading.Lock()

    # ── log helpers ──────────────────────────────────────────
    def add_log(self, message: str, level: str = "INFO"):
        with self._lock:
            self.logs.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": level,
                "message": str(message),
            })
            if len(self.logs) > 1000:
                self.logs = self.logs[-800:]

    def get_logs(self, since: int = 0) -> list[dict]:
        with self._lock:
            return list(self.logs[since:])

    def clear_logs(self):
        with self._lock:
            self.logs.clear()

    # ── stop flag ────────────────────────────────────────────
    def should_stop(self) -> bool:
        return self.stop_event.is_set()

    def request_stop(self):
        self.stop_event.set()
        self.last_status = "stopping"
        self.add_log("⏹ Stop requested — finishing current action…", "WARNING")

    def reset(self):
        self.stop_event.clear()
        self.running = False


# ── Module-level singleton ───────────────────────────────────
state = BotState()


# ── Custom log handler that feeds the dashboard ─────────────
class DashboardLogHandler(logging.Handler):
    """Pushes every log record into the shared BotState buffer."""

    def emit(self, record):
        try:
            state.add_log(self.format(record), record.levelname)
        except Exception:
            pass
