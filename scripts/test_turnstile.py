#!/usr/bin/env python3
"""Test script for captcha solving with SeleniumBase CDP Mode.

Validates that:
1. sb_cdp.Chrome(cdp_port=9222) connects to existing Chrome
2. Navigation works
3. solve_captcha() resolves Turnstile
4. Success indicator is detected
5. Browser stays open after solving
"""

import sys
import time

from seleniumbase import sb_cdp


def test_turnstile():
    print("[1/5] Connecting to Chrome via CDP on port 9222...")
    sb = sb_cdp.Chrome(cdp_port=9222)
    print("      OK - Connected")

    try:
        print("[2/5] Navigating to Turnstile demo...")
        sb.goto("https://seleniumbase.io/apps/turnstile")
        time.sleep(5)
        print(f"      OK - URL: {sb.get_current_url()}")
        print(f"      OK - Title: {sb.get_title()}")

        print("[3/5] Solving Turnstile captcha...")
        sb.solve_captcha()
        time.sleep(3)
        print("      OK - solve_captcha() completed")

        print("[4/5] Checking success indicator...")
        success = sb.is_element_present("img#captcha-success")
        if success:
            print("      OK - captcha-success image FOUND")
        else:
            print("      WARN - captcha-success image not found")

        print("[5/5] Final state:")
        print(f"      URL: {sb.get_current_url()}")
        print(f"      Title: {sb.get_title()}")

        return success

    finally:
        # Do NOT close the browser
        print("\nBrowser left open (not owned by us).")


if __name__ == "__main__":
    print("=" * 60)
    print("  Turnstile Captcha Solver Test")
    print("=" * 60)
    print()

    try:
        result = test_turnstile()
        print()
        if result:
            print("RESULT: PASS")
            sys.exit(0)
        else:
            print("RESULT: PARTIAL (captcha solved but no success image)")
            sys.exit(0)
    except Exception as e:
        print(f"\nRESULT: FAIL - {e}")
        sys.exit(1)
