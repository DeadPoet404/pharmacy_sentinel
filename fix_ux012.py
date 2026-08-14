#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-012 — First-run: factory PIN must be replaced.

Changes two files:
  main.py
    - bootstrap_db() flags any active operator still using the factory
      PIN 1234 with must_change_pin = 1. Idempotent and self-healing:
      once the PIN is changed, 1234 no longer verifies, so the flag is
      never re-applied. Existing databases are migrated the same way.
  sentinel/ui/login.py
    - After a successful login, a user flagged must_change_pin gets a
      modal PIN-change dialog (new PIN 4-8 digits + confirmation,
      inline errors, keyboard flow: PIN ↵ -> CONFIRM ↵ -> saves).
    - Save re-hashes via PBKDF2, clears the flag, and opens the POS.
    - Cancel returns to the login screen with
      "SET A NEW PIN TO CONTINUE" — the station stays locked until the
      PIN is changed.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; both files validated before any write;
atomic writes via os.replace.
Rollback: git checkout -- main.py sentinel/ui/login.py
"""
import os
import sys

PIN_DIALOG_CLASS = '''class PinChangeDialog(QDialog):
    """Forced PIN change on first login (UX-012)."""

    def __init__(self, db_manager, user_id, display_name, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = user_id
        self.display_name = display_name
        self.setWindowTitle("STATION SETUP")
        self.setFixedSize(440, 460)
        self.setStyleSheet(GLOBAL_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 28, 28, 28)
        root.setSpacing(14)

        kicker = QLabel("FIRST LOGIN  ·  STATION SETUP")
        kicker.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 11px; font-weight: 800; letter-spacing: 0.24em;"
        )
        title = QLabel("Set a new PIN")
        title.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: 28px; font-weight: 800; letter-spacing: -1px;"
        )
        sub = QLabel(
            f"Operator: {display_name}\\n"
            "The factory PIN 1234 must be replaced before the station opens."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 13px;")

        self.new_pin = QLineEdit()
        self.new_pin.setEchoMode(QLineEdit.Password)
        self.new_pin.setMaxLength(8)
        self.new_pin.setPlaceholderText("NEW PIN  ·  4–8 DIGITS")
        self.new_pin.setAlignment(Qt.AlignCenter)

        self.confirm_pin = QLineEdit()
        self.confirm_pin.setEchoMode(QLineEdit.Password)
        self.confirm_pin.setMaxLength(8)
        self.confirm_pin.setPlaceholderText("REPEAT NEW PIN")
        self.confirm_pin.setAlignment(Qt.AlignCenter)

        self.err = QLabel("")
        self.err.setAlignment(Qt.AlignCenter)
        self.err.setStyleSheet(
            "color: #E07A5F; font-size: 11px; font-weight: 600; min-height: 16px;"
        )

        self.save_btn = IndustrialButton("SET PIN  ·  OPEN STATION")
        self.save_btn.clicked.connect(self.save)
        cancel_btn = IndustrialButton("CANCEL", primary=False)
        cancel_btn.clicked.connect(self.reject)

        root.addWidget(kicker)
        root.addWidget(title)
        root.addWidget(sub)
        root.addSpacing(8)
        root.addWidget(self.new_pin)
        root.addWidget(self.confirm_pin)
        root.addWidget(self.err)
        root.addSpacing(8)
        root.addWidget(self.save_btn)
        root.addWidget(cancel_btn)

        # Keyboard flow: PIN ↵ -> CONFIRM ↵ -> save
        self.new_pin.returnPressed.connect(self.confirm_pin.setFocus)
        self.confirm_pin.returnPressed.connect(self.save)
        QTimer.singleShot(0, self.new_pin.setFocus)

    def save(self):
        pin = self.new_pin.text().strip()
        confirm = self.confirm_pin.text().strip()
        if not (pin.isdigit() and 4 <= len(pin) <= 8):
            self.err.setText("PIN MUST BE 4–8 DIGITS")
            self.new_pin.setFocus()
            return
        if pin != confirm:
            self.err.setText("PINS DO NOT MATCH")
            self.confirm_pin.setFocus()
            return
        self.save_btn.setEnabled(False)
        self.save_btn.setText("SAVING…")
        try:
            h, s = hash_pin(pin)
            cur = self.db.conn.cursor()
            cur.execute(
                "UPDATE users SET pin_hash = ?, pin_salt = ?, must_change_pin = 0 "
                "WHERE id = ?",
                (h, s, self.user_id),
            )
            self.db.conn.commit()
            self.accept()
        except Exception as e:
            self.save_btn.setEnabled(True)
            self.save_btn.setText("SET PIN  ·  OPEN STATION")
            self.err.setText(f"SAVE FAILED  ·  {str(e)[:60]}")


'''

OLD_OK = '''    def _on_login_ok(self, user_id, display_name):
        self._set_busy(False)
        self._set_setting("login_failed_attempts", "0")
        self._set_setting("login_locked_until", "")
        self.err.setText("")
        self.on_success(user_id, display_name)
'''

NEW_OK = '''    def _on_login_ok(self, user_id, display_name):
        self._set_busy(False)
        self._set_setting("login_failed_attempts", "0")
        self._set_setting("login_locked_until", "")
        self.err.setText("")
        if self._must_change_pin(user_id):
            self._open_pin_change(user_id, display_name)
            return
        self.on_success(user_id, display_name)

    def _must_change_pin(self, user_id):
        try:
            cur = self.db.conn.cursor()
            cur.execute("SELECT must_change_pin FROM users WHERE id = ?", (user_id,))
            row = cur.fetchone()
            return bool(row and row[0])
        except Exception:
            return False

    def _open_pin_change(self, user_id, display_name):
        dlg = PinChangeDialog(self.db, user_id, display_name, self)
        dlg.setWindowModality(Qt.WindowModal)
        self._change_dlg = dlg
        dlg.finished.connect(
            lambda result: self._on_pin_change_finished(user_id, display_name, result)
        )
        dlg.show()

    def _on_pin_change_finished(self, user_id, display_name, result):
        if result == QDialog.Accepted:
            self.err.setText("")
            self.on_success(user_id, display_name)
        else:
            self.err.setText("SET A NEW PIN TO CONTINUE")
            self.pin_in.setFocus()
'''

FILES = [
    ("main.py", [
        (
            "verify_pin imported for the factory-PIN check",
            "from sentinel.security.auth import hash_pin",
            "from sentinel.security.auth import hash_pin, verify_pin",
        ),
        (
            "bootstrap_db flags factory-PIN users",
            '''def bootstrap_db(db):
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        h, s = hash_pin("1234")
        db.conn.execute("INSERT INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at) VALUES (?, 'admin', 'ADMIN', 'owner', ?, ?, 'now')", (str(uuid.uuid4()), h, s))
        db.conn.commit()''',
            '''def bootstrap_db(db):
    cursor = db.conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        h, s = hash_pin("1234")
        db.conn.execute("INSERT INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at) VALUES (?, 'admin', 'ADMIN', 'owner', ?, ?, 'now')", (str(uuid.uuid4()), h, s))
        db.conn.commit()
    # UX-012: anyone still using the factory PIN must replace it before
    # the station opens. Self-healing: once changed, 1234 stops matching.
    cursor.execute("SELECT id, pin_hash, pin_salt, must_change_pin FROM users WHERE is_active = 1")
    for uid, pin_hash_blob, pin_salt_blob, must_change in cursor.fetchall():
        if not must_change and verify_pin("1234", pin_hash_blob, pin_salt_blob):
            db.conn.execute("UPDATE users SET must_change_pin = 1 WHERE id = ?", (uid,))
    db.conn.commit()''',
        ),
    ]),
    ("sentinel/ui/login.py", [
        (
            "QtWidgets import gains QDialog",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame, QSizePolicy,
)""",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame, QSizePolicy,
    QDialog,
)""",
        ),
        (
            "hash_pin imported for the PIN-change save",
            "from sentinel.security.auth import verify_pin",
            "from sentinel.security.auth import verify_pin, hash_pin",
        ),
        (
            "PinChangeDialog class inserted before SaaSLogin",
            "class SaaSLogin(QWidget):",
            PIN_DIALOG_CLASS + "class SaaSLogin(QWidget):",
        ),
        (
            "login success now routes flagged users through the PIN change",
            OLD_OK,
            NEW_OK,
        ),
    ]),
]


def main():
    contents = {}
    # Pass 1 — validate every anchor for every file BEFORE writing anything.
    for path, edits in FILES:
        if not os.path.exists(path):
            print(f"[ABORT] {path} not found. Run this script from the repository root.")
            sys.exit(1)
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        content = raw.replace("\r\n", "\n")
        contents[path] = content
        for label, old, new in edits:
            hits = content.count(old)
            if hits == 0:
                print(f"[ABORT] Anchor not found ({hits} hits): {path} -> {label}")
                print("        Your local file differs from the audited version.")
                print("        No changes were written. Paste the file content and re-check.")
                sys.exit(1)
            if hits > 1:
                print(f"[ABORT] Anchor ambiguous ({hits} hits): {path} -> {label}")
                print("        No changes were written.")
                sys.exit(1)
    # Pass 2 — apply.
    for path, edits in FILES:
        content = contents[path]
        for label, old, new in edits:
            content = content.replace(old, new, 1)
            print(f"[ OK ] {path} -> {label}")
        tmp = path + ".ux012.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    print("[DONE] Patch applied.")
    print("Next: python3 -m py_compile main.py sentinel/ui/login.py")


if __name__ == "__main__":
    main()
