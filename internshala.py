"""
internshala.py — Auto-apply to internships on Internshala
"""

from playwright.sync_api import Page
from config import INTERNSHALA, PROFILE, SEARCH, FILTERS
from utils import (logger, log_application, already_applied,
                   human_delay, human_type, safe_click,
                   fill_if_visible, screenshot, contains_excluded)
from bot_state import state as bot_state

BASE_URL = "https://internshala.com"


def login(page: Page) -> bool:
    """Log into Internshala. Returns True on success."""
    logger.info("[Internshala] Logging in...")
    try:
        page.goto(f"{BASE_URL}/login/student", timeout=30000)
        human_delay(2, 3)

        page.fill("#email", INTERNSHALA["email"])
        human_delay(0.5, 1)
        page.fill("#password", INTERNSHALA["password"])
        human_delay(0.5, 1)
        page.click("#login_submit")
        human_delay(3, 5)

        logger.info("[Internshala] Waiting for login to complete (Solve CAPTCHA/OTP if prompted)...")
        for _ in range(30):
            if "dashboard" in page.url or "student/dashboard" in page.url:
                logger.info("[Internshala] Login successful ✓")
                return True
            if page.locator(".error-block").is_visible(timeout=1000):
                logger.error("[Internshala] Login failed — check credentials in config.py")
                return False
            human_delay(1, 2)
            
        logger.error("[Internshala] Login timed out. Please check the browser.")
        return False

    except Exception as e:
        logger.error(f"[Internshala] Login error: {e}")
        return False


def search_internships(page: Page, keyword: str) -> list:
    """Search for internships and return list of job URLs."""
    logger.info(f"[Internshala] Searching: '{keyword}'")
    results = []

    try:
        # Build search URL — keep "intern" in slug as Internshala expects it
        kw_slug = keyword.lower().replace(" ", "-")

        if SEARCH.get("remote"):
            url = f"{BASE_URL}/internships/work-from-home-{kw_slug}-internship"
        else:
            loc = SEARCH["location"].lower().replace(" ", "-")
            url = f"{BASE_URL}/internships/in-{loc}/{kw_slug}-internship"

        page.goto(url, timeout=30000)
        human_delay(2, 4)

        # Scroll to load more listings
        for _ in range(3):
            try:
                page.keyboard.press("End")
                human_delay(1, 2)
            except Exception:
                break

        # Collect internship links — try multiple selectors
        seen = set()
        for selector in [".internship_meta a", ".view_detail_button", "a[href*='/internship/detail/']"]:
            cards = page.locator(selector).all()
            for card in cards[:15]:
                try:
                    href = card.get_attribute("href")
                    if href and "/internship/detail/" in href:
                        full_url = BASE_URL + href if href.startswith("/") else href
                        if full_url not in seen:
                            seen.add(full_url)
                            results.append(full_url)
                except Exception:
                    continue

        logger.info(f"[Internshala] Found {len(results)} listings for '{keyword}'")

    except Exception as e:
        logger.error(f"[Internshala] Search error: {e}")

    return results


