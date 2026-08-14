from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, COLOR_ACCENT, COLOR_DIM,
    COLOR_TEXT, COLOR_MUTED, COLOR_BORDER, COLOR_SURFACE, COLOR_BG,
)
from sentinel.security.auth import verify_pin


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
