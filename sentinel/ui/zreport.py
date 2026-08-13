import sys
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QFrame, 
                             QPushButton, QProgressBar, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from sentinel.logic.backup import BackupEngine
from sentinel.logic.sessions import SessionManager

class ZReportCeremony(QWidget):
    def __init__(self, db_manager, session_id, user_id, device_id):
        super().__init__()
        self.db = db_manager
        self.session_id = session_id
        self.user_id = user_id
        
        # For simplicity, we use a fixed master key for Phase 1
        self.master_key = "SENTINEL-MASTER-KEY-12345"
        self.backup_eng = BackupEngine("sentinel.db", self.master_key)
        self.sess_mgr = SessionManager(db_manager, device_id)

        self.setWindowTitle("Z_REPORT_CEREMONY")
        self.setFixedSize(500, 400)
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        layout = QVBoxLayout(self)
        
        self.header = QLabel("➔ END_OF_DAY_GOVERNANCE")
        self.header.setStyleSheet("background-color: black; color: #FF4500; padding: 5px; font-weight: bold;")
        layout.addWidget(self.header)

        self.console = QFrame()
        self.console.setStyleSheet("border: 2px solid black; background: #f4f4f4;")
        c_layout = QVBoxLayout(self.console)
        
        self.status = QLabel("WAITING_FOR_USB_ENCRYPTION...")
        self.status.setStyleSheet("font-weight: bold; font-size: 14px;")
        c_layout.addWidget(self.status)
        
        self.progress = QProgressBar()
        self.progress.setStyleSheet("""
            QProgressBar { border: 2px solid black; background: #ddd; height: 30px; text-align: center; }
            QProgressBar::chunk { background-color: #FF4500; }
        """)
        c_layout.addWidget(self.progress)
        
        layout.addWidget(self.console)

        self.run_btn = QPushButton("INITIATE_BACKUP_AND_CLOSE ➔")
        self.run_btn.setFixedHeight(60)
        self.run_btn.setStyleSheet("background-color: #FF4500; border: 2px solid black; font-weight: bold;")
        self.run_btn.clicked.connect(self.start_ceremony)
        layout.addWidget(self.run_btn)

    def start_ceremony(self):
        self.run_btn.setEnabled(False)
        self.status.setText("GENERATING_ENCRYPTED_ARCHIVE...")
        self.progress.setValue(30)
        
        # Run backup logic
        QTimer.singleShot(1000, self.do_backup)

    def do_backup(self):
        try:
            # Simulate USB path (on Linux, we'll just use a local folder)
            backup_dir = os.path.expanduser("~/SentinelBackups")
            os.makedirs(backup_dir, exist_ok=True)
            
            backup_name = f"sentinel_backup_{self.session_id}"
            dest = os.path.join(backup_dir, backup_name)
            
            # 1. Create and Encrypt
            sha256, final_path = self.backup_eng.create_encrypted_backup(dest)
            self.progress.setValue(70)
            
            # 2. Verify and Record Z-Report
            z_id = self.sess_mgr.generate_z_report(self.session_id, self.user_id, final_path, sha256)
            self.progress.setValue(90)
            
            # 3. Close the Session
            self.sess_mgr.close_session(self.session_id, self.user_id)
            self.progress.setValue(100)
            
            QMessageBox.information(self, "SUCCESS", f"DAY_CLOSED.\nARCHIVE_LOCATION: {final_path}")
            sys.exit(0) # Terminate app after Z-Report
            
        except Exception as e:
            QMessageBox.critical(self, "BACKUP_FAILED", str(e))
            self.run_btn.setEnabled(True)
