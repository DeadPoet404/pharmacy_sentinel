#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-007 — Universal :disabled button styles.

Changes sentinel/ui/components.py only:

  1. GLOBAL_STYLE gains a QPushButton:disabled rule (dimmed surface,
     muted text, soft border) — plain QPushButtons across the app now
     visibly grey out when disabled.
  2. IndustrialButton gains matching :disabled blocks for all three
     variants (danger / primary / secondary). Previously a disabled
     button looked identical to an enabled one; operators clicked dead
     buttons and assumed the app was broken.
  3. The ad-hoc disabled styles added by UX-002 (login) and UX-021
     (checkout) remain valid — they re-apply the captured button sheet,
     which now simply includes the :disabled state.

Note on contrast: WCAG explicitly exempts disabled controls from
contrast requirements; muted text on a dimmed surface is the standard
"not interactive" signal.

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/components.py
"""
import os
import sys

TARGET = "sentinel/ui/components.py"

EDITS = [
    (
        "danger variant gains :disabled",
        "                QPushButton:hover {{ background: #E9927A; }}",
        "                QPushButton:hover {{ background: #E9927A; }}\n"
        "                QPushButton:disabled {{ background: {COLOR_SURFACE_2}; color: {COLOR_DIM}; }}",
    ),
    (
        "primary variant gains :disabled",
        """                QPushButton:hover {{ background: #F0C98A; }}
                QPushButton:pressed {{ background: {COLOR_ACCENT_DIM}; }}""",
        """                QPushButton:hover {{ background: #F0C98A; }}
                QPushButton:pressed {{ background: {COLOR_ACCENT_DIM}; }}
                QPushButton:disabled {{ background: {COLOR_SURFACE_2}; color: {COLOR_DIM}; }}""",
    ),
    (
        "secondary variant gains :disabled",
        """                QPushButton:hover {{
                    border-color: {COLOR_ACCENT};
                    color: {COLOR_ACCENT};
                }}""",
        """                QPushButton:hover {{
                    border-color: {COLOR_ACCENT};
                    color: {COLOR_ACCENT};
                }}
                QPushButton:disabled {{
                    background: {COLOR_SURFACE_2};
                    color: {COLOR_DIM};
                    border-color: {COLOR_BORDER_SOFT};
                }}""",
    ),
    (
        "GLOBAL_STYLE gains QPushButton:disabled",
        """QTabBar::tab:selected {{
    color: {COLOR_ACCENT};
    background: {COLOR_SURFACE};
}}
\"\"\"""",
        """QTabBar::tab:selected {{
    color: {COLOR_ACCENT};
    background: {COLOR_SURFACE};
}}
QPushButton:disabled {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_DIM};
    border: 1px solid {COLOR_BORDER_SOFT};
}}
\"\"\"""",
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

    tmp = TARGET + ".ux007.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
