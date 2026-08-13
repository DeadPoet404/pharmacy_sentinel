import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLineEdit, QLabel, QFrame)
from PySide6.QtCore import Qt
from sentinel.ui.components import GLOBAL_STYLE, IndustrialButton, COLOR_SIDEBAR, TechnicalCard
from sentinel.security.auth import verify_pin

class SaaSLogin(QWidget):
    def __init__(self, db_manager, on_login_success):
        super().__init__()
        self.db, self.on_success = db_manager, on_login_success
        self.setWindowTitle("SENTINEL_AUTH")
        self.setFixedSize(1280, 800)
        self.setStyleSheet(GLOBAL_STYLE)
        
        l = QVBoxLayout(self); l.setAlignment(Qt.AlignCenter)
        
        card = TechnicalCard(); card.setFixedSize(350, 450)
        cl = QVBoxLayout(card); cl.setContentsMargins(30, 40, 30, 40); cl.setSpacing(15)
        
        logo = QLabel("🛡️"); logo.setStyleSheet("font-size: 40px; border: none;"); logo.setAlignment(Qt.AlignCenter)
        title = QLabel("STATION_LOCKED"); title.setStyleSheet("font-weight: 900; font-size: 18px; border: none;"); title.setAlignment(Qt.AlignCenter)
        
        cl.addWidget(logo); cl.addWidget(title); cl.addSpacing(20)
        
        cl.addWidget(QLabel("INPUT_PIN", styleSheet="font-weight: 900; font-size: 10px; border: none;"))
        self.pin_in = QLineEdit(); self.pin_in.setEchoMode(QLineEdit.Password)
        cl.addWidget(self.pin_in)
        
        self.btn = IndustrialButton("Initiate_Session")
        self.btn.clicked.connect(self.attempt_login); self.pin_in.returnPressed.connect(self.attempt_login)
        cl.addWidget(self.btn)
        
        cl.addStretch(); l.addWidget(card); self.pin_in.setFocus()

    def attempt_login(self):
        pin = self.pin_in.text()
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, display_name, pin_hash, pin_salt FROM users WHERE is_active = 1")
        for u in cursor.fetchall():
            if verify_pin(pin, u[2], u[3]):
                self.on_success(u[0], u[1])
                return
        self.pin_in.clear()
