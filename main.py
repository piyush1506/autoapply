"""
main.py — Job Application Agent entry point

Usage:
    python main.py                  # Run all enabled platforms
    python main.py --platform linkedin
    python main.py --platform internshala
    python main.py --platform indeed
    python main.py --report         # Show application stats
    python main.py --parse-resume   # Test resume parser only
"""

import argparse
import sys
from datetime import datetime
from playwright.sync_api import sync_playwright

import config
from config import PLATFORMS, SEARCH, PROFILE, HEADLESS
from utils import logger, init_csv, count_applied_today, CSV_FILE
from bot_state import state as bot_state
import internshala
import linkedin
import indeed


def print_banner():
    print("\n" + "=" * 55)
    print("  Job Application Agent")
    print(f"       {datetime.now().strftime('%A, %d %B %Y — %H:%M')}")
    print("=" * 55 + "\n")


def load_resume_into_config():
    """
    Read resume PDF, extract profile data, and patch the live config
    module in-memory. config.py values are used as fallback for anything
    the parser couldn't find.
    """
    resume_path = PROFILE.get("resume_path", "resume.pdf")

    try:
        from resume_parser import parse_resume, print_summary
    except ImportError:
        logger.warning("resume_parser.py not found — skipping auto-detection")
        return

    profile_data, search_data = parse_resume(resume_path)

    if not profile_data and not search_data:
        logger.warning("Resume parsing returned nothing — using config.py as-is")
        return

    print_summary(profile_data, search_data)

    # ── Patch config.PROFILE in-memory ──────────────────────────────────────
    # Only override fields the parser actually found (non-empty)
    for key, value in profile_data.items():
        if value and not key.startswith("_"):
            old = config.PROFILE.get(key, "")
            if old != value:
                logger.info(f"[Config] {key}: '{old}' → '{value}'")
            config.PROFILE[key] = value

    # ── Patch config.SEARCH keywords ────────────────────────────────────────
    if search_data.get("keywords"):
        logger.info(f"[Config] keywords set from resume: {search_data['keywords']}")
        config.SEARCH["keywords"] = search_data["keywords"]

    logger.info("[Config] Resume data merged into config successfully\n")


def print_report():
    """Print a summary from the CSV log."""
    import csv, collections
    init_csv()
    statuses  = collections.Counter()
    platforms = collections.Counter()
    companies = []

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            statuses[row["status"]] += 1
            platforms[row["platform"]] += 1
            if row["status"] == "Applied":
                companies.append(f"  • {row['company']:30s} {row['role'][:30]}")

    print("\n  Application Report")
    print("─" * 40)
    print(f"  Total applications : {sum(statuses.values())}")
    for status, count in statuses.items():
        print(f"  {status:20s} : {count}")
    print("\n  By platform:")
    for plat, count in platforms.items():
        print(f"  {plat:20s} : {count}")
    if companies:
        print(f"\n  Applied to ({statuses['Applied']}):")
        for c in companies[-10:]:
            print(c)
    print()


def run_agent(platform_filter: str = None):
    """Launch Playwright and run enabled platforms."""
    print_banner()

    # ── Step 1: Read resume and auto-configure ───────────────────────────────
    load_resume_into_config()

    # ── Step 2: Check daily limit ────────────────────────────────────────────
    today_count = count_applied_today()
    max_apps    = config.SEARCH["max_per_run"]

    if today_count >= max_apps:
        logger.info(f"Daily limit already reached ({today_count}/{max_apps}). Done for today.")
        return

    logger.info(f"Already applied today: {today_count}. Remaining: {max_apps - today_count}")
    applied_count = [today_count]

    # ── Step 3: Launch browser ───────────────────────────────────────────────
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=HEADLESS,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]
        )

        context = browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )

        # Stealth: hide webdriver flag
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en', 'hi'] });
            Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        """)

        page = context.new_page()
        bot_state.current_page = page

        # Auto-update live preview on page load
        from utils import update_live_screenshot
        page.on("load", lambda p: update_live_screenshot(p))

        try:
            # ── Internshala ──────────────────────────────────
            if (platform_filter in (None, "internshala")
                    and PLATFORMS.get("internshala")
                    and applied_count[0] < max_apps
                    and not bot_state.should_stop()):
                logger.info("\n── Internshala ──────────────────────────────")
                try:
                    internshala.run(page, applied_count)
                except Exception as e:
                    logger.error(f"Internshala module crashed: {e}")

            # ── LinkedIn ─────────────────────────────────────
            if (platform_filter in (None, "linkedin")
                    and PLATFORMS.get("linkedin")
                    and applied_count[0] < max_apps
                    and not bot_state.should_stop()):
                logger.info("\n── LinkedIn ─────────────────────────────────")
                try:
                    linkedin.run(page, applied_count)
                except Exception as e:
                    logger.error(f"LinkedIn module crashed: {e}")

            # ── Indeed ───────────────────────────────────────
            if (platform_filter in (None, "indeed")
                    and PLATFORMS.get("indeed")
                    and applied_count[0] < max_apps
                    and not bot_state.should_stop()):
                logger.info("\n── Indeed ───────────────────────────────────")
                try:
                    indeed.run(page, applied_count)
                except Exception as e:
                    logger.error(f"Indeed module crashed: {e}")

        finally:
            context.close()
            browser.close()

    applied_this_run = applied_count[0] - today_count
    logger.info(f"\n{'='*40}")
    logger.info(f"  Run complete — Applied this run : {applied_this_run}")
    logger.info(f"  Total applied today             : {applied_count[0]}/{max_apps}")
    logger.info(f"  Log saved to                    : {CSV_FILE}")
    logger.info(f"{'='*40}\n")


def main():
    parser = argparse.ArgumentParser(description="Job Application Agent")
    parser.add_argument("--platform", choices=["internshala", "linkedin", "indeed"],
                        help="Run only this platform")
    parser.add_argument("--report", action="store_true",
                        help="Show application statistics and exit")
    parser.add_argument("--parse-resume", action="store_true",
                        help="Test resume parser and show what was detected, then exit")
    args = parser.parse_args()

    if args.report:
        print_report()
        sys.exit(0)

    if args.parse_resume:
        from resume_parser import parse_resume, print_summary
        profile_data, search_data = parse_resume(PROFILE.get("resume_path", "resume.pdf"))
        print_summary(profile_data, search_data)
        sys.exit(0)

    run_agent(platform_filter=args.platform)


if __name__ == "__main__":
    main()
