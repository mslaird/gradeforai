"""
End-to-end test of the GradeForAI scan flow:
1. Homepage loads, hero visible, scan input works
2. Enter a URL and submit scan
3. Results page loads with score
4. Email gate appears
5. CTA / payment link is accessible
6. Check for broken links, console errors, mobile responsiveness
"""
from playwright.sync_api import sync_playwright
import json
import time

BASE = "https://gradeforai.com"
TEST_URL = "bmutlucpa.com"  # Known scored business
RESULTS = []
CONSOLE_ERRORS = []


def log(test, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({"test": test, "passed": passed, "detail": detail})
    print(f"  [{status}] {test}" + (f" -- {detail}" if detail else ""))


def run_tests():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ====== DESKTOP TESTS ======
        print("\n=== DESKTOP TESTS ===\n")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Capture console errors
        page.on("console", lambda msg: CONSOLE_ERRORS.append(msg.text) if msg.type == "error" else None)

        # TEST 1: Homepage loads
        try:
            resp = page.goto(BASE, wait_until="networkidle", timeout=15000)
            log("Homepage loads", resp.status == 200, f"Status: {resp.status}")
        except Exception as e:
            log("Homepage loads", False, str(e))

        # TEST 2: Hero section visible
        try:
            hero = page.locator(".hero, #hero, [class*='hero']").first
            hero.wait_for(timeout=5000)
            log("Hero section visible", hero.is_visible())
        except Exception as e:
            log("Hero section visible", False, str(e))

        # TEST 3: Scan input exists
        try:
            scan_input = page.locator("input[type='text'], input[type='url'], input[name='url'], #url-input, #scan-input, .scan-input").first
            scan_input.wait_for(timeout=5000)
            log("Scan input exists", scan_input.is_visible())
        except Exception as e:
            log("Scan input exists", False, str(e))

        # TEST 4: Scan button exists
        try:
            scan_btn = page.locator("button:has-text('Scan'), button:has-text('Grade'), button:has-text('Check'), button[type='submit'], .scan-btn").first
            scan_btn.wait_for(timeout=5000)
            log("Scan button exists", scan_btn.is_visible())
        except Exception as e:
            log("Scan button exists", False, str(e))

        # Take screenshot of homepage
        page.screenshot(path="/tmp/gradeforai_homepage_desktop.png", full_page=True)

        # TEST 5: Submit a scan
        try:
            scan_input = page.locator("input[type='text'], input[type='url'], input[name='url'], #url-input, #scan-input, .scan-input").first
            scan_input.fill(TEST_URL)
            scan_btn = page.locator("button:has-text('Scan'), button:has-text('Grade'), button:has-text('Check'), button[type='submit'], .scan-btn").first
            scan_btn.click()
            # Wait for navigation or results
            page.wait_for_timeout(8000)
            current_url = page.url
            log("Scan submits and navigates", "result" in current_url.lower() or "scan" in current_url.lower() or page.url != BASE, f"URL: {current_url}")
        except Exception as e:
            log("Scan submits and navigates", False, str(e))

        # Take screenshot of results
        page.screenshot(path="/tmp/gradeforai_results_desktop.png", full_page=True)

        # TEST 6: Score displayed
        try:
            page.wait_for_timeout(3000)
            content = page.content()
            has_score = any(s in content for s in ["/100", "out of 100", "score", "Score"])
            log("Score displayed on results", has_score)
        except Exception as e:
            log("Score displayed on results", False, str(e))

        # TEST 7: Email gate present
        try:
            email_input = page.locator("input[type='email']").first
            has_email = email_input.is_visible()
            log("Email gate present", has_email)
        except Exception as e:
            log("Email gate present", False, str(e))

        # TEST 8: Check for payment/upgrade CTA
        try:
            content = page.content()
            has_payment = any(s in content.lower() for s in ["report", "$49", "full report", "upgrade", "buy", "stripe", "purchase"])
            log("Payment/upgrade CTA present", has_payment, "Found payment reference" if has_payment else "No payment CTA found")
        except Exception as e:
            log("Payment/upgrade CTA present", False, str(e))

        context.close()

        # ====== MOBILE TESTS ======
        print("\n=== MOBILE TESTS ===\n")
        mobile_context = browser.new_context(
            viewport={"width": 390, "height": 844},
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        mobile_page = mobile_context.new_page()

        # TEST 9: Mobile homepage loads
        try:
            resp = mobile_page.goto(BASE, wait_until="networkidle", timeout=15000)
            log("Mobile homepage loads", resp.status == 200)
        except Exception as e:
            log("Mobile homepage loads", False, str(e))

        mobile_page.screenshot(path="/tmp/gradeforai_homepage_mobile.png", full_page=True)

        # TEST 10: Mobile scan input accessible
        try:
            scan_input = mobile_page.locator("input[type='text'], input[type='url'], input[name='url'], #url-input, #scan-input, .scan-input").first
            log("Mobile scan input accessible", scan_input.is_visible())
        except Exception as e:
            log("Mobile scan input accessible", False, str(e))

        # TEST 11: Mobile nav works
        try:
            hamburger = mobile_page.locator(".hamburger, .nav-burger, .menu-toggle, [class*='hamburger'], [class*='menu-btn'], button[aria-label*='menu']").first
            if hamburger.is_visible():
                hamburger.click()
                mobile_page.wait_for_timeout(500)
                log("Mobile hamburger menu works", True)
            else:
                log("Mobile hamburger menu works", False, "No hamburger found")
        except Exception as e:
            log("Mobile hamburger menu works", False, str(e))

        mobile_page.screenshot(path="/tmp/gradeforai_mobile_nav.png", full_page=True)

        # TEST 12: Mobile scan flow
        try:
            scan_input = mobile_page.locator("input[type='text'], input[type='url'], input[name='url'], #url-input, #scan-input, .scan-input").first
            scan_input.fill(TEST_URL)
            scan_btn = mobile_page.locator("button:has-text('Scan'), button:has-text('Grade'), button:has-text('Check'), button[type='submit'], .scan-btn").first
            scan_btn.click()
            mobile_page.wait_for_timeout(8000)
            current_url = mobile_page.url
            log("Mobile scan submits", "result" in current_url.lower() or mobile_page.url != BASE, f"URL: {current_url}")
        except Exception as e:
            log("Mobile scan submits", False, str(e))

        mobile_page.screenshot(path="/tmp/gradeforai_results_mobile.png", full_page=True)

        mobile_context.close()

        # ====== KEY PAGES TEST ======
        print("\n=== KEY PAGES ===\n")
        ctx = browser.new_context()
        pg = ctx.new_page()

        pages_to_check = [
            ("/aao", "AAO pillar page"),
            ("/glossary", "Glossary"),
            ("/blog/aao-for-plumbers", "Blog: AAO for Plumbers"),
            ("/blog/what-is-llms-txt", "Blog: What is llms.txt"),
            ("/reports/march-2026", "March 2026 Report"),
            ("/privacy", "Privacy Policy"),
            ("/terms", "Terms of Service"),
            ("/llms.txt", "llms.txt"),
            ("/.well-known/agent.json", "agent.json"),
        ]

        for path, name in pages_to_check:
            try:
                resp = pg.goto(f"{BASE}{path}", wait_until="domcontentloaded", timeout=10000)
                log(f"{name} loads", resp.status == 200, f"Status: {resp.status}")
            except Exception as e:
                log(f"{name} loads", False, str(e))

        ctx.close()
        browser.close()

    # ====== SUMMARY ======
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["passed"])
    failed = sum(1 for r in RESULTS if not r["passed"])
    print(f"  Passed: {passed}/{len(RESULTS)}")
    print(f"  Failed: {failed}/{len(RESULTS)}")

    if CONSOLE_ERRORS:
        print(f"\n  Console errors ({len(CONSOLE_ERRORS)}):")
        for err in CONSOLE_ERRORS[:10]:
            print(f"    - {err[:120]}")

    if failed:
        print(f"\n  FAILURES:")
        for r in RESULTS:
            if not r["passed"]:
                print(f"    - {r['test']}: {r['detail']}")


if __name__ == "__main__":
    run_tests()
