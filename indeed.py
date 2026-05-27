"""
indeed.py — Auto-apply to jobs on Indeed (India)
"""

from playwright.sync_api import Page
from config import INDEED, PROFILE, SEARCH, FILTERS
from utils import (logger, log_application, already_applied,
                   human_delay, safe_click, fill_if_visible,
                   screenshot, contains_excluded)
from bot_state import state as bot_state

BASE_URL = "https://in.indeed.com"


def login(page: Page) -> bool:
    """Log into Indeed. Returns True on success."""
    logger.info("[Indeed] Logging in...")
    try:
        page.goto(f"{BASE_URL}", timeout=30000)
        human_delay(2, 3)

        # Click Sign In
        safe_click(page, "a[data-gnav-element-name='SignIn'], a:has-text('Sign in')")
        human_delay(2, 3)

        # Step 1: Enter email
        try:
            page.wait_for_selector("input[name='__email'], input[type='email']", timeout=10000)
            page.fill("input[name='__email'], input[type='email']", INDEED["email"])
            human_delay(0.5, 1)
        except Exception:
            logger.error("[Indeed] Email field not found")
            return False

        # Click Continue
        safe_click(page, "button[type='submit'], button:has-text('Continue')")
        human_delay(2, 3)

        # Step 2: Enter password — wait for it to become visible
        try:
            page.wait_for_selector("input[type='password']", timeout=10000)
            page.fill("input[type='password']", INDEED["password"])
            human_delay(0.5, 1)
        except Exception:
            logger.error("[Indeed] Password field not found after Continue")
            return False

        safe_click(page, "button[type='submit'], button:has-text('Sign in')")
        human_delay(4, 6)

        if "indeed.com" in page.url and "login" not in page.url and "auth" not in page.url:
            logger.info("[Indeed] Login successful ✓")
            return True

        logger.warning("[Indeed] Login may have failed — check credentials")
        return False

    except Exception as e:
        logger.error(f"[Indeed] Login error: {e}")
        return False


def search_jobs(page: Page, keyword: str) -> list:
    """Search Indeed for jobs. Returns list of job URLs."""
    logger.info(f"[Indeed] Searching: '{keyword}'")
    results = []

    try:
        location = "Remote" if SEARCH.get("remote") else SEARCH["location"]
        url = (f"{BASE_URL}/jobs?q={keyword.replace(' ', '+')}"
               f"&l={location.replace(' ', '+')}"
               f"&sc=0kf%3Aattr(DSQF7)%3B"  # Easily apply filter
               f"&sort=date")

        page.goto(url, timeout=30000)
        human_delay(3, 5)

        for _ in range(2):
            page.keyboard.press("End")
            human_delay(1.5, 2.5)

        # Collect job links
        links = page.locator("h2.jobTitle a, .jcs-JobTitle").all()
        for link in links[:15]:
            try:
                href = link.get_attribute("href")
                if href:
                    full_url = BASE_URL + href if href.startswith("/") else href
                    if full_url not in results:
                        results.append(full_url)
            except Exception:
                continue

        logger.info(f"[Indeed] Found {len(results)} listings for '{keyword}'")

    except Exception as e:
        logger.error(f"[Indeed] Search error: {e}")

    return results


