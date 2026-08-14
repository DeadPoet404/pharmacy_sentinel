#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-015 — Day totals shown before the Z-report close.

Changes sentinel/ui/zreport.py only:

  1. The ceremony window now shows a live totals line inside the meta
     card: "SALES n   ·   TOTAL GHS x,xxx.xx" — computed from the
     session's committed sales. The operator sees exactly what the
     day's Z-report will contain BEFORE initiating the irreversible
     close.
  2. Totals are refreshed when the window opens AND again when the
     ceremony starts, so they always reflect the latest committed
     sales.
  3. If the query fails for any reason, the preview degrades to zeros
     rather than crashing the window.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/zreport.py
"""
import os
import sys

TARGET = "sentinel/ui/zreport.py"

REFRESH_METHOD = '''    def _refresh_totals(self):
        """UX-015: day totals preview before the irreversible close."""
        try:
            cur = self.db.conn.cursor()
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(total_minor), 0) FROM sales "
                "WHERE pos_session_id = ?",
                (self.session_id,),
            )
            row = cur.fetchone()
            count = int(row[0] or 0)
            total_ghs = int(row[1] or 0) / 100
        except Exception:
            count, total_ghs = 0, 0.0
        self.totals_lbl.setText(f"SALES {count}   ·   TOTAL GHS {total_ghs:,.2f}")

'''

EDITS = [
    (
        "totals label added to the meta card",
        """        ml.addWidget(sess)
        ml.addWidget(dest)
        body.addWidget(meta)""",
        """        ml.addWidget(sess)
        ml.addWidget(dest)
        self.totals_lbl = QLabel("")
        self.totals_lbl.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 14px; font-weight: 800; "
            "letter-spacing: 0.12em; padding-top: 4px;"
        )
        ml.addWidget(self.totals_lbl)
        body.addWidget(meta)""",
    ),
    (
        "refresh method inserted before start_ceremony",
        "    def start_ceremony(self):",
        REFRESH_METHOD + "    def start_ceremony(self):",
    ),
    (
        "totals refreshed when the window opens",
        "        body.addWidget(self.run_btn)",
        "        body.addWidget(self.run_btn)\n\n"
        "        # UX-015: show the day's totals before the irreversible close\n"
        "        self._refresh_totals()",
    ),
    (
        "totals refreshed again when the ceremony starts",
        """        self._busy = True
        self._pending_success = None""",
        """        self._busy = True
        self._pending_success = None
        self._refresh_totals()""",
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

    tmp = TARGET + ".ux015.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
