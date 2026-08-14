#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-010 — PIN attempt counter + station lockout.

Changes sentinel/ui/login.py only:

  1. Wrong PINs are counted (settings table, so the counter survives
     restarts). The status line shows how many attempts remain:
     "PIN rejected  ·  4 attempts left".
  2. After MAX_ATTEMPTS (5) failures the station locks for LOCK_MINUTES
     (5): PIN field and button disable, a live countdown shows
     "STATION LOCKED  ·  RETRY IN 4:59", then the station unlocks itself
     and focus returns to the PIN field.
  3. A correct PIN resets the counters; a locked station refuses
     verification attempts until the lock expires.
  4. Lock state is restored on launch — restarting the app during a
     lockout re-arms the countdown immediately.

Design note: login is PIN-only (no username), so failures are tracked
station-wide in the settings table — the per-user lockout columns stay
for future multi-operator attribution. The lockout state is checked
before the verification thread even starts.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/login.py
"""
import os
import sys

TARGET = "sentinel/ui/login.py"

CONSTANTS = '''MAX_ATTEMPTS = 5
LOCK_MINUTES = 5


'''

OLD_BAD = '''    def _on_login_ok(self, user_id, display_name):
        self._set_busy(False)
        self.err.setText("")
        self.on_success(user_id, display_name)

    def _on_login_bad(self):
        self._set_busy(False)
        self.pin_in.clear()
        self.err.setText("PIN rejected  ·  station remains locked")
        self.pin_in.setFocus()
'''

NEW_BAD = '''    def _on_login_ok(self, user_id, display_name):
        self._set_busy(False)
        self._set_setting("login_failed_attempts", "0")
        self._set_setting("login_locked_until", "")
        self.err.setText("")
        self.on_success(user_id, display_name)

    def _on_login_bad(self):
        self._set_busy(False)
        try:
            attempts = int(self._get_setting("login_failed_attempts") or 0) + 1
        except ValueError:
            attempts = 1
        if attempts >= MAX_ATTEMPTS:
            until = datetime.now() + timedelta(minutes=LOCK_MINUTES)
            self._set_setting("login_locked_until", until.isoformat())
            self._set_setting("login_failed_attempts", "0")
            self.pin_in.clear()
            self._show_lock_countdown()
            return
        self._set_setting("login_failed_attempts", str(attempts))
        left = MAX_ATTEMPTS - attempts
        suffix = "attempts" if left != 1 else "attempt"
        self.pin_in.clear()
        self.err.setText(f"PIN rejected  ·  {left} {suffix} left")
        self.pin_in.setFocus()

    def _get_setting(self, key, default=""):
        try:
            cur = self.db.conn.cursor()
            cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cur.fetchone()
            return row[0] if row else default
        except Exception:
            return default

    def _set_setting(self, key, value):
        try:
            cur = self.db.conn.cursor()
            cur.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self.db.conn.commit()
        except Exception:
            pass

    def _remaining_lock_seconds(self):
        try:
            raw = self._get_setting("login_locked_until")
            if not raw:
                return 0
            until = datetime.fromisoformat(raw)
            return max(0, int((until - datetime.now()).total_seconds()))
        except Exception:
            return 0

    def _show_lock_countdown(self):
        """Lock the station: disable inputs, count down until unlock."""
        self._lock_remaining = self._remaining_lock_seconds()
        self._set_busy(False)
        self.pin_in.setEnabled(False)
        self.btn.setEnabled(False)
        self._tick_lock()
        self._lock_timer.start()

    def _tick_lock(self):
        if self._lock_remaining <= 0:
            self._lock_timer.stop()
            self.pin_in.setEnabled(True)
            self.btn.setEnabled(True)
            self.err.setText("Station unlocked  ·  enter PIN")
            self.err.setStyleSheet(self._err_style)
            self.pin_in.setFocus()
            return
        mm = self._lock_remaining // 60
        ss = self._lock_remaining % 60
        self.err.setText(f"STATION LOCKED  ·  RETRY IN {mm}:{ss:02d}")
        self.err.setStyleSheet(
            "color: #E07A5F; font-size: 11px; font-weight: 600; min-height: 16px;"
        )
        self._lock_remaining -= 1
'''

EDITS = [
    (
        "datetime import added",
        "from PySide6.QtWidgets import (",
        "from datetime import datetime, timedelta\nfrom PySide6.QtWidgets import (",
    ),
    (
        "lockout constants inserted before _PinWorker",
        "class _PinWorker(QObject):",
        CONSTANTS + "class _PinWorker(QObject):",
    ),
    (
        "QtCore import gains QTimer (for the lockout countdown)",
        "from PySide6.QtCore import Qt, QThread, Signal, QObject",
        "from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer",
    ),
    (
        "lock countdown timer initialized",
        """        self._btn_style = self.btn.styleSheet()
        self._err_style = self.err.styleSheet()
        self._busy = False""",
        """        self._btn_style = self.btn.styleSheet()
        self._err_style = self.err.styleSheet()
        self._busy = False
        self._lock_remaining = 0
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(1000)
        self._lock_timer.timeout.connect(self._tick_lock)""",
    ),
    (
        "lock state restored on launch (restart during a lockout)",
        """        self._lock_timer.timeout.connect(self._tick_lock)""",
        """        self._lock_timer.timeout.connect(self._tick_lock)
        if self._remaining_lock_seconds() > 0:
            QTimer.singleShot(0, self._show_lock_countdown)""",
    ),
    (
        "attempt_login checks the lock before verifying",
        """        if self._busy:
            return
        pin = self.pin_in.text().strip()""",
        """        if self._busy:
            return
        if self._remaining_lock_seconds() > 0:
            self._show_lock_countdown()
            return
        pin = self.pin_in.text().strip()""",
    ),
    (
        "ok/bad handlers gain counter + lockout logic",
        OLD_BAD,
        NEW_BAD,
    ),
]


def main():
    if not os.path.exists(TARGET):
        print(f"[ABORT] {TARGET} not found. Run this script from the repository root.")
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        raw = f.read()

    content = raw.replace("\r\n", "\n")
    if content != raw:
        print("[INFO] CRLF line endings normalized to LF.")

    for label, old, new in EDITS:
        hits = content.count(old)
        if hits == 0:
            print(f"[ABORT] Anchor not found ({hits} hits): {label}")
            print("        Your local file differs from the audited version.")
            print("        No changes were written. Paste the file content and re-check.")
            sys.exit(1)
        if hits > 1:
            print(f"[ABORT] Anchor ambiguous ({hits} hits): {label}")
            print("        No changes were written.")
            sys.exit(1)
        content = content.replace(old, new, 1)
        print(f"[ OK ] {label}")

    tmp = TARGET + ".ux010.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
