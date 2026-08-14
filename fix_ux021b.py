#!/usr/bin/env python3
"""
Fix(UX): UX-021 follow-up — E-key leaking into the tender field.

Symptom: pressing E in the settlement window typed 'e' into the amount
field, so the label showed "ENTER A NUMBER" instead of pre-filling EXACT.

Cause: the EXACT hotkey was a window-level QShortcut("E"). With the
tender field focused, the key event also reached the QLineEdit and was
inserted as text, corrupting the amount.

Fix: E is now handled INSIDE the tender field by a TenderLineEdit
subclass that intercepts the key and emits exact_key — it can never be
typed into the amount. F5 remains the window-level EXACT shortcut and
F6/F7/F8 quick notes are unchanged.

Changes sentinel/ui/checkout.py only. Safety: every anchor must appear
exactly once or the script aborts before writing anything; writes are
atomic via os.replace. Rollback: git checkout -- sentinel/ui/checkout.py
"""
import os
import sys

TARGET = "sentinel/ui/checkout.py"

TENDER_CLASS = '''class TenderLineEdit(QLineEdit):
    """Tender field: E means EXACT — it is never inserted as text."""

    exact_key = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_E and event.modifiers() in (Qt.NoModifier, Qt.ShiftModifier):
            self.exact_key.emit()
            event.accept()
            return
        super().keyPressEvent(event)


'''

EDITS = [
    (
        "QtCore import gains Signal",
        "from PySide6.QtCore import Qt",
        "from PySide6.QtCore import Qt, Signal",
    ),
    (
        "TenderLineEdit class inserted before SettlementUI",
        "class SettlementUI(QWidget):",
        TENDER_CLASS + "class SettlementUI(QWidget):",
    ),
    (
        "tendered_in becomes TenderLineEdit",
        "        self.tendered_in = QLineEdit()",
        "        self.tendered_in = TenderLineEdit()",
    ),
    (
        "E shortcut removed from the window level",
        """        # Keyboard-first tender: E/F5 = EXACT, F6/F7/F8 = quick notes
        QShortcut(QKeySequence("E"), self, self.fill_exact)
        QShortcut(QKeySequence("F5"), self, self.fill_exact)""",
        """        # Keyboard-first tender: F5 = EXACT, F6/F7/F8 = quick notes
        # (E is handled by TenderLineEdit so it can never leak into the amount)
        QShortcut(QKeySequence("F5"), self, self.fill_exact)""",
    ),
    (
        "exact_key connected to fill_exact",
        """        self.tendered_in.returnPressed.connect(lambda: self.finish("CASH"))
        self.tendered_in.setFocus()""",
        """        self.tendered_in.returnPressed.connect(lambda: self.finish("CASH"))
        self.tendered_in.exact_key.connect(self.fill_exact)
        self.tendered_in.setFocus()""",
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

    tmp = TARGET + ".ux021b.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
