#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-016 — Global scan capture + scanner-burst discrimination.

Changes sentinel/ui/pos.py only:

  1. Global input routing in keyPressEvent: printable input that lands
     anywhere outside an editable field (window itself, buttons, labels)
     is routed into the search box and focused — a scanner or typed text
     always lands in the product flow.
  2. Enter routing: with search text present, Enter adds the match even
     when focus is on a button or the window (prevents Enter from firing
     a focused button while a scan is waiting to be added).
  3. CartTable scan-burst discrimination: human quantity digits arrive
     slowly (>=50ms apart) and are emitted one at a time as before. A
     barcode scanner floods digits within milliseconds; once more than
     three digits accumulate they are treated as a scan and routed to
     the search box, so a scan fired while the cart is focused adds a
     product instead of corrupting a quantity.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

NEW_CART_TABLE = '''class CartTable(QTableWidget):
    """Cart table: qty-entry keys plus barcode-scan burst discrimination.

    Human quantity digits arrive slowly and are emitted one at a time
    through qty_key. A barcode scanner floods digits within milliseconds;
    once more than three digits accumulate they are treated as a scan and
    routed to the POS search box (scan_keys) so the scan lands in the
    product flow instead of corrupting a quantity.
    """

    qty_key = Signal(str)      # commands: DIGIT:x / ENTER / BACKSPACE / ESC
    scan_keys = Signal(str)    # detected barcode-scan digit string

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._burst = ""
        self._burst_timer = QTimer(self)
        self._burst_timer.setSingleShot(True)
        self._burst_timer.setInterval(50)
        self._burst_timer.timeout.connect(self._flush_burst)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._burst:
                self.scan_keys.emit(self._burst)
                self._burst = ""
                self._burst_timer.stop()
            else:
                self.qty_key.emit("ENTER")
            event.accept()
            return
        if key == Qt.Key_Backspace:
            if self._burst:
                self._burst = self._burst[:-1]
                if not self._burst:
                    self._burst_timer.stop()
            else:
                self.qty_key.emit("BACKSPACE")
            event.accept()
            return
        if key == Qt.Key_Escape:
            if self._burst:
                self._burst = ""
                self._burst_timer.stop()
            self.qty_key.emit("ESC")
            event.accept()
            return
        if event.text().isdigit():
            self._burst += event.text()
            if len(self._burst) > 3:
                self.scan_keys.emit(self._burst)
                self._burst = ""
                self._burst_timer.stop()
            else:
                self._burst_timer.start()
            event.accept()
            return
        super().keyPressEvent(event)

    def _flush_burst(self):
        """Slow digits are human quantity entry — emit them one at a time."""
        digits = self._burst
        self._burst = ""
        for ch in digits:
            self.qty_key.emit(f"DIGIT:{ch}")
'''

OLD_CART_TABLE = '''class CartTable(QTableWidget):
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

OLD_QTY_KEY = '''    def _on_cart_qty_key(self, event):
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
'''

NEW_QTY_KEY = '''    def _on_cart_qty_key(self, cmd):
        """Route cart-table key commands for quantity fast-entry."""
        if cmd == "ENTER":
            self._commit_qty_buffer()
        elif cmd == "ESC":
            self._clear_qty_buffer()
        elif cmd == "BACKSPACE":
            if self.qty_buffer:
                self.qty_buffer = self.qty_buffer[:-1]
                self._paint_qty_hint()
            else:
                self.remove_cart_line()
        elif cmd.startswith("DIGIT:"):
            self.qty_buffer = (self.qty_buffer + cmd[6:])[-3:]
            self._paint_qty_hint()

    def _on_cart_scan(self, digits):
        """A barcode scan arrived while the cart was focused — route to search."""
        self.search_box.setFocus()
        self.search_box.setText(digits)
'''

OLD_KEYPRESS = '''    def keyPressEvent(self, event):
        if self.search_box.hasFocus() and event.text().isalpha():
            return super().keyPressEvent(event)
        key = event.key()
        if key in (Qt.Key_Delete, Qt.Key_Backspace) and not self.search_box.hasFocus():
            self.remove_cart_line()
            return
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.nudge_qty(1)
            return
        if key == Qt.Key_Minus:
            self.nudge_qty(-1)
            return
        super().keyPressEvent(event)
'''

NEW_KEYPRESS = '''    def keyPressEvent(self, event):
        """Global routing: scans/typing land in the search box even when
        focus has drifted onto a button or the window itself."""
        if self.search_box.hasFocus() and event.text().isalpha():
            return super().keyPressEvent(event)
        key = event.key()
        if key in (Qt.Key_Delete, Qt.Key_Backspace) and not self.search_box.hasFocus():
            self.remove_cart_line()
            return
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.nudge_qty(1)
            return
        if key == Qt.Key_Minus:
            self.nudge_qty(-1)
            return
        # UX-016: Enter with search text adds the match, even when focus
        # has drifted (prevents a focused button from swallowing the Enter
        # that belongs to a scan waiting in the search box).
        if key in (Qt.Key_Return, Qt.Key_Enter) and self.search_box.text().strip():
            self._search_return_pressed()
            return
        # UX-016: printable input outside an editable field -> search box
        text = event.text()
        if (
            text
            and text.strip()
            and text.isprintable()
            and not isinstance(QApplication.focusWidget(), QLineEdit)
        ):
            self.search_box.setFocus()
            self.search_box.insert(text)
            return
        super().keyPressEvent(event)
'''

EDITS = [
    (
        "QtWidgets import gains QApplication",
        """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox, QSizePolicy,
)""",
        """from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox, QSizePolicy,
    QApplication,
)""",
    ),
    (
        "CartTable gains scan-burst discrimination",
        OLD_CART_TABLE,
        NEW_CART_TABLE,
    ),
    (
        "scan_keys connected",
        "        self.cart_table.qty_key.connect(self._on_cart_qty_key)",
        "        self.cart_table.qty_key.connect(self._on_cart_qty_key)\n"
        "        self.cart_table.scan_keys.connect(self._on_cart_scan)",
    ),
    (
        "qty-key handler switches to the string protocol",
        OLD_QTY_KEY,
        NEW_QTY_KEY,
    ),
    (
        "keyPressEvent gains global scan/type routing",
        OLD_KEYPRESS,
        NEW_KEYPRESS,
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

    tmp = TARGET + ".ux016.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