def apply_to_internship(page: Page, url: str) -> bool:
    """Visit a single internship page and apply. Returns True on success."""
    try:
        page.goto(url, timeout=30000)
        human_delay(2, 4)

        # Extract company and role info
        company = "Unknown Company"
        role    = "Internship"
        try:
            company = page.locator(".company_name a, .company-name").first.inner_text().strip()
        except Exception:
            pass
        try:
            role = page.locator("h1.heading_4_5, .profile").first.inner_text().strip()
        except Exception:
            pass

        logger.info(f"[Internshala] Evaluating: {role} @ {company}")

        # Skip if already applied
        if already_applied(url):
            logger.info(f"[Internshala] Skipping — already applied: {company}")
            return False

        # Check for excluded keywords
        page_text = page.inner_text("body")
        if contains_excluded(page_text, FILTERS["exclude_keywords"]):
            logger.info(f"[Internshala] Skipping — excluded keyword matched: {company}")
            log_application("Internshala", company, role, url, "Skipped", "excluded keyword")
            return False

        # Check stipend if filter is set
        if FILTERS["min_stipend"] > 0:
            try:
                stipend_text = page.locator(".stipend").first.inner_text()
                numbers = [int(s.replace(",","")) for s in stipend_text.split() if s.replace(",","").isdigit()]
                if numbers and max(numbers) < FILTERS["min_stipend"]:
                    logger.info(f"[Internshala] Skipping — stipend too low: {company}")
                    return False
            except Exception:
                pass

        # Click Apply button
        apply_clicked = False
        for selector in ["#apply_button", ".apply_button", "button:has-text('Apply Now')",
                         "a:has-text('Apply Now')", ".easy_apply"]:
            if safe_click(page, selector):
                apply_clicked = True
                break

        if not apply_clicked:
            logger.warning(f"[Internshala] Could not find Apply button: {company}")
            log_application("Internshala", company, role, url, "Failed", "no apply button")
            return False

        human_delay(2, 3)

        # ── Fill application form ────────────────────────────
        # Availability question
        fill_if_visible(page, "input[name='availability']", "1")
        fill_if_visible(page, "textarea[placeholder*='availability']", "I am available to start immediately.")

        # Why should we hire you / cover letter
        cover = PROFILE["cover_letter"].format(
            company=company, role=role, platform="Internshala"
        )
        for selector in ["#cover_letter", "textarea[name='cover_letter']",
                         "textarea[placeholder*='cover letter']",
                         "textarea[placeholder*='why']"]:
            if fill_if_visible(page, selector, cover):
                break

        # Custom questions — answer generically
        text_areas = page.locator("textarea:visible").all()
        for ta in text_areas:
            try:
                placeholder = (ta.get_attribute("placeholder") or "").lower()
                if ta.input_value() == "":
                    if "skill" in placeholder or "experience" in placeholder:
                        ta.fill(PROFILE["skills"])
                    elif "available" in placeholder:
                        ta.fill("I can start immediately and am available full-time.")
                    elif "why" in placeholder or "interest" in placeholder:
                        ta.fill(f"I am genuinely interested in the {role} role at {company} "
                                f"and believe my skills in {PROFILE['skills']} align well with "
                                f"your requirements.")
                    else:
                        ta.fill("I am highly motivated and ready to contribute to your team.")
                    human_delay(0.3, 0.7)
            except Exception:
                continue

        # Submit
        submitted = False
        for selector in ["#submit", "button[type='submit']",
                         "button:has-text('Submit')", "input[type='submit']",
                         "button:has-text('Apply')"]:
            if safe_click(page, selector, timeout=4000):
                submitted = True
                break

        human_delay(2, 3)

        # Confirm success
        success_indicators = ["successfully applied", "application submitted",
                               "thank you", "applied successfully"]
        page_text_lower = page.inner_text("body").lower()
        success = submitted and any(ind in page_text_lower for ind in success_indicators)

        if success or submitted:
            logger.info(f"[Internshala] ✓ Applied: {role} @ {company}")
            log_application("Internshala", company, role, url, "Applied")
            return True
        else:
            logger.warning(f"[Internshala] Submission unclear for: {company}")
            screenshot(page, f"internshala_unclear_{company[:20]}")
            log_application("Internshala", company, role, url, "Unclear", "verify manually")
            return False

    except Exception as e:
        logger.error(f"[Internshala] Error applying to {url}: {e}")
        log_application("Internshala", "Unknown", "Unknown", url, "Error", str(e))
        return False


