#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-020 — Quantity fast-entry.

Changes sentinel/ui/pos.py only:
  1. CartTable subclass — forwards digits/Enter/Backspace/Esc key events
     from the cart table to the POS instead of letting Qt swallow them.
  2. F5 focuses the cart (selects the last line if none selected).
  3. With a cart line focused: type digits (up to 3) and press Enter to
     set that line's quantity; Backspace pops the last digit; Esc cancels.
  4. A status label next to the cart controls shows the pending quantity
     and teaches the gesture ("F5 QTY · TYPE qty ↵").
  5. Empty Enter while the cart is focused returns focus to the search box.

Safety: aborts before writing if any anchor is missing/ambiguous,
writes atomically via os.replace. Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

CART_TABLE_CLASS = '''class CartTable(QTableWidget):
    """Cart table that forwards qty-entry keys to the POS for fast quantity entry."""

    qty_key = Signal(object)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Escape, Qt.Key_Backspace):
            self.qty_key.emit(event)
            event.accept()
            return
        if event.text().isdigit():
            self.qty_key.emit(event)
            event.accept()
            return
        super().keyPressEvent(event)


'''

QTY_METHODS = '''
    def _paint_qty_hint(self):
        """Refresh the qty-entry status label next to the cart controls."""
        if not hasattr(self, "qty_hint"):
            return
        if self.qty_buffer:
            self.qty_hint.setText(f"QTY  →  {self.qty_buffer}  ↵")
            self.qty_hint.setStyleSheet(
                f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 800; "
                "letter-spacing: 0.12em; background: transparent;"
            )
        else:
            self.qty_hint.setText("F5 QTY  ·  TYPE qty ↵")
            self.qty_hint.setStyleSheet(
                f"color: {COLOR_DIM}; font-size: 11px; font-weight: 700; "
                "letter-spacing: 0.1em; background: transparent;"
            )

    def _clear_qty_buffer(self):
        self.qty_buffer = ""
        self._paint_qty_hint()

    def _commit_qty_buffer(self):
        """Apply the pending quantity to the selected cart line."""
        if not self.qty_buffer:
            # Empty Enter while the cart is focused returns to the search box.
            self.search_box.setFocus()
            return
        r = self._selected_cart_row()
        if r is None:
            self._clear_qty_buffer()
            return
        qty = max(1, int(self.qty_buffer))
        self.cart_items[r]["qty"] = qty
        self.cart_items[r]["qty_atomic"] = qty * self.cart_items[r].get("atoms_per", 1)
        self.qty_buffer = ""
        self._paint_qty_hint()
        self.update_ledger()

    def _on_cart_qty_key(self, event):
        """Route cart-table key events for quantity fast-entry."""
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self._commit_qty_buffer()
        elif key == Qt.Key_Escape:
            self._clear_qty_buffer()
        elif key == Qt.Key_Backspace:
            if self.qty_buffer:
                self.qty_buffer = self.qty_buffer[:-1]
                self._paint_qty_hint()
            else:
                self.remove_cart_line()
        elif event.text().isdigit():
            self.qty_buffer = (self.qty_buffer + event.text())[-3:]
            self._paint_qty_hint()

    def focus_cart(self):
        """F5 — move keyboard focus to the cart for quantity fast-entry."""
        if not self.cart_items:
            return
        rows = self.cart_table.rowCount()
        r = self.cart_table.currentRow()
        if r < 0 or r >= rows:
            r = rows - 1
        self.cart_table.selectRow(r)
        self.cart_table.setFocus()
        self._paint_qty_hint()

'''

EDITS = [
    (
        "CartTable class inserted before SearchLineEdit",
        "class SearchLineEdit(QLineEdit):",
        CART_TABLE_CLASS + "class SearchLineEdit(QLineEdit):",
    ),
    (
        "qty buffer state initialized",
        '        self.current_uom = "UNIT"',
        '        self.current_uom = "UNIT"\n        self.qty_buffer = ""',
    ),
    (
        "cart_table becomes CartTable",
        "        self.cart_table = QTableWidget(0, 4)",
        "        self.cart_table = CartTable(0, 4)",
    ),
    (
        "selection change clears pending qty",
        "        self.cart_table.itemDoubleClicked.connect(self.remove_cart_line)",
        "        self.cart_table.itemDoubleClicked.connect(self.remove_cart_line)\n"
        "        self.cart_table.itemSelectionChanged.connect(self._clear_qty_buffer)",
    ),
    (
        "qty status label added to cart controls",
        "        cart_ops.addStretch()",
        "        cart_ops.addStretch()\n"
        '        self.qty_hint = QLabel("F5 QTY  ·  TYPE qty ↵")\n'
        "        self.qty_hint.setMinimumWidth(190)\n"
        "        self.qty_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)\n"
        "        self.qty_hint.setStyleSheet(\n"
        "            f\"color: {COLOR_DIM}; font-size: 11px; font-weight: 700; \"\n"
        '            "letter-spacing: 0.1em; background: transparent;"\n'
        "        )\n"
        "        cart_ops.addWidget(self.qty_hint)",
    ),
    (
        "F5 shortcut added",
        '        QShortcut(QKeySequence("F2"), self, self.search_box.setFocus)',
        '        QShortcut(QKeySequence("F2"), self, self.search_box.setFocus)\n'
        '        QShortcut(QKeySequence("F5"), self, self.focus_cart)',
    ),
    (
        "cart qty keys connected",
        "        self.search_box.textChanged.connect(self.run_search)",
        "        self.search_box.textChanged.connect(self.run_search)\n"
        "        self.cart_table.qty_key.connect(self._on_cart_qty_key)",
    ),
    (
        "qty-entry methods inserted before open_zreport",
        "    def open_zreport(self):",
        QTY_METHODS + "    def open_zreport(self):",
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

    tmp = TARGET + ".ux020.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
