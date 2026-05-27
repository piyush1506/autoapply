"""
linkedin.py — Auto-apply via LinkedIn Easy Apply
"""

import os
from playwright.sync_api import Page
from config import LINKEDIN, PROFILE, SEARCH, FILTERS
from utils import (logger, log_application, already_applied,
                   human_delay, human_type, safe_click,
                   fill_if_visible, screenshot, contains_excluded)
from bot_state import state as bot_state

BASE_URL = "https://www.linkedin.com"


def login(page: Page) -> bool:
    """Log into LinkedIn. Returns True on success."""
    logger.info("[LinkedIn] Logging in...")
    try:
        page.goto(f"{BASE_URL}/login", timeout=30000)
        human_delay(3, 4)

        # Wait for email field to appear (up to 15s)
        try:
            page.wait_for_selector("#username, input[name='session_key'], input[type='email']", timeout=15000)
        except Exception:
            logger.error("[LinkedIn] Login page did not load properly")
            return False

        # Fill email
        for sel in ["#username", "input[name='session_key']", "input[type='email']"]:
            try:
                if page.locator(sel).is_visible(timeout=2000):
                    page.fill(sel, LINKEDIN["email"])
                    break
            except Exception:
                continue

        human_delay(0.5, 1)

        # Fill password
        for sel in ["#password", "input[name='session_password']", "input[type='password']"]:
            try:
                if page.locator(sel).is_visible(timeout=2000):
                    page.fill(sel, LINKEDIN["password"])
                    break
            except Exception:
                continue

        human_delay(0.5, 1)
        page.click("button[type='submit']")
        human_delay(4, 6)

        if "feed" in page.url or "checkpoint" in page.url:
            if "checkpoint" in page.url:
                logger.warning("[LinkedIn] Security checkpoint — solve it manually in the browser")
                # Wait up to 60s for manual resolution
                for _ in range(30):
                    human_delay(2, 2)
                    if "feed" in page.url:
                        break
            logger.info("[LinkedIn] Login successful ✓")
            return True

        logger.error("[LinkedIn] Login failed — check credentials in config.py")
        return False

    except Exception as e:
        logger.error(f"[LinkedIn] Login error: {e}")
        return False


def search_jobs(page: Page, keyword: str) -> list:
    """Search LinkedIn for jobs and return Easy Apply URLs."""
    logger.info(f"[LinkedIn] Searching: '{keyword}'")
    results = []

    try:
        location = "Remote" if SEARCH.get("remote") else SEARCH["location"]
        # LinkedIn job search URL with Easy Apply filter (f_LF=f_AL)
        url = (f"{BASE_URL}/jobs/search/?keywords={keyword.replace(' ', '%20')}"
               f"&location={location.replace(' ', '%20')}"
               f"&f_LF=f_AL"          # Easy Apply only
               f"&f_E=1"              # Internship experience level
               f"&sortBy=DD")         # Sort by date

        page.goto(url, timeout=30000)
        human_delay(3, 5)

        # Scroll to load listings
        for _ in range(3):
            page.keyboard.press("End")
            human_delay(1.5, 2.5)

        # Collect job card links
        cards = page.locator(".job-card-container__link, .jobs-search-results__list-item a").all()
        for card in cards[:15]:
            try:
                href = card.get_attribute("href")
                if href and "/jobs/view/" in href:
                    # Normalize URL
                    if "?" in href:
                        href = href.split("?")[0]
                    full_url = BASE_URL + href if href.startswith("/") else href
                    if full_url not in results:
                        results.append(full_url)
            except Exception:
                continue

        logger.info(f"[LinkedIn] Found {len(results)} Easy Apply jobs for '{keyword}'")

    except Exception as e:
        logger.error(f"[LinkedIn] Search error: {e}")

    return results


