#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-001 — Silent sale failure now visible.

Changes sentinel/ui/pos.py only:
  finalize_sale() gains an else branch. When SalesController.commit_sale()
  returns False the operator now sees a red error toast
  ("SALE FAILED · CART PRESERVED · PRESS F8 TO RETRY") for 5 seconds,
  and the cart is left untouched so the sale can be retried with F8.

Previously a failed commit was invisible: commit_sale() only prints to
stdout, the checkout window closed, and the operator could not tell the
sale had not been recorded.

Note: the exact database reason is swallowed inside commit_sale()
(logic/sales.py); surfacing it requires the sales.py refactor flagged
in the audit's Appendix B and is intentionally out of scope here.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

EDITS = [
    (
        "else branch added to finalize_sale (failed commit becomes visible)",
        """            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_DIM}; "
                "font-size: 12px; letter-spacing: 0.08em;"
            )""",
        """            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_DIM}; "
                "font-size: 12px; letter-spacing: 0.08em;"
            )
        else:
            self.toast.show_message(
                "SALE FAILED  ·  CART PRESERVED  ·  PRESS F8 TO RETRY",
                "error",
                duration_ms=5000,
            )""",
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

    tmp = TARGET + ".ux001.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
