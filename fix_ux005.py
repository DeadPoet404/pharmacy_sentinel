#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-005 — Overselling warns at add-time; debt needs consent.

Changes sentinel/ui/pos.py only:

  1. Add-time guardrail: when a cart line's quantity exceeds on-hand,
     the operator sees an amber toast
     ("LOW STOCK · <NAME> · ON-HAND <n> · SHORTAGE WILL BE DEBT") and
     the line's QTY cell turns red in the ledger.
  2. Settlement consent: if any cart line still exceeds on-hand at F8,
     a blocking confirmation lists the short lines and asks
     "Commit the shortage as a DEBT sale?" — No by default. Only an
     explicit Yes proceeds. (A modal is justified here: this is a
     consequential action with audit implications.)
  3. Lines within stock behave exactly as before — no dialog, no toast.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

NEW_SELECT_TAIL = '''        uom = self.current_uom
        for line in self.cart_items:
            if line["id"] == p_id and line.get("uom") == uom:
                line["qty"] = line.get("qty", 1) + 1
                line["qty_atomic"] = line["qty"] * line.get("atoms_per", 1)
                self._check_line_stock(line)
                self.update_ledger()
                return
        line = {
            "id": p_id,
            "name": it.text(),
            "qty": 1,
            "price": price,
            "uom": uom,
            "atoms_per": atoms,
            "qty_atomic": atoms,
        }
        self.cart_items.append(line)
        self._check_line_stock(line)
        self.update_ledger()
'''

OLD_SELECT_TAIL = '''        uom = self.current_uom
        for line in self.cart_items:
            if line["id"] == p_id and line.get("uom") == uom:
                line["qty"] = line.get("qty", 1) + 1
                line["qty_atomic"] = line["qty"] * line.get("atoms_per", 1)
                self.update_ledger()
                return
        self.cart_items.append({
            "id": p_id,
            "name": it.text(),
            "qty": 1,
            "price": price,
            "uom": uom,
            "atoms_per": atoms,
            "qty_atomic": atoms,
        })
        self.update_ledger()
'''

OLD_OPEN_CHECKOUT = '''    def open_checkout(self):
        if not self.cart_items:
            self.toast.show_message("LEDGER EMPTY  ·  ADD A LINE FIRST", "error")
            return
        raw = self.total_lbl.text().replace(",", "")
        t = float(raw or 0)
        self.checkout_ui = SettlementUI(t, self.finalize_sale)
        self.checkout_ui.show()
'''

NEW_OPEN_CHECKOUT = '''    def _check_line_stock(self, line):
        """Warn (non-blocking) when a cart line exceeds on-hand (UX-005)."""
        try:
            oh = int(self.sales_ctrl.inv.get_on_hand(line["id"]) or 0)
        except Exception:
            oh = None
        line["overdraft"] = oh is not None and line.get("qty_atomic", 0) > oh
        if line["overdraft"] and hasattr(self, "toast"):
            self.toast.show_message(
                f"LOW STOCK  ·  {line['name']}  ·  ON-HAND {oh}  ·  SHORTAGE WILL BE DEBT",
                "info",
                duration_ms=2500,
            )

    def open_checkout(self):
        if not self.cart_items:
            self.toast.show_message("LEDGER EMPTY  ·  ADD A LINE FIRST", "error")
            return
        short_lines = []
        for line in self.cart_items:
            try:
                oh = int(self.sales_ctrl.inv.get_on_hand(line["id"]) or 0)
            except Exception:
                oh = None
            if oh is not None and line.get("qty_atomic", 0) > oh:
                short_lines.append(f"· {line['name']}   {oh} on hand")
        if short_lines:
            ans = QMessageBox.question(
                self,
                "SHORTAGE  ·  DEBT REQUIRED",
                "Insufficient stock for:\\n" + "\\n".join(short_lines)
                + "\\n\\nCommit the shortage as a DEBT sale?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if ans != QMessageBox.Yes:
                return
        raw = self.total_lbl.text().replace(",", "")
        t = float(raw or 0)
        self.checkout_ui = SettlementUI(t, self.finalize_sale)
        self.checkout_ui.show()
'''

EDITS = [
    (
        "COLOR_DANGER imported from the UI kit",
        """    COLOR_TEXT, COLOR_BG, apply_deep_elevation,
    Toast,
)""",
        """    COLOR_TEXT, COLOR_BG, apply_deep_elevation,
    Toast, COLOR_DANGER,
)""",
    ),
    (
        "select_item checks stock after every add/merge",
        OLD_SELECT_TAIL,
        NEW_SELECT_TAIL,
    ),
    (
        "overdraft lines render their QTY in red",
        """            self._style_item(n)
            self._style_item(u, muted=True)
            self._style_item(q, align_right=True, muted=True)
            self._style_item(p, align_right=True)""",
        """            self._style_item(n)
            self._style_item(u, muted=True)
            self._style_item(q, align_right=True, muted=True)
            self._style_item(p, align_right=True)
            if i.get("overdraft"):
                q.setForeground(QColor(COLOR_DANGER))""",
    ),
    (
        "open_checkout gains debt consent; _check_line_stock added",
        OLD_OPEN_CHECKOUT,
        NEW_OPEN_CHECKOUT,
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

    tmp = TARGET + ".ux005.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
