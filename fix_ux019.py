#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-019 — Auto-dismissing toast replaces success modals.

Changes three files:
  sentinel/ui/components.py
    - New Toast widget: auto-dismissing overlay, bottom-center of its
      parent, mouse-transparent, kinds: success / error / info.
  sentinel/ui/pos.py
    - "Sale committed." modal -> toast with the change amount.
    - "EMPTY LEDGER" modal -> error toast (no click to dismiss).
    - Stock-ingest completion toast appears on the POS window after the
      ingest window closes.
  sentinel/ui/purchasing.py
    - "Stock ingested." modal removed; the POS notifies via on_complete.

Z-Report success modal is intentionally kept: it shows the archive path
and the app exits right after, so it must stay readable.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; all files validated before any write; atomic
writes via os.replace.
Rollback: git checkout -- sentinel/ui/components.py sentinel/ui/pos.py sentinel/ui/purchasing.py
"""
import os
import sys

TOAST_CLASS = '''class Toast(QFrame):
    """Auto-dismissing overlay notification — replaces success modals.

    Usage: toast.show_message("TEXT", kind="success"|"error"|"info",
                              duration_ms=1600)
    Positions itself bottom-center of its parent and hides automatically.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 10, 18, 10)
        self.label = QLabel("")
        lay.addWidget(self.label)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text, kind="success", duration_ms=1600):
        color = {
            "success": COLOR_OK,
            "error": COLOR_DANGER,
            "info": COLOR_ACCENT,
        }.get(kind, COLOR_ACCENT)
        self.label.setText(text)
        self.label.setStyleSheet(
            f"background: transparent; color: {color}; font-size: 13px; "
            "font-weight: 800; letter-spacing: 0.12em;"
        )
        self.setStyleSheet(
            f"QFrame#Toast {{ background: {COLOR_SURFACE_2}; "
            f"border: 1px solid {color}; border-radius: 10px; }}"
        )
        self.adjustSize()
        self._reposition()
        self.raise_()
        self.show()
        self._timer.start(duration_ms)

    def _reposition(self):
        p = self.parentWidget()
        if p is None:
            return
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 28)
'''

FILES = [
    ("sentinel/ui/components.py", [
        (
            "components imports gain QHBoxLayout + QTimer",
            "from PySide6.QtWidgets import QPushButton, QLabel, QFrame\nfrom PySide6.QtCore import Qt",
            "from PySide6.QtWidgets import QPushButton, QLabel, QFrame, QHBoxLayout\nfrom PySide6.QtCore import Qt, QTimer",
        ),
        (
            "Toast class appended at the end of the UI kit",
            """        if title:
            self.setToolTip(str(title))""",
            """        if title:
            self.setToolTip(str(title))
""" + TOAST_CLASS.rstrip() + "\n",
        ),
    ]),
    ("sentinel/ui/pos.py", [
        (
            "Toast imported from the UI kit",
            """    COLOR_TEXT, COLOR_BG, apply_deep_elevation,
)""",
            """    COLOR_TEXT, COLOR_BG, apply_deep_elevation,
    Toast,
)""",
        ),
        (
            "Toast instance created in __init__",
            """        self.setup_shortcuts()
        self.run_search()
        QTimer.singleShot(0, self.search_box.setFocus)""",
            """        self.setup_shortcuts()
        self.run_search()
        QTimer.singleShot(0, self.search_box.setFocus)
        self.toast = Toast(self)""",
        ),
        (
            "ingest completion notifies on the POS window",
            """    def open_ingest(self):
        self.ingest = BatchIngest(self.db, "DEV-001", on_complete=self.run_search)
        self.ingest.show()""",
            """    def open_ingest(self):
        def _done():
            self.run_search()
            self.toast.show_message("STOCK INGESTED", "success")

        self.ingest = BatchIngest(self.db, "DEV-001", on_complete=_done)
        self.ingest.show()""",
        ),
        (
            "empty-ledger modal becomes an error toast",
            """        if not self.cart_items:
            QMessageBox.information(self, "EMPTY LEDGER", "Add at least one line before settlement.")
            return""",
            """        if not self.cart_items:
            self.toast.show_message("LEDGER EMPTY  ·  ADD A LINE FIRST", "error")
            return""",
        ),
        (
            "sale success modal becomes a toast with the change amount",
            """            QMessageBox.information(self, "SUCCESS", "Sale committed.")
            self.cart_items = []""",
            """            change = tendered - float(self.total_lbl.text().replace(",", "") or 0)
            self.toast.show_message(f"SALE COMMITTED  ·  CHANGE {change:,.2f}", "success")
            self.cart_items = []""",
        ),
    ]),
    ("sentinel/ui/purchasing.py", [
        (
            "ingest success modal removed (POS notifies via on_complete)",
            """            self.db.conn.commit()
            QMessageBox.information(self, "SUCCESS", "Stock ingested.")
            self.close()
            if self.on_complete:
                self.on_complete()""",
            """            self.db.conn.commit()
            self.close()
            if self.on_complete:
                self.on_complete()""",
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
        tmp = path + ".ux019.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    print("[DONE] Patch applied.")
    print("Next: python3 -m py_compile sentinel/ui/components.py sentinel/ui/pos.py sentinel/ui/purchasing.py")


if __name__ == "__main__":
    main()
