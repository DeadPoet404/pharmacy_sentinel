#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-008 — Contrast-safe dim color + focus-visible rings.

Changes sentinel/ui/components.py only:

  1. COLOR_DIM raised from #5C6478 (3.29:1 — failed WCAG AA) to
     #7A8498 (5.17:1 on the darkest background, >=4.5:1 on every
     surface in the palette). All labels using the constant improve
     automatically.
  2. GLOBAL_STYLE gains QPushButton:focus (accent ring) and
     QTableWidget/QTableView:focus (accent border) — keyboard users
     can see exactly where they are.
  3. IndustrialButton variants gain :focus rings too (their own
     stylesheets override the global rule): danger/primary get a light
     ring (#FFF8EC), secondary gets the accent border + accent text.

Note: the one hardcoded #5C6478 left in checkout.py styles a DISABLED
button — WCAG exempts disabled controls from contrast requirements.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/components.py
"""
import os
import sys

TARGET = "sentinel/ui/components.py"

EDITS = [
    (
        "COLOR_DIM raised to AA-safe value",
        'COLOR_DIM = "#5C6478"',
        'COLOR_DIM = "#7A8498"',
    ),
    (
        "global focus rings added after the disabled rule",
        """QPushButton:disabled {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_DIM};
    border: 1px solid {COLOR_BORDER_SOFT};
}}
\"\"\"""",
        """QPushButton:disabled {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_DIM};
    border: 1px solid {COLOR_BORDER_SOFT};
}}
QPushButton:focus {{
    border: 2px solid {COLOR_ACCENT};
}}
QTableWidget:focus, QTableView:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
\"\"\"""",
    ),
    (
        "danger variant gains a focus ring",
        """                QPushButton:hover {{ background: #E9927A; }}
                QPushButton:disabled {{ background: {COLOR_SURFACE_2}; color: {COLOR_DIM}; }}""",
        """                QPushButton:hover {{ background: #E9927A; }}
                QPushButton:disabled {{ background: {COLOR_SURFACE_2}; color: {COLOR_DIM}; }}
                QPushButton:focus {{ border: 2px solid #FFF8EC; }}""",
    ),
    (
        "primary variant gains a focus ring",
        """                QPushButton:pressed {{ background: {COLOR_ACCENT_DIM}; }}
                QPushButton:disabled {{ background: {COLOR_SURFACE_2}; color: {COLOR_DIM}; }}""",
        """                QPushButton:pressed {{ background: {COLOR_ACCENT_DIM}; }}
                QPushButton:disabled {{ background: {COLOR_SURFACE_2}; color: {COLOR_DIM}; }}
                QPushButton:focus {{ border: 2px solid #FFF8EC; }}""",
    ),
    (
        "secondary variant gains a focus ring",
        """                QPushButton:disabled {{
                    background: {COLOR_SURFACE_2};
                    color: {COLOR_DIM};
                    border-color: {COLOR_BORDER_SOFT};
                }}""",
        """                QPushButton:disabled {{
                    background: {COLOR_SURFACE_2};
                    color: {COLOR_DIM};
                    border-color: {COLOR_BORDER_SOFT};
                }}
                QPushButton:focus {{
                    border-color: {COLOR_ACCENT};
                    color: {COLOR_ACCENT};
                }}""",
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

    tmp = TARGET + ".ux008.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