def handle_easy_apply_modal(page: Page, company: str, role: str) -> bool:
    """Navigate through Easy Apply multi-step modal. Returns True if submitted."""
    try:
        max_steps = 8
        for step in range(max_steps):
            human_delay(1.5, 2.5)

            # ── Fill common fields ────────────────────────────

            # Phone number
            fill_if_visible(page, "input[id*='phoneNumber']", PROFILE["phone"].replace("+91 ", ""))
            fill_if_visible(page, "input[aria-label*='Phone']", PROFILE["phone"])
            fill_if_visible(page, "input[id*='phone']", PROFILE["phone"])

            # City / Location
            fill_if_visible(page, "input[id*='city']", PROFILE["location"])

            # Resume upload
            resume_input = page.locator("input[type='file']").first
            try:
                if resume_input.is_visible(timeout=1500):
                    resume_path = os.path.abspath(PROFILE["resume_path"])
                    if os.path.exists(resume_path):
                        resume_input.set_input_files(resume_path)
                        human_delay(1, 2)
                    else:
                        logger.warning(f"[LinkedIn] Resume not found at: {resume_path}")
            except Exception:
                pass

            # Text questions
            text_inputs = page.locator("input[type='text']:visible, input[type='number']:visible").all()
            for inp in text_inputs:
                try:
                    label_text = ""
                    lid = inp.get_attribute("id") or ""
                    if lid:
                        label_el = page.locator(f"label[for='{lid}']").first
                        try:
                            label_text = label_el.inner_text().lower()
                        except Exception:
                            pass

                    if inp.input_value() != "":
                        continue

                    if "year" in label_text or "experience" in label_text:
                        inp.fill("1")
                    elif "gpa" in label_text or "cgpa" in label_text:
                        inp.fill(PROFILE["cgpa"])
                    elif "salary" in label_text or "stipend" in label_text or "ctc" in label_text:
                        inp.fill(PROFILE["expected_stipend"])
                    elif "notice" in label_text:
                        inp.fill("0")
                    elif "linkedin" in label_text:
                        inp.fill(PROFILE["linkedin_url"])
                    elif "github" in label_text:
                        inp.fill(PROFILE["github_url"])
                    elif "portfolio" in label_text or "website" in label_text:
                        inp.fill(PROFILE["portfolio_url"])
                    else:
                        inp.fill("1")   # Safe default for numeric questions

                    human_delay(0.2, 0.5)
                except Exception:
                    continue

            # Textarea questions
            textareas = page.locator("textarea:visible").all()
            for ta in textareas:
                try:
                    if ta.input_value() != "":
                        continue
                    cover = PROFILE["cover_letter"].format(
                        company=company, role=role, platform="LinkedIn"
                    )
                    ta.fill(cover)
                    human_delay(0.3, 0.8)
                except Exception:
                    continue

            # Dropdowns — pick first non-empty option
            selects = page.locator("select:visible").all()
            for sel in selects:
                try:
                    if sel.input_value() in ("", "Select an option", None):
                        options = sel.locator("option").all()
                        for opt in options:
                            val = opt.get_attribute("value") or ""
                            if val and val not in ("", "Select an option"):
                                sel.select_option(val)
                                break
                    human_delay(0.2, 0.5)
                except Exception:
                    continue

            # Radio buttons — select "Yes" or first option
            radios = page.locator("input[type='radio']:visible").all()
            for radio in radios:
                try:
                    label_for = radio.get_attribute("id")
                    label_el  = page.locator(f"label[for='{label_for}']").first
                    label_txt = label_el.inner_text().lower()
                    if "yes" in label_txt:
                        radio.click()
                        human_delay(0.2, 0.4)
                        break
                except Exception:
                    continue

            # ── Navigation buttons ────────────────────────────

            # Check for Submit button first
            submit_btn = page.locator("button:has-text('Submit application'), "
                                       "button:has-text('Submit')").first
            try:
                if submit_btn.is_visible(timeout=1500):
                    submit_btn.click()
                    human_delay(2, 3)
                    logger.info(f"[LinkedIn] ✓ Submitted: {role} @ {company}")
                    return True
            except Exception:
                pass

            # Next / Review
            next_clicked = False
            for selector in ["button:has-text('Next')", "button:has-text('Review')",
                              "button:has-text('Continue')"]:
                btn = page.locator(selector).first
                try:
                    if btn.is_visible(timeout=1500):
                        btn.click()
                        next_clicked = True
                        human_delay(1, 2)
                        break
                except Exception:
                    continue

            if not next_clicked:
                logger.warning(f"[LinkedIn] No navigation button found on step {step+1}")
                break

        logger.warning(f"[LinkedIn] Max steps reached without submit for: {company}")
        return False

    except Exception as e:
        logger.error(f"[LinkedIn] Modal error for {company}: {e}")
        return False