def apply_to_job(page: Page, url: str) -> bool:
    """Apply to a single Indeed job. Returns True on success."""
    try:
        page.goto(url, timeout=30000)
        human_delay(2, 4)

        company = "Unknown"
        role    = "Unknown"
        try:
            role    = page.locator("h1.jobsearch-JobInfoHeader-title").first.inner_text().strip()
            company = page.locator(".jobsearch-CompanyInfoContainer a, "
                                    "[data-testid='inlineHeader-companyName']").first.inner_text().strip()
        except Exception:
            pass

        logger.info(f"[Indeed] Evaluating: {role} @ {company}")

        if already_applied(url):
            logger.info(f"[Indeed] Skipping — already applied: {company}")
            return False

        page_text = page.inner_text("body")
        if contains_excluded(page_text, FILTERS["exclude_keywords"]):
            log_application("Indeed", company, role, url, "Skipped", "excluded keyword")
            return False

        # Click Apply / Easily Apply button
        apply_clicked = False
        for selector in ["button:has-text('Apply now')", "button:has-text('Easily Apply')",
                          "a:has-text('Apply')", ".jobsearch-IndeedApplyButton-newDesign",
                          "button[id*='apply']"]:
            if safe_click(page, selector, timeout=4000):
                apply_clicked = True
                break

        if not apply_clicked:
            logger.info(f"[Indeed] No apply button — skipping: {company}")
            log_application("Indeed", company, role, url, "Skipped", "no apply button")
            return False

        human_delay(2, 4)

        # Indeed may open a new tab / iframe — handle both
        # Check if it redirected to company site (external)
        if "indeed.com" not in page.url:
            logger.info(f"[Indeed] External application — skipping: {company}")
            log_application("Indeed", company, role, url, "Skipped", "external apply")
            return False

        # ── Fill Indeed application form ─────────────────────
        for _ in range(6):
            human_delay(1.5, 2.5)

            # Name fields
            fill_if_visible(page, "input[id*='firstName'], input[name*='firstName']",
                            PROFILE["full_name"].split()[0])
            fill_if_visible(page, "input[id*='lastName'], input[name*='lastName']",
                            PROFILE["full_name"].split()[-1])
            fill_if_visible(page, "input[id*='fullName'], input[name*='name']",
                            PROFILE["full_name"])

            # Contact
            fill_if_visible(page, "input[id*='phone'], input[type='tel']", PROFILE["phone"])
            fill_if_visible(page, "input[id*='email'], input[type='email']", PROFILE["email"])

            # Location
            fill_if_visible(page, "input[id*='city'], input[id*='location']", PROFILE["location"])

            # Resume upload
            try:
                resume_input = page.locator("input[type='file']").first
                if resume_input.is_visible(timeout=1500):
                    import os
                    rp = os.path.abspath(PROFILE["resume_path"])
                    if os.path.exists(rp):
                        resume_input.set_input_files(rp)
                        human_delay(1, 2)
            except Exception:
                pass

            # Textarea (cover letter / additional info)
            for ta in page.locator("textarea:visible").all():
                try:
                    if ta.input_value() == "":
                        cover = PROFILE["cover_letter"].format(
                            company=company, role=role, platform="Indeed"
                        )
                        ta.fill(cover)
                        human_delay(0.3, 0.7)
                except Exception:
                    continue

            # Yes/No radio buttons — default to "Yes"
            for radio in page.locator("input[type='radio']:visible").all():
                try:
                    label_el = page.locator(
                        f"label[for='{radio.get_attribute('id')}']"
                    ).first
                    if "yes" in label_el.inner_text().lower():
                        radio.click()
                        human_delay(0.2, 0.4)
                except Exception:
                    continue

            # Select dropdowns
            for sel in page.locator("select:visible").all():
                try:
                    if not sel.input_value():
                        opts = sel.locator("option").all()
                        for opt in opts:
                            v = opt.get_attribute("value") or ""
                            if v:
                                sel.select_option(v)
                                break
                    human_delay(0.2, 0.4)
                except Exception:
                    continue

            # Submit or Continue
            submitted = False
            for selector in ["button:has-text('Submit')", "button:has-text('Submit application')",
                              "button[type='submit']:has-text('Submit')"]:
                btn = page.locator(selector).first
                try:
                    if btn.is_visible(timeout=1500):
                        btn.click()
                        human_delay(2, 3)
                        submitted = True
                        break
                except Exception:
                    continue

            if submitted:
                page_lower = page.inner_text("body").lower()
                if any(w in page_lower for w in ["application submitted", "applied", "thank you"]):
                    logger.info(f"[Indeed] ✓ Applied: {role} @ {company}")
                    log_application("Indeed", company, role, url, "Applied")
                    return True
                break

            # Continue to next step
            for selector in ["button:has-text('Continue')", "button:has-text('Next')"]:
                if safe_click(page, selector, timeout=3000):
                    break

        logger.warning(f"[Indeed] Submission unclear: {company}")
        screenshot(page, f"indeed_unclear_{company[:20]}")
        log_application("Indeed", company, role, url, "Unclear", "verify manually")
        return False

    except Exception as e:
        logger.error(f"[Indeed] Error applying to {url}: {e}")
        log_application("Indeed", "Unknown", "Unknown", url, "Error", str(e))
        return False


def run(page: Page, applied_count: list):
    """Main Indeed runner."""
    max_apps = SEARCH["max_per_run"]

    if not login(page):
        return

    seen_urls = set()

    for keyword in SEARCH["keywords"]:
        if applied_count[0] >= max_apps:
            logger.info("[Indeed] Daily limit reached.")
            break
        if bot_state.should_stop():
            logger.info("[Indeed] Stop requested.")
            break

        urls = search_jobs(page, keyword)

        for url in urls:
            if applied_count[0] >= max_apps:
                break
            if bot_state.should_stop():
                logger.info("[Indeed] Stop requested.")
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)

            success = apply_to_job(page, url)
            if success:
                applied_count[0] += 1
                logger.info(f"[Indeed] Total applied this run: {applied_count[0]}/{max_apps}")

            human_delay(SEARCH["delay_min"], SEARCH["delay_max"])
