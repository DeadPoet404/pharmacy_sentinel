#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-003 — Registry rejects empty generic names; missing
brand defaults to UNBRANDED.

Changes sentinel/ui/registry.py only:

  1. Empty GENERIC NAME -> red inline status "ENTER A GENERIC NAME FIRST"
     and focus jumps to the field; nothing is written.
  2. Empty BRAND NAME -> saved as "UNBRANDED" instead of an empty string
     (the schema demands brand NOT NULL; empty strings were junk rows).
     Keeps the fast path: scan ↵ -> name ↵ -> brand ↵ still commits
     even when brand is skipped.
  3. Duplicates already surface in red on the status label (UX-017).

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace. Re-running the
script after a successful apply aborts safely (anchors no longer match).
Rollback: git checkout -- sentinel/ui/registry.py
"""
import os
import sys

TARGET = "sentinel/ui/registry.py"

EDITS = [
    (
        "save_product validates generic, defaults brand to UNBRANDED",
        """    def save_product(self):
        cursor = self.db.conn.cursor()
        try:
            p_uuid = str(uuid.uuid4())
""",
        """    def save_product(self):
        cursor = self.db.conn.cursor()
        generic = self.generic_in.text().strip().upper()
        brand = self.brand_in.text().strip().upper() or "UNBRANDED"
        if not generic:
            self.status_lbl.setText("ENTER A GENERIC NAME FIRST")
            self.status_lbl.setStyleSheet(
                f"color: {COLOR_DANGER}; font-size: 11px; font-weight: 800; "
                "letter-spacing: 0.08em; padding-top: 6px;"
            )
            self.generic_in.setFocus()
            return
        try:
            p_uuid = str(uuid.uuid4())
""",
    ),
    (
        "insert uses the validated generic/brand values",
        """                (
                    p_uuid,
                    self.generic_in.text().upper(),
                    self.brand_in.text().upper(),
                    self.form_in.currentText(),
                    self.barcode_in.text().strip().upper() or None,
                ),""",
        """                (
                    p_uuid,
                    generic,
                    brand,
                    self.form_in.currentText(),
                    self.barcode_in.text().strip().upper() or None,
                ),""",
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

    tmp = TARGET + ".ux003.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
