#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-014 — Cart undo (Ctrl+Z) + formatted line totals.

Changes sentinel/ui/pos.py only:

  1. Ctrl+Z (or Cmd+Z) restores the cart to its state before the last
     destructive edit (removing a line, or nudging a quantity down to
     zero). Snapshot stack capped at 20, cleared after a committed
     sale. An "UNDONE" toast confirms the restore.
  2. Ctrl+Z is handled in keyPressEvent — so when the search box has
     focus it keeps QLineEdit's built-in text undo instead of being
     hijacked.
  3. Line totals now render with thousand separators (2,000.00),
     matching the AMOUNT DUE display.
  4. The empty-ledger hint teaches the new shortcut.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

UNDO_METHODS = '''
    def _push_undo(self):
        """Snapshot the cart before a destructive edit (UX-014)."""
        self._undo_stack.append([dict(i) for i in self.cart_items])
        if len(self._undo_stack) > 20:
            self._undo_stack.pop(0)

    def undo_last(self):
        """Ctrl+Z restores the cart to the last snapshot."""
        if not self._undo_stack:
            return
        self.cart_items = [dict(i) for i in self._undo_stack.pop()]
        self.update_ledger()
        if hasattr(self, "toast"):
            self.toast.show_message("UNDONE", "info", duration_ms=1200)
'''

EDITS = [
    (
        "undo stack initialized",
        "        self._debounce.timeout.connect(self.run_search)",
        "        self._debounce.timeout.connect(self.run_search)\n"
        "        self._undo_stack = []",
    ),
    (
        "undo methods inserted before open_zreport",
        "    def open_zreport(self):",
        UNDO_METHODS + "    def open_zreport(self):",
    ),
    (
        "remove_cart_line snapshots before deleting",
        """    def remove_cart_line(self, *args):
        r = self._selected_cart_row()
        if r is None:
            return
        del self.cart_items[r]
        self.update_ledger()""",
        """    def remove_cart_line(self, *args):
        r = self._selected_cart_row()
        if r is None:
            return
        self._push_undo()
        del self.cart_items[r]
        self.update_ledger()""",
    ),
    (
        "nudge-to-zero snapshots before deleting",
        """        q = self.cart_items[r].get("qty", 1) + delta
        if q <= 0:
            del self.cart_items[r]
        else:""",
        """        q = self.cart_items[r].get("qty", 1) + delta
        if q <= 0:
            self._push_undo()
            del self.cart_items[r]
        else:""",
    ),
    (
        "Ctrl+Z handled in keyPressEvent (search box keeps its own undo)",
        """        if self.search_box.hasFocus() and event.text().isalpha():
            return super().keyPressEvent(event)
        key = event.key()""",
        """        if self.search_box.hasFocus() and event.text().isalpha():
            return super().keyPressEvent(event)
        if not self.search_box.hasFocus() and event.matches(QKeySequence.Undo):
            self.undo_last()
            return
        key = event.key()""",
    ),
    (
        "line totals gain thousand separators",
        """            p = QTableWidgetItem(f"{i['price'] * i.get('qty', 1):.2f}")""",
        """            p = QTableWidgetItem(f"{i['price'] * i.get('qty', 1):,.2f}")""",
    ),
    (
        "undo stack cleared after a committed sale",
        """            self.cart_items = []
            self.update_ledger()
            self.run_search()
            self.search_box.setFocus()""",
        """            self.cart_items = []
            self._undo_stack.clear()
            self.update_ledger()
            self.run_search()
            self.search_box.setFocus()""",
    ),
    (
        "empty-ledger hint teaches Ctrl+Z",
        '        self.cart_empty = QLabel("Empty  ·  type to search, ↵ adds top match  ·  ↑↓ pick  ·  Del removes  ·  +/− qty")',
        '        self.cart_empty = QLabel("Empty  ·  type to search, ↵ adds top match  ·  ↑↓ pick  ·  Del removes  ·  +/− qty  ·  Ctrl+Z undo")',
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

    tmp = TARGET + ".ux014.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