def apply_to_job(page: Page, url: str) -> bool:
    """Visit a LinkedIn job and apply via Easy Apply. Returns True on success."""
    try:
        page.goto(url, timeout=30000)
        human_delay(2, 4)

        # Extract details
        company = "Unknown"
        role    = "Unknown"
        try:
            role    = page.locator("h1.t-24, h1.jobs-unified-top-card__job-title").first.inner_text().strip()
            company = page.locator(".jobs-unified-top-card__company-name a, "
                                    ".topcard__org-name-link").first.inner_text().strip()
        except Exception:
            pass

        logger.info(f"[LinkedIn] Evaluating: {role} @ {company}")

        if already_applied(url):
            logger.info(f"[LinkedIn] Skipping — already applied: {company}")
            return False

        page_text = page.inner_text("body")
        if contains_excluded(page_text, FILTERS["exclude_keywords"]):
            logger.info(f"[LinkedIn] Skipping — excluded keyword: {company}")
            log_application("LinkedIn", company, role, url, "Skipped", "excluded keyword")
            return False

        # Click Easy Apply button
        easy_apply_clicked = False
        for selector in ["button.jobs-apply-button:has-text('Easy Apply')",
                          "button:has-text('Easy Apply')",
                          ".jobs-apply-button"]:
            if safe_click(page, selector, timeout=4000):
                easy_apply_clicked = True
                break

        if not easy_apply_clicked:
            if FILTERS.get("easy_apply_only"):
                logger.info(f"[LinkedIn] No Easy Apply — skipping: {company}")
                log_application("LinkedIn", company, role, url, "Skipped", "no easy apply")
                return False
            else:
                logger.info(f"[LinkedIn] No Easy Apply — skipping: {company}")
                return False

        human_delay(1.5, 2.5)
        success = handle_easy_apply_modal(page, company, role)

        if success:
            log_application("LinkedIn", company, role, url, "Applied")
            return True
        else:
            screenshot(page, f"linkedin_failed_{company[:20]}")
            log_application("LinkedIn", company, role, url, "Failed", "modal issue")
            # Dismiss modal
            safe_click(page, "button[aria-label='Dismiss'], button[data-test-modal-close-btn]")
            return False

    except Exception as e:
        logger.error(f"[LinkedIn] Error applying to {url}: {e}")
        log_application("LinkedIn", "Unknown", "Unknown", url, "Error", str(e))
        return False


def run(page: Page, applied_count: list):
    """Main LinkedIn runner."""
    max_apps = SEARCH["max_per_run"]

    if not login(page):
        return

    seen_urls = set()

    for keyword in SEARCH["keywords"]:
        if applied_count[0] >= max_apps:
            logger.info("[LinkedIn] Daily limit reached.")
            break
        if bot_state.should_stop():
            logger.info("[LinkedIn] Stop requested.")
            break

        urls = search_jobs(page, keyword)

        for url in urls:
            if applied_count[0] >= max_apps:
                break
            if bot_state.should_stop():
                logger.info("[LinkedIn] Stop requested.")
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)

            success = apply_to_job(page, url)
            if success:
                applied_count[0] += 1
                logger.info(f"[LinkedIn] Total applied this run: {applied_count[0]}/{max_apps}")

            human_delay(SEARCH["delay_min"], SEARCH["delay_max"])
