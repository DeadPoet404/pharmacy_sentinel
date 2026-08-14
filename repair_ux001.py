#!/usr/bin/env python3
"""
Repair UX-001: rebuild finalize_sale after a duplicated `else:`.

Cause of the break: fix_ux001.py was applied twice. Its anchor text
survives its own replacement, so a second run appended a second
`else:` to the same if-block -> SyntaxError at line ~917.

This script:
  1. Locates `def finalize_sale` (last method of BrutalistPOS).
  2. Replaces the method through the end of its class body with a
     canonical implementation (success toast + visible failure toast,
     with a QMessageBox fallback if the Toast was never installed).
  3. Marks the rebuilt method so re-running this script is a no-op.

Idempotent and safe: if the canonical method is already present, it
prints [INFO] and exits without writing. Everything outside
finalize_sale is untouched.
"""
import os
import re
import sys

TARGET = "sentinel/ui/pos.py"
MARKER = "# [UX-001] canonical finalize_sale"

CANONICAL = '''    def finalize_sale(self, method, tendered):
        """Commit the cart. Failure is visible and preserves the cart."""
        total = float(self.total_lbl.text().replace(",", "") or 0)
        if self.sales_ctrl.commit_sale(
            self.user_id,
            self.session_id,
            self.cart_items,
            total,
            method,
            tendered,
        ):
            change = tendered - total
            if hasattr(self, "toast"):
                self.toast.show_message(f"SALE COMMITTED  ·  CHANGE {change:,.2f}", "success")
            else:
                QMessageBox.information(self, "SUCCESS", f"Sale committed. Change: {change:,.2f}")
            self.cart_items = []
            self.update_ledger()
            self.run_search()
            self.search_box.setFocus()
            self.viz_img.clear()
            self.viz_img.setText("No item\\nselected")
            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_DIM}; "
                "font-size: 12px; letter-spacing: 0.08em;"
            )
        else:
            # [UX-001] canonical finalize_sale
            if hasattr(self, "toast"):
                self.toast.show_message(
                    "SALE FAILED  ·  CART PRESERVED  ·  PRESS F8 TO RETRY",
                    "error",
                    duration_ms=5000,
                )
            else:
                QMessageBox.warning(
                    self,
                    "SALE FAILED",
                    "The sale could not be committed. Cart preserved.",
                )
'''


def main():
    if not os.path.exists(TARGET):
        print(f"[ABORT] {TARGET} not found. Run this script from the repository root.")
        sys.exit(1)

    src = open(TARGET, encoding="utf-8").read()

    if MARKER in src:
        print("[INFO] Canonical finalize_sale already present — nothing to do.")
        sys.exit(0)

    lines = src.splitlines(keepends=True)

    start = None
    for i, ln in enumerate(lines):
        if ln.strip() == "def finalize_sale(self, method, tendered):" and ln.startswith("    "):
            start = i
            break
    if start is None:
        print("[ABORT] def finalize_sale not found — the file differs from expectations.")
        print("        Paste the tail of sentinel/ui/pos.py (last ~60 lines) here.")
        sys.exit(1)

    # Method ends at the next class-level def, or end of file.
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.match(r"^    def \w", lines[j]):
            end = j
            break

    new_src = "".join(lines[:start]) + CANONICAL + "".join(lines[end:])
    if not new_src.endswith("\n"):
        new_src += "\n"

    tmp = TARGET + ".repair.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(new_src)
    os.replace(tmp, TARGET)
    print(f"[DONE] Rebuilt finalize_sale (old lines {start + 1}..{end}).")
    print("Next: python3 -m py_compile sentinel/ui/pos.py")


if __name__ == "__main__":
    main()
