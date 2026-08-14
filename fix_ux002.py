#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-002 — Login loading state, off-thread PIN verification.

Changes sentinel/ui/login.py only:

  1. PBKDF2 PIN verification now runs in a QThread — the login window
     no longer freezes for seconds while every user row is hashed.
  2. Loading state: while verifying, the button dims and reads
     "VERIFYING…", the PIN field is disabled, and the status line shows
     an amber "VERIFYING…" — no double-submit possible (attempts while
     busy are ignored).
  3. Empty PINs get an inline hint instead of being submitted.
  4. No active operators produces an explicit message instead of a
     generic "PIN rejected".

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/login.py
"""
import os
import sys

TARGET = "sentinel/ui/login.py"

WORKER_CLASS = '''class _PinWorker(QObject):
    """Runs PBKDF2 verification off the UI thread."""

    ok = Signal(int, str)
    bad = Signal()
    done = Signal()

    def __init__(self, pin, users):
        super().__init__()
        self._pin = pin
        self._users = users

    def run(self):
        try:
            for uid, name, pin_hash, pin_salt in self._users:
                if verify_pin(self._pin, pin_hash, pin_salt):
                    self.ok.emit(uid, name)
                    break
            else:
                self.bad.emit()
        except Exception:
            self.bad.emit()
        self.done.emit()


'''

OLD_ATTEMPT = '''    def attempt_login(self):
        pin = self.pin_in.text()
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT id, display_name, pin_hash, pin_salt FROM users WHERE is_active = 1"
        )
        for u in cursor.fetchall():
            if verify_pin(pin, u[2], u[3]):
                self.err.setText("")
                self.on_success(u[0], u[1])
                return
        self.pin_in.clear()
        self.err.setText("PIN rejected  ·  station remains locked")
        self.pin_in.setFocus()
'''

NEW_ATTEMPT = '''    def attempt_login(self):
        """Start PIN verification off the UI thread (UX-002)."""
        if self._busy:
            return
        pin = self.pin_in.text().strip()
        if not pin:
            self.err.setText("Enter the four-digit PIN")
            self.pin_in.setFocus()
            return
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT id, display_name, pin_hash, pin_salt FROM users WHERE is_active = 1"
        )
        users = [(r[0], r[1], r[2], r[3]) for r in cursor.fetchall()]
        if not users:
            self.err.setText("No active operators  ·  station remains locked")
            self.pin_in.setFocus()
            return
        self._set_busy(True)
        self._thread = QThread(self)
        self._worker = _PinWorker(pin, users)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.ok.connect(self._on_login_ok)
        self._worker.bad.connect(self._on_login_bad)
        self._worker.done.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

    def _set_busy(self, busy):
        """Loading state: disable inputs, dim the button, show VERIFYING…"""
        self._busy = busy
        self.btn.setEnabled(not busy)
        self.pin_in.setEnabled(not busy)
        if busy:
            self.err.setText("VERIFYING…")
            self.err.setStyleSheet(
                "color: #E8B86D; font-size: 11px; font-weight: 600; min-height: 16px;"
            )
            self.btn.setText("VERIFYING…")
            self.btn.setStyleSheet("""
                QPushButton {
                    background: #181C23;
                    color: #8B93A7;
                    border: 1px solid #2A3140;
                    border-radius: 10px;
                    font-weight: 800;
                    font-size: 13px;
                    letter-spacing: 0.12em;
                    padding: 0 22px;
                }
            """)
        else:
            self.err.setStyleSheet(self._err_style)
            self.btn.setText("INITIATE SESSION")
            self.btn.setStyleSheet(self._btn_style)

    def _on_login_ok(self, user_id, display_name):
        self._set_busy(False)
        self.err.setText("")
        self.on_success(user_id, display_name)

    def _on_login_bad(self):
        self._set_busy(False)
        self.pin_in.clear()
        self.err.setText("PIN rejected  ·  station remains locked")
        self.pin_in.setFocus()
'''

EDITS = [
    (
        "QtCore import gains QThread + Signal + QObject",
        "from PySide6.QtCore import Qt",
        "from PySide6.QtCore import Qt, QThread, Signal, QObject",
    ),
    (
        "_PinWorker class inserted before SaaSLogin",
        "class SaaSLogin(QWidget):",
        WORKER_CLASS + "class SaaSLogin(QWidget):",
    ),
    (
        "busy state + style captures initialized",
        '        self.btn = IndustrialButton("INITIATE SESSION")',
        '        self.btn = IndustrialButton("INITIATE SESSION")\n'
        "        self._btn_style = self.btn.styleSheet()\n"
        "        self._err_style = self.err.styleSheet()\n"
        "        self._busy = False",
    ),
    (
        "attempt_login replaced with off-thread verification + loading state",
        OLD_ATTEMPT,
        NEW_ATTEMPT,
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

    tmp = TARGET + ".ux002.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
