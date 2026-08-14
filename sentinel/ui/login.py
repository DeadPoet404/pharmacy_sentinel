from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame, QSizePolicy,
    QDialog,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject, QTimer
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, COLOR_ACCENT, COLOR_DIM,
    COLOR_TEXT, COLOR_MUTED, COLOR_BORDER, COLOR_SURFACE, COLOR_BG,
)
from sentinel.security.auth import verify_pin, hash_pin


MAX_ATTEMPTS = 5
LOCK_MINUTES = 5


class _PinWorker(QObject):
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


class PinChangeDialog(QDialog):
    """Forced PIN change on first login (UX-012)."""

    def __init__(self, db_manager, user_id, display_name, parent=None):
        super().__init__(parent)
        self.db = db_manager
        self.user_id = user_id
        self.display_name = display_name
        self.setWindowTitle("STATION SETUP")
        self.setMinimumSize(440, 460)
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
            f"Operator: {display_name}\n"
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


class SaaSLogin(QWidget):
    def __init__(self, db_manager, on_login_success):
        super().__init__()
        self.db, self.on_success = db_manager, on_login_success
        self.setWindowTitle("SENTINEL")
        self.setMinimumSize(1100, 680)
        self.resize(1280, 800)
        self.setStyleSheet(GLOBAL_STYLE)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── left: brand panel ─────────────────────────────────────────────
        hero = QFrame()
        hero.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #0E1116, stop:0.55 #12100C, stop:1 #1A150E);
                border: none;
                border-right: 1px solid {COLOR_BORDER};
            }}
        """)
        hl = QVBoxLayout(hero)
        hl.setContentsMargins(56, 48, 56, 48)
        hl.setSpacing(0)

        top = QHBoxLayout()
        mark = QLabel("●")
        mark.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px;")
        word = QLabel("SENTINEL")
        word.setStyleSheet(
            f"color: {COLOR_TEXT}; font-weight: 900; font-size: 14px; letter-spacing: 0.32em;"
        )
        top.addWidget(mark)
        top.addWidget(word)
        top.addStretch()
        hl.addLayout(top)
        hl.addStretch(2)

        kicker = QLabel("PHARMACY OPERATIONS")
        kicker.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 11px; font-weight: 800; letter-spacing: 0.28em;"
        )
        headline = QLabel("Station locked.")
        headline.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: 48px; font-weight: 800; letter-spacing: -1.5px; padding-top: 14px;"
        )
        blurb = QLabel(
            "Authenticate to open a live register session.\n"
            "All sales, stock, and Z-reports bind to this operator."
        )
        blurb.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 14px; line-height: 150%; padding-top: 16px;"
        )
        blurb.setWordWrap(True)

        hl.addWidget(kicker)
        hl.addWidget(headline)
        hl.addWidget(blurb)
        hl.addStretch(3)

        foot = QLabel("DEV-001  ·  OFFLINE FIRST  ·  LEDGER INTEGRITY")
        foot.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 0.16em;"
        )
        hl.addWidget(foot)

        root.addWidget(hero, 5)

        # ── right: pin ────────────────────────────────────────────────────
        pane = QFrame()
        pane.setStyleSheet(f"background: {COLOR_BG};")
        pl = QVBoxLayout(pane)
        pl.setContentsMargins(64, 0, 64, 0)
        pl.setAlignment(Qt.AlignVCenter)

        card = QFrame()
        card.setFixedWidth(380)
        card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 16px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(32, 36, 32, 32)
        cl.setSpacing(8)

        st = QLabel("OPERATOR PIN")
        st.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 800; letter-spacing: 0.22em;"
        )
        sub = QLabel("Four-digit station credential")
        sub.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 13px; padding-bottom: 12px;")

        self.pin_in = QLineEdit()
        self.pin_in.setEchoMode(QLineEdit.Password)
        self.pin_in.setAlignment(Qt.AlignCenter)
        self.pin_in.setMaxLength(8)
        self.pin_in.setPlaceholderText("••••")
        self.pin_in.setStyleSheet(f"""
            QLineEdit {{
                background: #0B0D10;
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
                font-size: 28px;
                font-weight: 700;
                letter-spacing: 0.4em;
                padding: 16px 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {COLOR_ACCENT}; }}
        """)

        self.err = QLabel("")
        self.err.setAlignment(Qt.AlignCenter)
        self.err.setStyleSheet("color: #E07A5F; font-size: 11px; font-weight: 600; min-height: 16px;")

        self.btn = IndustrialButton("INITIATE SESSION")
        self._btn_style = self.btn.styleSheet()
        self._err_style = self.err.styleSheet()
        self._busy = False
        self._lock_remaining = 0
        self._lock_timer = QTimer(self)
        self._lock_timer.setInterval(1000)
        self._lock_timer.timeout.connect(self._tick_lock)
        if self._remaining_lock_seconds() > 0:
            QTimer.singleShot(0, self._show_lock_countdown)
        self.btn.clicked.connect(self.attempt_login)
        self.pin_in.returnPressed.connect(self.attempt_login)

        cl.addWidget(st)
        cl.addWidget(sub)
        cl.addWidget(self.pin_in)
        cl.addWidget(self.err)
        cl.addSpacing(8)
        cl.addWidget(self.btn)

        wrap = QHBoxLayout()
        wrap.addStretch()
        wrap.addWidget(card)
        wrap.addStretch()
        pl.addLayout(wrap)

        hint = QLabel("Enter  ·  confirm")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; letter-spacing: 0.18em; padding-top: 18px;"
        )
        pl.addWidget(hint)

        root.addWidget(pane, 4)
        self.pin_in.setFocus()

    def attempt_login(self):
        """Start PIN verification off the UI thread (UX-002)."""
        if self._busy:
            return
        if self._remaining_lock_seconds() > 0:
            self._show_lock_countdown()
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
