import sys
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar, QMessageBox,
)
from PySide6.QtCore import Qt, QThread, QObject, Signal
from sentinel.logic.backup import BackupEngine
from sentinel.logic.sessions import SessionManager
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, SectionLabel,
    COLOR_ACCENT, COLOR_DIM, COLOR_TEXT, COLOR_MUTED,
    COLOR_SURFACE, COLOR_BORDER, COLOR_BG,
)


class _CeremonyWorker(QObject):
    """Runs the encrypted-backup + verification off the UI thread."""

    progress = Signal(int)
    status = Signal(str)
    ok = Signal(str, str)
    bad = Signal(str)
    done = Signal()

    def __init__(self, master_key, session_id):
        super().__init__()
        self._master_key = master_key
        self._session_id = session_id

    def run(self):
        try:
            self.status.emit("GENERATING ENCRYPTED ARCHIVE…")
            self.progress.emit(30)
            backup_dir = os.path.expanduser("~/SentinelBackups")
            os.makedirs(backup_dir, exist_ok=True)
            backup_name = f"sentinel_backup_{self._session_id}"
            dest = os.path.join(backup_dir, backup_name)
            engine = BackupEngine("sentinel.db", self._master_key)
            sha256, final_path = engine.create_encrypted_backup(dest)
            self.progress.emit(60)
            self.status.emit("VERIFYING ARCHIVE…")
            if not engine.verify_backup(final_path, sha256):
                raise RuntimeError("Backup hash mismatch — session left OPEN.")
            self.progress.emit(70)
            self.ok.emit(sha256, final_path)
        except Exception as e:
            self.bad.emit(str(e))
        self.done.emit()


class ZReportCeremony(QWidget):
    def __init__(self, db_manager, session_id, user_id, device_id):
        super().__init__()
        self.db = db_manager
        self.session_id = session_id
        self.user_id = user_id

        self.master_key = "SENTINEL-MASTER-KEY-12345"
        self.backup_eng = BackupEngine("sentinel.db", self.master_key)
        self.sess_mgr = SessionManager(db_manager, device_id)

        self.setWindowTitle("End of day")
        self.setFixedSize(520, 480)
        self.setStyleSheet(GLOBAL_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background: #0E1116; border-bottom: 1px solid {COLOR_BORDER};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(22, 0, 22, 0)
        mark = QLabel("●")
        mark.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px;")
        title = QLabel("Z-REPORT  ·  GOVERNANCE")
        title.setStyleSheet(
            f"color: {COLOR_TEXT}; font-weight: 800; font-size: 12px; letter-spacing: 0.2em;"
        )
        bl.addWidget(mark)
        bl.addWidget(title)
        bl.addStretch()
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 24)
        body.setSpacing(14)

        body.addWidget(SectionLabel("End of day close"))

        intro = QLabel(
            "Encrypt the ledger, write a Z-report, then close this register session. "
            "The application will exit when the ceremony completes."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 13px;")
        body.addWidget(intro)

        meta = QFrame()
        meta.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        ml = QVBoxLayout(meta)
        ml.setContentsMargins(16, 14, 16, 14)
        ml.setSpacing(6)
        sess = QLabel(f"SESSION   {self.session_id}")
        sess.setStyleSheet(
            f"color: {COLOR_TEXT}; font-size: 12px; font-weight: 700; letter-spacing: 0.12em;"
        )
        dest = QLabel("ARCHIVE   ~/SentinelBackups")
        dest.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 11px; font-weight: 600; letter-spacing: 0.1em;"
        )
        ml.addWidget(sess)
        ml.addWidget(dest)
        body.addWidget(meta)

        console = QFrame()
        console.setStyleSheet(f"""
            QFrame {{
                background: #0B0D10;
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        cl = QVBoxLayout(console)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        self.status = QLabel("READY  ·  waiting to encrypt")
        self.status.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 700; letter-spacing: 0.1em;"
        )
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(10)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 5px;
            }}
            QProgressBar::chunk {{
                background: {COLOR_ACCENT};
                border-radius: 4px;
            }}
        """)
        cl.addWidget(self.status)
        cl.addWidget(self.progress)
        body.addWidget(console)

        body.addStretch()

        self.run_btn = IndustrialButton("INITIATE BACKUP AND CLOSE")
        self.run_btn.setFixedHeight(58)
        self.run_btn.clicked.connect(self.start_ceremony)
        body.addWidget(self.run_btn)

        wrap = QWidget()
        wrap.setLayout(body)
        wrap.setStyleSheet(f"background: {COLOR_BG};")
        root.addWidget(wrap, 1)

    def start_ceremony(self):
        if getattr(self, "_busy", False):
            return
        self._busy = True
        self._pending_success = None
        self.run_btn.setEnabled(False)
        self.status.setText("GENERATING ENCRYPTED ARCHIVE…")
        self.progress.setValue(30)

        self._thread = QThread(self)
        self._worker = _CeremonyWorker(self.master_key, self.session_id)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self.progress.setValue)
        self._worker.status.connect(self.status.setText)
        self._worker.ok.connect(self._on_ceremony_ok)
        self._worker.bad.connect(self._on_ceremony_bad)
        self._worker.done.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_ceremony_ok(self, sha256, final_path):
        """Heavy work done off-thread; fast DB writes stay on the UI thread."""
        self.progress.setValue(80)
        self.status.setText("WRITING Z-REPORT…")
        self.sess_mgr.generate_z_report(self.session_id, self.user_id, final_path, sha256)
        self.progress.setValue(90)
        self.status.setText("CLOSING SESSION…")
        self.sess_mgr.close_session(self.session_id, self.user_id)
        self.progress.setValue(100)
        self.status.setText("DAY CLOSED")
        self._pending_success = final_path

    def _on_thread_finished(self):
        """Exit only after the worker thread has fully stopped (avoids
        Qt aborting on a destroyed-but-running QThread)."""
        if self._pending_success:
            self._busy = False
            QMessageBox.information(
                self, "SUCCESS", f"Day closed.\nArchive:\n{self._pending_success}"
            )
            sys.exit(0)

    def _on_ceremony_bad(self, message):
        self._busy = False
        QMessageBox.critical(self, "BACKUP FAILED", message)
        self.run_btn.setEnabled(True)
        self.status.setText("FAILED  ·  retry when ready")
        self.progress.setValue(0)
