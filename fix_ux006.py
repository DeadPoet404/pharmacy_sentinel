#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-006 — Z-Report ceremony runs off the UI thread.

Changes sentinel/ui/zreport.py only:

  The backup snapshot + SHA-256 + AES-GCM encryption + verification now
  run in a _CeremonyWorker QThread with live progress/status signals.
  The window stays responsive during the whole ceremony (previously it
  froze at ~30% while the backup ran synchronously).

  Design note: the final Z-report write and session close stay on the
  UI thread — they are millisecond-fast DB writes and the app's shared
  SQLite connection is bound to the main thread (cross-thread use would
  raise sqlite3.ProgrammingError). The BackupEngine opens its own
  connections inside the worker, which is thread-safe.

  Exit is gated on thread.finished — exiting while the worker thread is
  still winding down makes Qt abort ("QThread: Destroyed while thread
  is still running").

  Button is disabled while the ceremony runs; double-start is guarded.
  Failure path re-enables the button, resets progress, and shows the
  reason (session remains OPEN, unchanged from before).

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/zreport.py
"""
import os
import sys

TARGET = "sentinel/ui/zreport.py"

WORKER_CLASS = '''class _CeremonyWorker(QObject):
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


'''

OLD_CEREMONY = '''    def start_ceremony(self):
        self.run_btn.setEnabled(False)
        self.status.setText("GENERATING ENCRYPTED ARCHIVE…")
        self.progress.setValue(30)
        QTimer.singleShot(1000, self.do_backup)

    def do_backup(self):
        try:
            backup_dir = os.path.expanduser("~/SentinelBackups")
            os.makedirs(backup_dir, exist_ok=True)

            backup_name = f"sentinel_backup_{self.session_id}"
            dest = os.path.join(backup_dir, backup_name)

            sha256, final_path = self.backup_eng.create_encrypted_backup(dest)
            self.progress.setValue(60)
            self.status.setText("VERIFYING ARCHIVE…")
            if not self.backup_eng.verify_backup(final_path, sha256):
                raise RuntimeError("Backup hash mismatch — session left OPEN.")
            self.progress.setValue(70)
            self.status.setText("WRITING Z-REPORT…")

            self.sess_mgr.generate_z_report(self.session_id, self.user_id, final_path, sha256)
            self.progress.setValue(90)
            self.status.setText("CLOSING SESSION…")

            self.sess_mgr.close_session(self.session_id, self.user_id)
            self.progress.setValue(100)
            self.status.setText("DAY CLOSED")

            QMessageBox.information(
                self, "SUCCESS", f"Day closed.\\nArchive:\\n{final_path}"
            )
            sys.exit(0)

        except Exception as e:
            QMessageBox.critical(self, "BACKUP FAILED", str(e))
            self.run_btn.setEnabled(True)
            self.status.setText("FAILED  ·  retry when ready")
            self.progress.setValue(0)
'''

NEW_CEREMONY = '''    def start_ceremony(self):
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
                self, "SUCCESS", f"Day closed.\\nArchive:\\n{self._pending_success}"
            )
            sys.exit(0)

    def _on_ceremony_bad(self, message):
        self._busy = False
        QMessageBox.critical(self, "BACKUP FAILED", message)
        self.run_btn.setEnabled(True)
        self.status.setText("FAILED  ·  retry when ready")
        self.progress.setValue(0)
'''

EDITS = [
    (
        "QtCore import gains QThread + QObject + Signal",
        "from PySide6.QtCore import Qt, QTimer",
        "from PySide6.QtCore import Qt, QThread, QObject, Signal",
    ),
    (
        "_CeremonyWorker class inserted before ZReportCeremony",
        "class ZReportCeremony(QWidget):",
        WORKER_CLASS + "class ZReportCeremony(QWidget):",
    ),
    (
        "ceremony methods replaced with off-thread version",
        OLD_CEREMONY,
        NEW_CEREMONY,
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

    tmp = TARGET + ".ux006.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
