import sys
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLineEdit, 
                             QPushButton, QLabel, QFrame, QGridLayout)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor
from sentinel.security.auth import verify_pin

class BrutalistLogin(QWidget):
    def __init__(self, db_manager, on_login_success):
        super().__init__()
        self.db = db_manager
        self.on_success = on_login_success
        
        self.setWindowTitle("SENTINEL_SYSTEM_V1.0")
        self.setFixedSize(1000, 700)
        self.setStyleSheet("background-color: #e0e0e0;") # Industrial Gray

        # Main Layout (Centered Grid)
        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)

        # The Modular Console Card
        self.console = QFrame()
        self.console.setFixedSize(450, 550)
        self.console.setStyleSheet("""
            QFrame {
                background-color: #f4f4f4;
                border: 2px solid black;
            }
        """)
        
        self.c_layout = QVBoxLayout(self.console)
        self.c_layout.setContentsMargins(0, 0, 0, 0)
        self.c_layout.setSpacing(0)

        # Header Section (Top Bar)
        self.header = QLabel("AUTH_PROTOCOL_04")
        self.header.setFixedHeight(30)
        self.header.setStyleSheet("""
            background-color: black;
            color: #FF4500;
            font-family: monospace;
            font-weight: bold;
            padding-left: 10px;
        """)
        self.c_layout.addWidget(self.header)

        # Title Block
        self.title_block = QFrame()
        self.title_block.setFixedHeight(150)
        self.title_block.setStyleSheet("border-bottom: 2px solid black;")
        tb_layout = QVBoxLayout(self.title_block)
        
        self.main_title = QLabel("STATION_")
        self.main_title.setStyleSheet("font-size: 60px; font-weight: 900; color: black;")
        self.main_title.setAlignment(Qt.AlignCenter)
        
        self.sub_title = QLabel("ACCESS_LOCKED")
        self.sub_title.setStyleSheet("font-size: 20px; color: black; font-family: monospace;")
        self.sub_title.setAlignment(Qt.AlignCenter)
        
        tb_layout.addWidget(self.main_title)
        tb_layout.addWidget(self.sub_title)
        self.c_layout.addWidget(self.title_block)

        # Input Area
        self.input_area = QFrame()
        self.input_layout = QVBoxLayout(self.input_area)
        self.input_layout.setContentsMargins(40, 40, 40, 40)
        self.input_layout.setSpacing(20)

        self.status_msg = QLabel("RUNNING_INTEGRITY_CHECK...")
        self.status_msg.setStyleSheet("font-family: monospace; color: #666;")
        self.status_msg.setAlignment(Qt.AlignCenter)

        self.pin_input = QLineEdit()
        self.pin_input.setEchoMode(QLineEdit.Password)
        self.pin_input.setPlaceholderText("ENTER_PIN")
        self.pin_input.setAlignment(Qt.AlignCenter)
        self.pin_input.setFixedHeight(60)
        self.pin_input.setVisible(False)
        self.pin_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid black;
                background-color: white;
                font-size: 32px;
                color: black;
                font-family: monospace;
            }
        """)
        self.pin_input.returnPressed.connect(self.attempt_login)

        self.unlock_btn = QPushButton("UNLOCK_SYSTEM ➔")
        self.unlock_btn.setFixedHeight(50)
        self.unlock_btn.setVisible(False)
        self.unlock_btn.setCursor(Qt.PointingHandCursor)
        self.unlock_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF4500;
                color: black;
                border: 2px solid black;
                font-weight: bold;
                font-size: 16px;
                font-family: monospace;
            }
            QPushButton:hover { background-color: #e63e00; }
        """)
        self.unlock_btn.clicked.connect(self.attempt_login)

        self.input_layout.addWidget(self.status_msg)
        self.input_layout.addWidget(self.pin_input)
        self.input_layout.addWidget(self.unlock_btn)
        self.c_layout.addWidget(self.input_area)

        # Bottom Sub-Grid (Metrics/Decoration)
        self.bottom_grid = QFrame()
        self.bottom_grid.setFixedHeight(60)
        self.bottom_grid.setStyleSheet("border-top: 2px solid black;")
        bg_layout = QGridLayout(self.bottom_grid)
        bg_layout.setContentsMargins(0,0,0,0)
        bg_layout.setSpacing(0)
        
        for i, txt in enumerate(["V.1.0", "SYS_STABLE", "LEDGER_OK"]):
            lbl = QLabel(txt)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("border-right: 1px solid black; font-family: monospace; font-size: 10px;")
            bg_layout.addWidget(lbl, 0, i)

        self.c_layout.addWidget(self.bottom_grid)
        self.layout.addWidget(self.console)
        
        QTimer.singleShot(1500, self.run_check)

    def run_check(self):
        self.status_msg.setText("GOVERNANCE_ACTIVE")
        self.pin_input.setVisible(True)
        self.unlock_btn.setVisible(True)
        self.pin_input.setFocus()

    def attempt_login(self):
        pin = self.pin_input.text()
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, display_name, pin_hash, pin_salt FROM users WHERE is_active = 1")
        users = cursor.fetchall()
        for user in users:
            if verify_pin(pin, user['pin_hash'], user['pin_salt']):
                self.on_success(user['id'], user['display_name'])
                return
        self.pin_input.clear()
        self.main_title.setText("ERROR_")
        QTimer.singleShot(1000, lambda: self.main_title.setText("STATION_"))

if __name__ == "__main__":
    from sentinel.db.manager import DatabaseManager
    from sentinel.security.auth import hash_pin
    import uuid
    app = QApplication(sys.argv)
    db = DatabaseManager("ui_test.db"); db.connect(); db.initialize()
    h, s = hash_pin("1234")
    db.conn.execute("INSERT OR IGNORE INTO users (uuid, username, display_name, role, pin_hash, pin_salt, created_at) VALUES (?, 'admin', 'OWNER', 'owner', ?, ?, 'now')", (str(uuid.uuid4()), h, s))
    db.conn.commit()
    win = BrutalistLogin(db, lambda uid, name: sys.exit(0))
    win.show()
    sys.exit(app.exec())
