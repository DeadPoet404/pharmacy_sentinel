#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-009 — Debounced search with scanner fast path.

Changes sentinel/ui/pos.py only:

  1. Typed input no longer queries the DB on every keystroke — a 180ms
     debounce timer collapses a typed word into ONE query (large
     catalogs stay smooth).
  2. Scanner fast path: digit-only input of 8+ characters (barcode
     scans) queries IMMEDIATELY — zero added latency for the scanner.
  3. Flush-on-Enter: if Enter arrives while a query is still pending,
     the search runs synchronously FIRST, so Enter always adds the
     correct, fresh match (no stale-result adds).
  4. Empty text refreshes immediately (clear = show all), and UoM
     changes / ingest completion keep their immediate refresh.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/pos.py
"""
import os
import sys

TARGET = "sentinel/ui/pos.py"

EDITS = [
    (
        "debounce timer created in __init__",
        "        self.toast = Toast(self)",
        "        self.toast = Toast(self)\n"
        "        self._debounce = QTimer(self)\n"
        "        self._debounce.setSingleShot(True)\n"
        "        self._debounce.setInterval(180)\n"
        "        self._debounce.timeout.connect(self.run_search)",
    ),
    (
        "textChanged now routes through the debounce handler",
        "        self.search_box.textChanged.connect(self.run_search)",
        "        self.search_box.textChanged.connect(self._on_search_text_changed)",
    ),
    (
        "debounce handlers inserted before run_search",
        "    def run_search(self):",
        """    def _on_search_text_changed(self, txt):
        \"\"\"Debounced search (UX-009): one query per typed burst.

        Empty text refreshes immediately (clear = show all). Digit-only
        input of 8+ characters is treated as a barcode scan and queried
        instantly — the scanner fast path. Ordinary typing waits for the
        debounce timer.
        \"\"\"
        if not txt.strip():
            self._debounce.stop()
            self.run_search()
            return
        if txt.strip().isdigit() and len(txt.strip()) >= 8:
            self._debounce.stop()
            self.run_search()
            return
        self._debounce.start()

    def _flush_search(self):
        \"\"\"Force the pending query to run now (Enter adds fresh results).\"\"\"
        if self._debounce.isActive():
            self._debounce.stop()
            self.run_search()

    def run_search(self):""",
    ),
    (
        "Enter flushes a pending query before adding",
        """        txt = self.search_box.text().strip()
        if not txt:
            return
        rows = self.search_table.rowCount()""",
        """        txt = self.search_box.text().strip()
        if not txt:
            return
        self._flush_search()
        rows = self.search_table.rowCount()""",
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

    tmp = TARGET + ".ux009.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
