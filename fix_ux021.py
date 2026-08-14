#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-021 — Checkout hotkeys, tender gating, focus return.

Changes two files only:
  sentinel/ui/checkout.py
    - E or F5 = EXACT tender; F6/F7/F8 = quick notes 50/100/200.
    - FINALIZE button disabled until the tender is a valid amount >= total;
      the disabled state is visibly styled (no dead-looking accent button).
    - Invalid text shows inline "ENTER A NUMBER"; short shows "SHORT  x.xx".
    - Bottom hint teaches the keyboard tender flow.
  sentinel/ui/pos.py
    - After a successful sale, focus returns to the search box so the next
      item can be typed/scanned immediately.

Safety: validates every anchor for BOTH files before writing anything,
aborts without changes if any anchor is missing/ambiguous,
writes atomically via os.replace. Rollback: git checkout -- sentinel/ui/checkout.py sentinel/ui/pos.py
"""
import os
import sys

FILL_METHODS = '''    def fill_exact(self):
        """Pre-fill the tender with the exact amount due."""
        self.tendered_in.setText(f"{self.total_ghs:,.2f}")

    def fill_amount(self, amount):
        """Pre-fill the tender with a quick note amount."""
        self.tendered_in.setText(f"{float(amount):,.2f}")

'''

NEW_CALC_CHANGE = '''    def calc_change(self):
        """Live change display, inline validation, and tender gating."""
        if not hasattr(self, "btn_cash"):
            return
        txt = self.tendered_in.text().replace(",", "")
        if not txt.strip():
            self.change_out.setText("CHANGE   0.00")
            self.change_out.setStyleSheet(
                f"color: {COLOR_MUTED}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
            )
            self._set_cash_enabled(False)
            return
        try:
            tendered = float(txt)
        except ValueError:
            self.change_out.setText("ENTER A NUMBER")
            self.change_out.setStyleSheet(
                f"color: {COLOR_DANGER}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
            )
            self._set_cash_enabled(False)
            return
        change = tendered - self.total_ghs
        if change < 0:
            self.change_out.setText(f"SHORT   {abs(change):,.2f}")
            self.change_out.setStyleSheet(
                f"color: {COLOR_DANGER}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
            )
            self._set_cash_enabled(False)
        else:
            self.change_out.setText(f"CHANGE   {change:,.2f}")
            self.change_out.setStyleSheet(
                f"color: {COLOR_ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
            )
            self._set_cash_enabled(True)

    def _set_cash_enabled(self, on):
        """Enable/disable FINALIZE with a visible disabled style."""
        if not hasattr(self, "btn_cash"):
            return
        self.btn_cash.setEnabled(on)
        if on:
            self.btn_cash.setStyleSheet(self._cash_style)
        else:
            self.btn_cash.setStyleSheet("""
                QPushButton {
                    background: #181C23;
                    color: #5C6478;
                    border: 1px solid #2A3140;
                    border-radius: 10px;
                    font-weight: 800;
                    font-size: 13px;
                    letter-spacing: 0.1em;
                    padding: 0 22px;
                }
            """)
'''

OLD_CALC_CHANGE = '''    def calc_change(self):
        try:
            tendered = float(self.tendered_in.text().replace(",", "") or 0)
            change = tendered - self.total_ghs
            if change < 0:
                self.change_out.setText(f"SHORT   {abs(change):,.2f}")
                self.change_out.setStyleSheet(
                    f"color: {COLOR_DANGER}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
                )
            else:
                self.change_out.setText(f"CHANGE   {change:,.2f}")
                self.change_out.setStyleSheet(
                    f"color: {COLOR_ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
                )
        except ValueError:
            pass
'''

# Each file: (path, [(label, exact_old, new), ...])
FILES = [
    ("sentinel/ui/checkout.py", [
        (
            "QtGui import gains QShortcut + QKeySequence",
            "from PySide6.QtGui import QColor",
            "from PySide6.QtGui import QColor, QShortcut, QKeySequence",
        ),
        (
            "FINALIZE starts disabled with its accent style captured",
            """        self.btn_cash = IndustrialButton("COMPLETE CASH SALE")
        self.btn_cash.setFixedHeight(58)
        self.btn_cash.clicked.connect(lambda: self.finish("CASH"))
        body.addWidget(self.btn_cash)""",
            """        self.btn_cash = IndustrialButton("COMPLETE CASH SALE")
        self.btn_cash.setFixedHeight(58)
        self._cash_style = self.btn_cash.styleSheet()
        self.btn_cash.setEnabled(False)
        self.btn_cash.clicked.connect(lambda: self.finish("CASH"))
        body.addWidget(self.btn_cash)""",
        ),
        (
            "hint teaches the keyboard tender flow",
            '        hint = QLabel("Enter tender  ·  Enter to confirm")',
            '        hint = QLabel("E EXACT  ·  F6 50  ·  F7 100  ·  F8 200  ·  ↵ CONFIRM")',
        ),
        (
            "keyboard tender shortcuts registered",
            """        self.tendered_in.returnPressed.connect(lambda: self.finish("CASH"))
        self.tendered_in.setFocus()""",
            """        self.tendered_in.returnPressed.connect(lambda: self.finish("CASH"))
        self.tendered_in.setFocus()

        # Keyboard-first tender: E/F5 = EXACT, F6/F7/F8 = quick notes
        QShortcut(QKeySequence("E"), self, self.fill_exact)
        QShortcut(QKeySequence("F5"), self, self.fill_exact)
        QShortcut(QKeySequence("F6"), self, lambda: self.fill_amount(50))
        QShortcut(QKeySequence("F7"), self, lambda: self.fill_amount(100))
        QShortcut(QKeySequence("F8"), self, lambda: self.fill_amount(200))""",
        ),
        (
            "missing quick-tender helpers added (HEAD bug: fill_exact/fill_amount did not exist, checkout crashed on open)",
            "    def calc_change(self):",
            FILL_METHODS + "    def calc_change(self):",
        ),
        (
            "calc_change rewritten with inline validation + gating",
            OLD_CALC_CHANGE,
            NEW_CALC_CHANGE,
        ),
    ]),
    ("sentinel/ui/pos.py", [
        (
            "focus returns to search box after a successful sale",
            """            QMessageBox.information(self, "SUCCESS", "Sale committed.")
            self.cart_items = []
            self.update_ledger()
            self.run_search()""",
            """            QMessageBox.information(self, "SUCCESS", "Sale committed.")
            self.cart_items = []
            self.update_ledger()
            self.run_search()
            self.search_box.setFocus()""",
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
        tmp = path + ".ux021.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    print("[DONE] Patch applied.")
    print("Next: python3 -m py_compile sentinel/ui/checkout.py sentinel/ui/pos.py")


if __name__ == "__main__":
    main()
