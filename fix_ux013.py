#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-013 — Dialogs resizable with scrollable bodies.

Changes five files:
  sentinel/ui/checkout.py, purchasing.py, registry.py, zreport.py
    - setFixedSize replaced with setMinimumSize + a sensible resize():
      windows can now grow (and stay usable on large/High-DPI displays).
    - Each dialog body is wrapped in a QScrollArea, so on displays
      smaller than the minimum size the content SCROLLS instead of
      clipping (window chrome stays reachable).
  sentinel/ui/login.py
    - The PinChangeDialog (UX-012) gets the same treatment.

No visual changes at default sizes — the layout renders identically at
the original dimensions.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; all five files validated before any write;
atomic writes via os.replace.
Rollback: git checkout -- sentinel/ui/checkout.py sentinel/ui/purchasing.py sentinel/ui/registry.py sentinel/ui/zreport.py sentinel/ui/login.py
"""
import os
import sys

SCROLL_BLOCK = """        wrap.setMinimumSize(wrap.sizeHint())
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(wrap)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        root.addWidget(scroll, 1)"""

FILES = [
    ("sentinel/ui/checkout.py", [
        (
            "QScrollArea imported",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QFormLayout, QMessageBox, QGraphicsDropShadowEffect,
)""",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QFormLayout, QMessageBox, QGraphicsDropShadowEffect,
    QScrollArea,
)""",
        ),
        (
            "fixed size becomes minimum + resize",
            "        self.setFixedSize(440, 560)",
            "        self.setMinimumSize(440, 560)\n        self.resize(460, 600)",
        ),
        (
            "body wrapped in a scroll area",
            """        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)""",
            """        wrap = QWidget()
        wrap.setLayout(body)
""" + SCROLL_BLOCK,
        ),
    ]),
    ("sentinel/ui/purchasing.py", [
        (
            "QScrollArea imported",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QPushButton, QComboBox, QFormLayout, QMessageBox,
)""",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QPushButton, QComboBox, QFormLayout, QMessageBox,
    QScrollArea,
)""",
        ),
        (
            "fixed size becomes minimum + resize",
            "        self.setFixedSize(520, 640)",
            "        self.setMinimumSize(520, 640)\n        self.resize(540, 680)",
        ),
        (
            "body wrapped in a scroll area",
            """        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)""",
            """        wrap = QWidget()
        wrap.setLayout(body)
""" + SCROLL_BLOCK,
        ),
    ]),
    ("sentinel/ui/registry.py", [
        (
            "QScrollArea imported",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QComboBox, QFormLayout, QTableWidgetItem,
)""",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QComboBox, QFormLayout, QTableWidgetItem,
    QScrollArea,
)""",
        ),
        (
            "fixed size becomes minimum + resize",
            "        self.setFixedSize(1040, 720)",
            "        self.setMinimumSize(1040, 720)\n        self.resize(1100, 780)",
        ),
        (
            "body wrapped in a scroll area",
            """        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)""",
            """        wrap = QWidget()
        wrap.setLayout(body)
""" + SCROLL_BLOCK,
        ),
    ]),
    ("sentinel/ui/zreport.py", [
        (
            "QScrollArea imported",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar, QMessageBox,
)""",
            """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QProgressBar, QMessageBox,
    QScrollArea,
)""",
        ),
        (
            "fixed size becomes minimum + resize",
            "        self.setFixedSize(520, 480)",
            "        self.setMinimumSize(520, 480)\n        self.resize(540, 520)",
        ),
        (
            "body wrapped in a scroll area",
            """        wrap = QWidget()
        wrap.setLayout(body)
        wrap.setStyleSheet(f"background: {COLOR_BG};")
        root.addWidget(wrap, 1)""",
            """        wrap = QWidget()
        wrap.setLayout(body)
        wrap.setStyleSheet(f"background: {COLOR_BG};")
""" + SCROLL_BLOCK,
        ),
    ]),
    ("sentinel/ui/login.py", [
        (
            "PinChangeDialog fixed size becomes minimum",
            "        self.setFixedSize(440, 460)",
            "        self.setMinimumSize(440, 460)",
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
        tmp = path + ".ux013.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    print("[DONE] Patch applied.")
    print("Next: python3 -m compileall -q sentinel")


if __name__ == "__main__":
    main()
