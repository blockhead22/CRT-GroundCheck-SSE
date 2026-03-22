"""
Chrome-based session grabber for claude.ai.
Extracts session cookie from Chrome's existing login.

Two modes:
1. Auto: Uses selenium + chromedriver to grab cookies from Chrome profile
2. Manual: Paste cookie string from Chrome DevTools

Usage:
    # Auto mode (requires chromedriver in PATH)
    python chrome_session.py --auto

    # Manual mode
    python chrome_session.py --manual

    # Test existing session
    python chrome_session.py --test
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests


@dataclass
class ClaudeSession:
    cookie: str
    user_agent: str
    organization_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "cookie": self.cookie,
            "user_agent": self.user_agent,
            "organization_id": self.organization_id,
        }

    def save(self, path: str = ".claude_session.json"):
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))
        print(f"Session saved to {path}")

    @classmethod
    def load(cls, path: str = ".claude_session.json") -> Optional["ClaudeSession"]:
        p = Path(path)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        return cls(**data)


SESSION_FILE = str(Path(__file__).parent / ".claude_session.json")


def grab_session_chrome_auto() -> Optional[ClaudeSession]:
    """Use selenium + chromedriver to grab session from Chrome profile."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
    except ImportError:
        print("selenium not installed or chromedriver not found")
        return None

    # Find Chrome user data directory
    if sys.platform == "win32":
        chrome_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data")
    elif sys.platform == "darwin":
        chrome_user_data = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        chrome_user_data = os.path.expanduser("~/.config/google-chrome")

    if not os.path.exists(chrome_user_data):
        print(f"Chrome user data not found at {chrome_user_data}")
        return None

    print(f"Using Chrome profile from: {chrome_user_data}")

    # Copy profile to temp dir to avoid conflict with running Chrome
    import shutil
    import tempfile
    temp_profile = os.path.join(tempfile.gettempdir(), "claude_chrome_session")
    if os.path.exists(temp_profile):
        shutil.rmtree(temp_profile, ignore_errors=True)

    # Only copy essential cookie/login files, not the entire profile
    src_default = os.path.join(chrome_user_data, "Default")
    dst_default = os.path.join(temp_profile, "Default")
    os.makedirs(dst_default, exist_ok=True)

    for fname in ["Cookies", "Cookies-journal", "Login Data", "Login Data-journal",
                   "Preferences", "Secure Preferences", "Local State"]:
        src = os.path.join(src_default, fname)
        if not os.path.exists(src):
            src = os.path.join(chrome_user_data, fname)  # Local State is in root
        if os.path.exists(src):
            dst = os.path.join(dst_default, fname) if fname != "Local State" else os.path.join(temp_profile, fname)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

    print(f"Using temp profile: {temp_profile}")

    opts = Options()
    opts.add_argument(f"--user-data-dir={temp_profile}")
    opts.add_argument("--profile-directory=Default")
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")

    try:
        driver = webdriver.Chrome(options=opts)
        driver.get("https://claude.ai/api/organizations")
        driver.implicitly_wait(10)

        # Get user agent
        user_agent = driver.execute_script("return navigator.userAgent")

        # Get cookies
        cookies = driver.get_cookies()
        cookie_string = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

        # Get org ID from the page content
        org_id = None
        try:
            body = driver.find_element("tag name", "pre")
            if body and body.text:
                orgs = json.loads(body.text)
                if orgs and len(orgs) >= 1 and "uuid" in orgs[0]:
                    org_id = orgs[0]["uuid"]
        except Exception:
            # Try getting page source
            try:
                page_text = driver.find_element("tag name", "body").text
                orgs = json.loads(page_text)
                if orgs and len(orgs) >= 1 and "uuid" in orgs[0]:
                    org_id = orgs[0]["uuid"]
            except Exception:
                pass

        driver.quit()

        if not cookie_string:
            print("No cookies found. Are you logged into claude.ai in Chrome?")
            return None

        session = ClaudeSession(
            cookie=cookie_string,
            user_agent=user_agent or "Mozilla/5.0",
            organization_id=org_id,
        )
        session.save(SESSION_FILE)
        return session

    except Exception as e:
        print(f"Chrome session grab failed: {e}")
        try:
            driver.quit()
        except Exception:
            pass
        return None


def grab_session_manual() -> Optional[ClaudeSession]:
    """Manually paste cookie from Chrome DevTools."""
    print("\n=== Manual Cookie Setup ===")
    print("1. Open Chrome → go to https://claude.ai/chats")
    print("2. Open DevTools (F12) → Network tab")
    print("3. Refresh the page")
    print("4. Click any request to claude.ai")
    print("5. In Headers, find 'Cookie:' under Request Headers")
    print("6. Copy the entire cookie value\n")

    cookie = input("Paste cookie string: ").strip()
    if not cookie:
        print("No cookie provided")
        return None

    # Try to get org ID
    print("\nFetching organization ID...")
    headers = {
        "Cookie": cookie,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    user_agent = headers["User-Agent"]

    org_id = None
    try:
        resp = requests.get("https://claude.ai/api/organizations", headers=headers, timeout=10)
        if resp.status_code == 200:
            orgs = resp.json()
            if orgs and len(orgs) >= 1 and "uuid" in orgs[0]:
                org_id = orgs[0]["uuid"]
                print(f"Organization ID: {org_id}")
        else:
            print(f"Failed to fetch org (status {resp.status_code}). Cookie may be invalid.")
    except Exception as e:
        print(f"Org fetch error: {e}")

    session = ClaudeSession(
        cookie=cookie,
        user_agent=user_agent,
        organization_id=org_id,
    )
    session.save(SESSION_FILE)
    return session


def test_session(session: Optional[ClaudeSession] = None) -> bool:
    """Test if a session is valid by hitting the organizations endpoint."""
    if session is None:
        session = ClaudeSession.load(SESSION_FILE)
    if session is None:
        print("No session found. Run with --auto or --manual first.")
        return False

    headers = {
        "Cookie": session.cookie,
        "User-Agent": session.user_agent,
        "Accept": "application/json",
    }

    try:
        resp = requests.get("https://claude.ai/api/organizations", headers=headers, timeout=10)
        if resp.status_code == 200:
            orgs = resp.json()
            print(f"Session valid! Found {len(orgs)} organization(s)")
            if orgs:
                print(f"  Org: {orgs[0].get('name', 'unknown')} ({orgs[0].get('uuid', '?')[:8]}...)")
            return True
        else:
            print(f"Session invalid (status {resp.status_code})")
            return False
    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Claude.ai Chrome session grabber")
    parser.add_argument("--auto", action="store_true", help="Auto-grab from Chrome profile")
    parser.add_argument("--manual", action="store_true", help="Manual cookie paste")
    parser.add_argument("--test", action="store_true", help="Test existing session")
    args = parser.parse_args()

    if args.auto:
        session = grab_session_chrome_auto()
        if session:
            test_session(session)
    elif args.manual:
        session = grab_session_manual()
        if session:
            test_session(session)
    elif args.test:
        test_session()
    else:
        parser.print_help()
