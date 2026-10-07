"""Auto punch in / punch out for hrm.fts-pl.com.

Usage:
    python punch.py in        -> punch in (once per day)
    python punch.py out       -> punch out (only after punch in; latest one counts)
    python punch.py in --dry  -> log in only, do NOT punch
"""
import json
import re
import sys
import time
import logging
from datetime import date
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent
CONFIG = json.loads((BASE / "config.json").read_text())
STATE_FILE = BASE / "state.json"

SITE = "https://hrm.fts-pl.com"
LOGIN_URL = SITE + "/accounts/login/?next=/attendance/"
ATTENDANCE_URL = SITE + "/attendance/"

logging.basicConfig(
    filename=BASE / "punch.log",
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger()
if sys.stdout:
    log.addHandler(logging.StreamHandler())


def load_state():
    try:
        state = json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    if state.get("date") != date.today().isoformat():
        state = {"date": date.today().isoformat(), "in": False, "out": False}
    return state


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


def csrf_token(html):
    m = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html)
    if not m:
        raise RuntimeError("CSRF token not found on page")
    return m.group(1)


def do_punch(dry=False, timeout=20):
    s = requests.Session()
    r = s.get(LOGIN_URL, timeout=timeout)
    r = s.post(
        LOGIN_URL,
        data={"csrfmiddlewaretoken": csrf_token(r.text),
              "username": CONFIG["email"], "password": CONFIG["password"]},
        headers={"Referer": LOGIN_URL},
        timeout=timeout,
    )
    if "/accounts/login" in r.url or 'id="id_attendance"' not in r.text:
        raise RuntimeError("Login failed - check email/password in config.json")
    log.info("Logged in")
    if dry:
        log.info("Dry run - not punching")
        return
    r = s.post(
        ATTENDANCE_URL,
        data={"csrfmiddlewaretoken": csrf_token(r.text), "latitude": "", "longitude": ""},
        headers={"Referer": ATTENDANCE_URL},
        timeout=timeout,
    )
    r.raise_for_status()
    today = s.get(SITE + "/api/attendances/?user=408", timeout=timeout).json()
    if today:
        latest = today[0] if isinstance(today, list) else today
        log.info("Site record: %s", latest)


def punch(action, dry=False, attempts=3, wait_net=180):
    """Returns True on success (or when skipped because nothing to do)."""
    state = load_state()
    if not dry:
        if action == "in" and state["in"]:
            log.info("Already punched in today - skipping")
            return True
        # Punch out may repeat: the site keeps the latest click as the punch-out time
        if action == "out" and not state["in"]:
            log.info("Punch out skipped - not punched in today")
            return True

    log.info("Punch %s started%s", action, " (dry run)" if dry else "")
    end = time.time() + wait_net
    attempt = 0
    while True:
        attempt += 1
        try:
            do_punch(dry)
            if not dry:
                state[action] = True
                save_state(state)
                log.info("Punch %s done", action.upper())
            return True
        except Exception as e:
            log.warning("Attempt %d failed: %s", attempt, e)
            if attempt >= attempts and time.time() > end:
                log.error("Punch %s FAILED", action)
                return False
            time.sleep(5)


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("in", "out"):
        print(__doc__)
        sys.exit(1)
    ok = punch(sys.argv[1], dry="--dry" in sys.argv)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
