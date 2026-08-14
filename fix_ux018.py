#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-018 — Keyboard-first cart entry.

Changes sentinel/ui/pos.py only:
  1. SearchLineEdit subclass — Up/Down arrows move the results selection
     while the search box keeps focus.
  2. Enter in the search box adds the selected result (or top match),
     clears the box, and keeps focus there for the next item.
  3. Search box auto-focuses when the POS window opens.
  4. Enter on a focused results row also activates it (itemActivated).
  5. On-screen hints updated to teach the keyboard flow.

Safety: aborts before writing if any anchor is missing/ambiguous,
writes atomically via os.replace. Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

SEARCH_LINEEDIT_CLASS = '''class SearchLineEdit(QLineEdit):
    """Search input that keeps focus while the POS navigates results with arrows."""

    up_pressed = Signal()
    down_pressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.up_pressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key_Down:
            self.down_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


'''

SELECTION_METHODS = '''

    def _move_search_selection(self, delta):
        """Arrow-key navigation over the results list while typing continues."""
        rows = self.search_table.rowCount()
        if rows == 0:
            return
        cur = self.search_table.currentRow()
        if cur < 0:
            new_row = 0 if delta > 0 else rows - 1
        else:
            new_row = max(0, min(rows - 1, cur + delta))
        self.search_table.selectRow(new_row)
        self.search_table.scrollToItem(self.search_table.item(new_row, 0))

    def _search_return_pressed(self):
        """Enter adds the selected result (or top match), clears and refocuses.

        Signals are blocked while clearing so we do not re-query the whole
        catalog after every add — the list stays put until the operator types
        the next item.
        """
        txt = self.search_box.text().strip()
        if not txt:
            return
        rows = self.search_table.rowCount()
        if rows == 0:
            return
        r = self.search_table.currentRow()
        if r < 0 or r >= rows:
            r = 0
        it = self.search_table.item(r, 0)
        if it is None:
            return
        self.select_item(it)
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self.search_box.setFocus()'''

# Each entry: (label, exact_old, new)  — old must occur exactly once.
EDITS = [
    (
        "QtCore import gains QTimer + Signal",
        "from PySide6.QtCore import Qt",
        "from PySide6.QtCore import Qt, QTimer, Signal",
    ),
    (
        "SearchLineEdit class inserted before BrutalistPOS",
        "class BrutalistPOS(QWidget):",
        SEARCH_LINEEDIT_CLASS + "class BrutalistPOS(QWidget):",
    ),
    (
        "search_box becomes SearchLineEdit",
        "        self.search_box = QLineEdit()",
        "        self.search_box = SearchLineEdit()",
    ),
    (
        "Enter / arrow connections wired",
        "        self.search_box.textChanged.connect(self.run_search)",
        "        self.search_box.textChanged.connect(self.run_search)\n"
        "        self.search_box.returnPressed.connect(self._search_return_pressed)\n"
        "        self.search_box.down_pressed.connect(lambda: self._move_search_selection(1))\n"
        "        self.search_box.up_pressed.connect(lambda: self._move_search_selection(-1))",
    ),
    (
        "search hint teaches the keyboard flow",
        '        hint = QLabel("  F2  SEARCH CATALOG")',
        '        hint = QLabel("  F2  SEARCH  ·  TYPE  ·  ↑↓ PICK  ·  ↵ ADD")',
    ),
    (
        "Enter activates a focused results row",
        "        self.search_table.itemDoubleClicked.connect(self.select_item)",
        "        self.search_table.itemDoubleClicked.connect(self.select_item)\n"
        "        self.search_table.itemActivated.connect(self.select_item)",
    ),
    (
        "empty-ledger hint updated",
        '        self.cart_empty = QLabel("Empty  ·  double-click a match to add  ·  Del removes  ·  +/− qty")',
        '        self.cart_empty = QLabel("Empty  ·  type to search, ↵ adds top match  ·  ↑↓ pick  ·  Del removes  ·  +/− qty")',
    ),
    (
        "selection/enter handler methods appended after _fill_search",
        "        self.search_empty.setVisible(self.search_table.rowCount() == 0)",
        "        self.search_empty.setVisible(self.search_table.rowCount() == 0)"
        + SELECTION_METHODS,
    ),
    (
        "auto-focus search box when POS opens",
        "        self.setup_shortcuts()\n        self.run_search()",
        "        self.setup_shortcuts()\n        self.run_search()\n"
        "        QTimer.singleShot(0, self.search_box.setFocus)",
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

    tmp = TARGET + ".ux018.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
