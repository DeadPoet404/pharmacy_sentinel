import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase
from sentinel.security.auth import verify_pin

class ShadcnLightLogin(QWidget):
    def __init__(self, db_manager, on_login_success):
        super().__init__()
        self.db = db_manager
        self.on_success = on_login_success
        
        self.setWindowTitle("Sentinel")
        self.setFixedSize(1200, 800)
        
        # Shadcn Zinc Light Palette
        self.bg_color = "#ffffff"       # White
        self.border_color = "#e4e4e7"   # Zinc 200
        self.text_primary = "#09090b"   # Zinc 950
        self.text_muted = "#71717a"     # Zinc 500
        self.input_bg = "#ffffff"
        self.primary = "#18181b"        # Zinc 900 (Black)
        self.primary_foreground = "#fafafa" # Zinc 50 (Off-white)
        self.badge_bg = "#f4f4f5"       # Zinc 100
        
        self.setStyleSheet(f"background-color: {self.bg_color};")

        # Main Layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setAlignment(Qt.AlignCenter)

        # The Login "Card" 
        self.card = QFrame()
        self.card.setFixedWidth(380)
        self.card.setStyleSheet(f"""
            QFrame {{
                background-color: {self.bg_color};
                border: 1px solid {self.border_color};
                border-radius: 8px;
            }}
        """)
        
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(32, 40, 32, 40)
        self.card_layout.setSpacing(8)

        # 1. Header
        self.title_label = QLabel("Unlock Station")
        self.title_label.setStyleSheet(f"""
            color: {self.text_primary};
            font-size: 20px;
            font-weight: 600;
            border: none;
            background: transparent;
        """)
        self.title_label.setAlignment(Qt.AlignCenter)

        self.subtitle_label = QLabel("Enter your PIN to resume operation.")
        self.subtitle_label.setStyleSheet(f"""
            color: {self.text_muted};
            font-size: 13px;
            border: none;
            background: transparent;
        """)
        self.subtitle_label.setAlignment(Qt.AlignCenter)

        # 2. Status Badge (Shadcn Light Badge)
        self.status_label = QLabel("System: Verifying Integrity")
        self.status_label.setFixedWidth(180)
        self.status_label.setFixedHeight(22)
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet(f"""
            color: {self.text_primary};
            font-size: 11px;
            font-weight: 500;
            background-color: {self.badge_bg};
            border: 1px solid {self.border_color};
            border-radius: 11px;
            margin-top: 8px;
        """)

        # 3. Input Section
        self.input_container = QWidget()
        self.input_container.setStyleSheet("border: none; background: transparent;")
        self.input_layout = QVBoxLayout(self.input_container)
        self.input_layout.setContentsMargins(0, 20, 0, 0)
        self.input_layout.setSpacing(12)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("••••••")
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setMaxLength(6)
        self.pin_input.setFixedHeight(40)
        self.pin_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {self.input_bg};
                border: 1px solid {self.border_color};
                border-radius: 6px;
                color: {self.text_primary};
                font-size: 16px;
                letter-spacing: 4px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.text_muted};
            }}
        """)
        self.pin_input.setVisible(False)
        self.pin_input.returnPressed.connect(self.attempt_login)

        self.unlock_btn = QPushButton("Continue")
        self.unlock_btn.setFixedHeight(40)
        self.unlock_btn.setCursor(Qt.PointingHandCursor)
        self.unlock_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.primary};
                color: {self.primary_foreground};
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: #27272a;
            }}
            QPushButton:pressed {{
                background-color: #3f3f46;
            }}
        """)
        self.unlock_btn.setVisible(False)
        self.unlock_btn.clicked.connect(self.attempt_login)

        # Assemble
        self.card_layout.addWidget(self.title_label)
        self.card_layout.addWidget(self.subtitle_label)
        self.card_layout.addWidget(self.status_label, 0, Qt.AlignCenter)
        
        self.input_layout.addWidget(self.pin_input)
        self.input_layout.addWidget(self.unlock_btn)
        self.card_layout.addWidget(self.input_container)

        self.main_layout.addWidget(self.card)
        
        # Logic Timer
        QTimer.singleShot(1500, self.run_integrity_check)

    def run_integrity_check(self):
        try:
            cursor = self.db.conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            if cursor.fetchone()[0] == "ok":
                self.status_label.setVisible(False)
                self.pin_input.setVisible(True)
                self.unlock_btn.setVisible(True)
                self.pin_input.setFocus()
        except:
            self.status_label.setText("Integrity Failed")
            self.status_label.setStyleSheet("color: #ef4444; border: 1px solid #fecaca; background: #fef2f2; font-size: 11px;")

    def attempt_login(self):
        pin = self.pin_input.text()
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, display_name, pin_hash, pin_salt FROM users WHERE is_active = 1")
        users = cursor.fetchall()
        
        for user in users:
            if verify_pin(pin, user['pin_hash'], user['pin_salt']):
                self.on_success(user['id'], user['display_name'])
                return
        
        # Error state
        self.pin_input.setStyleSheet(self.pin_input.styleSheet().replace(self.border_color, "#ef4444"))
        QTimer.singleShot(500, lambda: self.pin_input.setStyleSheet(self.pin_input.styleSheet().replace("#ef4444", self.border_color)))
        self.pin_input.clear()

if __name__ == "__main__":
    from sentinel.db.manager import DatabaseManager
    from sentinel.security.auth import hash_pin
    import uuid
    
    app = QApplication(sys.argv)
    
    # Set modern system font
    font = QFont("Segoe UI", 10)
    if sys.platform == "linux":
        font = QFont("Inter", 10)
    app.setFont(font)
    
    db = DatabaseManager("ui_test.db")
    db.connect()
    db.initialize()
    
    h, s = hash_pin("1234")
    db.conn.execute("INSERT OR IGNORE INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at) VALUES (?, 'admin', 'Test Owner', 'owner', ?, ?, 'now')", (str(uuid.uuid4()), h, s))
    db.conn.commit()
    
    def success(uid, name):
        print(f"✅ Access Granted: {name}")
        sys.exit(0)
        
    win = ShadcnLightLogin(db, success)
    win.show()
    sys.exit(app.exec())
