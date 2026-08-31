"""
Verify CRO fixes on results page:
1. Dimensions are hidden before email entry
2. Dimensions appear after email entry
3. Email gate text is updated
4. Grade summary uses new (softer) copy
"""
from playwright.sync_api import sync_playwright

BASE = "https://gradeforai.com"
TEST_URL = "bmutlucpa.com"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})

        # Navigate to a results page
        page.goto(f"{BASE}/?url={TEST_URL}", wait_until="networkidle")

        # Find and click scan
        scan_input = page.locator("input[type='text'], input[type='url'], #url-input").first
        scan_input.fill(TEST_URL)
        scan_btn = page.locator("button:has-text('Scan'), button:has-text('Grade'), button:has-text('Check'), button[type='submit']").first
        scan_btn.click()
        page.wait_for_timeout(10000)

        # Take screenshot BEFORE email entry
        page.screenshot(path="/tmp/results_before_email.png", full_page=True)

        content = page.content()

        # Check 1: Email gate has updated text
        has_new_cta = "Get My Breakdown" in content
        print(f"[{'PASS' if has_new_cta else 'FAIL'}] Email gate button says 'Get My Breakdown'")

        has_new_heading = "See Your Full Score Breakdown" in content
        print(f"[{'PASS' if has_new_heading else 'FAIL'}] Email gate heading updated")

        # Check 2: Dimensions section is hidden
        dim_section = page.locator("#dimensions-section")
        is_hidden = not dim_section.is_visible()
        print(f"[{'PASS' if is_hidden else 'FAIL'}] Dimensions hidden before email entry")

        # Check 3: Softer grade summary
        has_soft_f = "mostly unable" in content or "most room to improve" in content
        print(f"[{'PASS' if has_soft_f else 'FAIL'}] Grade F summary uses softer language")

        # Now enter email and unlock
        email_input = page.locator("#email-input")
        if email_input.is_visible():
            email_input.fill("test@gradeforai.com")
            unlock_btn = page.locator("button:has-text('Get My Breakdown')")
            unlock_btn.click()
            page.wait_for_timeout(1000)

            # Take screenshot AFTER email entry
            page.screenshot(path="/tmp/results_after_email.png", full_page=True)

            # Check 4: Dimensions now visible
            is_visible = dim_section.is_visible()
            print(f"[{'PASS' if is_visible else 'FAIL'}] Dimensions visible after email entry")

            # Check 5: Email gate hidden
            gate = page.locator("#email-gate")
            gate_hidden = not gate.is_visible()
            print(f"[{'PASS' if gate_hidden else 'FAIL'}] Email gate hidden after entry")
        else:
            print("[FAIL] Email input not found")

        browser.close()


if __name__ == "__main__":
    run()
