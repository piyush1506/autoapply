"""
utils.py — Logging, CSV tracking, and human-like helpers
"""

import csv
import logging
import os
import random
import time
from datetime import datetime
from config import LOG_FILE, CSV_FILE


# ── Logger ────────────────────────────────────────────────────
def setup_logger():
    logger = logging.getLogger("JobAgent")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S"
    )

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


logger = setup_logger()


# ── CSV Tracker ───────────────────────────────────────────────
CSV_HEADERS = ["date", "platform", "company", "role", "url", "status", "notes"]


def init_csv():
    """Create CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()


def log_application(platform: str, company: str, role: str,
                    url: str, status: str, notes: str = ""):
    """Append one application row to the CSV."""
    init_csv()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerow({
            "date":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "platform": platform,
            "company":  company,
            "role":     role,
            "url":      url,
            "status":   status,
            "notes":    notes,
        })


def already_applied(url: str) -> bool:
    """Return True if this URL was applied to before."""
    init_csv()
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["url"] == url and row["status"] == "Applied":
                return True
    return False


def count_applied_today() -> int:
    """Count applications submitted today."""
    init_csv()
    today = datetime.now().strftime("%Y-%m-%d")
    count = 0
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"].startswith(today) and row["status"] == "Applied":
                count += 1
    return count


# ── Human-like Helpers ────────────────────────────────────────
def human_delay(min_s: float = 2.0, max_s: float = 5.0):
    """Sleep a random amount to mimic human speed, capturing screenshots."""
    from bot_state import state as bot_state, StopRequestedException
    if bot_state.should_stop():
        raise StopRequestedException("Stop requested by user")

    t = random.uniform(min_s, max_s)
    step = 0.5  # Capture frame every 0.5s during idle
    elapsed = 0.0
    while elapsed < t:
        if bot_state.should_stop():
            raise StopRequestedException("Stop requested by user")
        
        # Take live screenshot if page is available
        update_live_screenshot()
        
        sleep_time = min(step, t - elapsed)
        time.sleep(sleep_time)
        elapsed += sleep_time


def human_type(page, selector: str, text: str, clear: bool = True):
    """Type text character-by-character with random delays."""
    el = page.locator(selector).first
    if clear:
        el.triple_click()
    for char in text:
        el.type(char, delay=random.randint(40, 130))
    human_delay(0.3, 0.8)
    update_live_screenshot(page)


def update_live_screenshot(page=None):
    """Capture the current page view into memory for the live dashboard stream."""
    from bot_state import state as bot_state
    p = page or bot_state.current_page
    if not p:
        return
    try:
        frame = p.screenshot(type="jpeg", quality=40)
        bot_state.latest_frame = frame
    except Exception:
        pass


def safe_click(page, selector: str, timeout: int = 5000):
    """Click an element safely, return True if successful."""
    try:
        page.locator(selector).first.click(timeout=timeout)
        update_live_screenshot(page)
        human_delay(0.5, 1.5)
        return True
    except BaseException as e:
        if isinstance(e, SystemExit) or type(e).__name__ == "StopRequestedException":
            raise
        return False


def fill_if_visible(page, selector: str, value: str):
    """Fill a field only if it's visible on the page."""
    try:
        el = page.locator(selector).first
        if el.is_visible(timeout=2000):
            el.fill(value)
            update_live_screenshot(page)
            human_delay(0.2, 0.6)
            return True
    except BaseException as e:
        if isinstance(e, SystemExit) or type(e).__name__ == "StopRequestedException":
            raise
        pass
    return False


def screenshot(page, name: str):
    """Save a screenshot for debugging."""
    path = f"screenshots/{name}_{datetime.now().strftime('%H%M%S')}.png"
    os.makedirs("screenshots", exist_ok=True)
    page.screenshot(path=path)
    logger.debug(f"Screenshot saved: {path}")


def contains_excluded(text: str, excluded: list) -> bool:
    """Return True if text contains any excluded keyword."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in excluded)