def search_internships_via_search_page(page: Page, keyword: str) -> list:
    """Fallback: Use Internshala's actual search page instead of URL slugs."""
    logger.info(f"[Internshala] Fallback search: '{keyword}'")
    results = []

    try:
        page.goto(f"{BASE_URL}/internships", timeout=30000)
        human_delay(2, 3)

        # Try using the search input on the internships page
        search_input = page.locator("input#keywords, input[name='keywords'], input[placeholder*='search'], #search_input")
        try:
            if search_input.first.is_visible(timeout=3000):
                search_input.first.fill("")
                human_delay(0.3, 0.5)
                search_input.first.fill(keyword)
                human_delay(0.5, 1)
                page.keyboard.press("Enter")
                human_delay(3, 5)
        except Exception:
            # Fallback to URL-based search with simpler slug
            kw_slug = keyword.lower().replace(" ", "-")
            page.goto(f"{BASE_URL}/internships/{kw_slug}-internship", timeout=30000)
            human_delay(2, 4)

        # Scroll
        for _ in range(3):
            try:
                page.keyboard.press("End")
                human_delay(1, 2)
            except Exception:
                break

        # Collect links
        for selector in [".internship_meta a", ".view_detail_button", "a[href*='/internship/detail/']"]:
            cards = page.locator(selector).all()
            for card in cards[:15]:
                try:
                    href = card.get_attribute("href")
                    if href and "/internship/detail/" in href:
                        full_url = BASE_URL + href if href.startswith("/") else href
                        if full_url not in results:
                            results.append(full_url)
                except Exception:
                    continue

        logger.info(f"[Internshala] Fallback found {len(results)} listings for '{keyword}'")

    except Exception as e:
        logger.error(f"[Internshala] Fallback search error: {e}")

    return results


def run(page: Page, applied_count: list):
    """Main Internshala runner with smart fallback search."""
    max_apps = SEARCH["max_per_run"]

    if not login(page):
        return

    seen_urls = set()
    total_found = 0

    # ── Phase 1: Try primary keywords ───────────────────────────
    for keyword in SEARCH["keywords"]:
        if applied_count[0] >= max_apps:
            logger.info("[Internshala] Daily limit reached.")
            break
        if bot_state.should_stop():
            logger.info("[Internshala] Stop requested.")
            break

        urls = search_internships(page, keyword)
        total_found += len(urls)

        for url in urls:
            if applied_count[0] >= max_apps:
                break
            if bot_state.should_stop():
                logger.info("[Internshala] Stop requested.")
                break
            if url in seen_urls:
                continue
            seen_urls.add(url)

            success = apply_to_internship(page, url)
            if success:
                applied_count[0] += 1
                logger.info(f"[Internshala] Total applied this run: {applied_count[0]}/{max_apps}")

            human_delay(SEARCH["delay_min"], SEARCH["delay_max"])

    # ── Phase 2: If primary keywords found nothing, try fallback ─
    if total_found == 0 and applied_count[0] < max_apps:
        fallback_keywords = SEARCH.get("fallback_keywords", [])
        if fallback_keywords:
            logger.info(f"[Internshala] Primary keywords found 0 jobs. Trying {len(fallback_keywords)} fallback keywords...")

            for keyword in fallback_keywords:
                if applied_count[0] >= max_apps:
                    logger.info("[Internshala] Daily limit reached.")
                    break
                if bot_state.should_stop():
                    logger.info("[Internshala] Stop requested.")
                    break

                # Try URL-based search first
                urls = search_internships(page, keyword)

                # If still 0, try the search page method
                if not urls:
                    urls = search_internships_via_search_page(page, keyword)

                for url in urls:
                    if applied_count[0] >= max_apps:
                        break
                    if bot_state.should_stop():
                        logger.info("[Internshala] Stop requested.")
                        break
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    success = apply_to_internship(page, url)
                    if success:
                        applied_count[0] += 1
                        logger.info(f"[Internshala] Total applied this run: {applied_count[0]}/{max_apps}")

                    human_delay(SEARCH["delay_min"], SEARCH["delay_max"])

    if total_found == 0 and applied_count[0] == 0:
        logger.warning("[Internshala] No jobs found with any keywords. Try updating keywords in config.py")
