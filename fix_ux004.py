#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-004 — Ingest validation, inline errors, keyboard flow.

Changes sentinel/ui/purchasing.py only:

  1. Field-level validation BEFORE any database work:
     - product must be selected
     - batch code required
     - expiry must be YYYY-MM-DD and not in the past
     - quantity must be a whole number > 0
     - cost must be a number >= 0
  2. Errors appear on an inline status label in red (no raw exception
     text, no blocking modal) — fields keep their values so the
     operator can correct and retry instantly.
  3. Keyboard flow matching the registry: BATCH ↵ -> EXPIRY ↵ ->
     QTY ↵ -> COST ↵ COMMITS. The product selector is focused on open.
  4. Unexpected database errors roll back and show a human message with
     the technical detail (truncated) on the status label instead of a
     raw critical popup.

Note: the original audit also proposed a pre-commit confirmation modal;
it is deliberately omitted to keep the stock-in flow friction-free
(success feedback comes from the POS toast via on_complete).

Safety: every anchor must appear exactly once or the script aborts
before writing anything; atomic write via os.replace.
Rollback: git checkout -- sentinel/ui/purchasing.py
"""
import os
import sys

TARGET = "sentinel/ui/purchasing.py"

OLD_PROCESS = '''    def process_ingest(self):
        try:
            prod_id = self.prod_selector.currentData()
            qty = int(self.qty_in.text())
            cost_ghs = float(self.cost_in.text())
            cost_p = int(cost_ghs * 100)

            cursor = self.db.conn.cursor()

            cursor.execute(
                "SELECT id FROM product_versions WHERE product_id = ? AND is_current = 1",
                (prod_id,),
            )
            res = cursor.fetchone()
            if not res:
                cursor.execute(
                    "SELECT id FROM product_versions WHERE product_id = ? ORDER BY id DESC LIMIT 1",
                    (prod_id,),
                )
                res = cursor.fetchone()
            if not res:
                raise ValueError("Product missing version mapping. Re-add product in Registry.")
            version_id = res[0]

            on_hand = self.inv.get_on_hand(prod_id)
            cursor.execute(
                "SELECT cost_minor_per_unit FROM stock_ledger "
                "WHERE product_id = ? AND cost_minor_per_unit IS NOT NULL "
                "ORDER BY event_seq DESC LIMIT 1",
                (prod_id,),
            )
            ledger_res = cursor.fetchone()
            old_wac = ledger_res[0] if ledger_res and ledger_res[0] is not None else cost_p
            new_wac = calculate_wac(on_hand, old_wac, qty, cost_p)

            b_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO batches (uuid, product_version_id, batch_code, expiry_date, received_at) "
                "VALUES (?, ?, ?, ?, 'now')",
                (b_uuid, version_id, self.batch_in.text(), self.expiry_in.text()),
            )
            batch_id = cursor.lastrowid

            self.inv.record_movement(prod_id, qty, "PURCHASE_IN", "po", 0, batch_id, new_wac)

            self.db.conn.commit()
            self.close()
            if self.on_complete:
                self.on_complete()

        except Exception as e:
            QMessageBox.critical(self, "INGEST ERROR", str(e))
'''

NEW_PROCESS = '''    def _set_status(self, text, kind="info"):
        colors = {
            "info": COLOR_MUTED,
            "ok": COLOR_OK,
            "error": COLOR_DANGER,
        }
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            f"color: {colors.get(kind, COLOR_MUTED)}; font-size: 11px; "
            "font-weight: 700; letter-spacing: 0.06em;"
        )

    def _validate_fields(self):
        """Field-level validation with human messages. Returns (msg, values)."""
        prod_id = self.prod_selector.currentData()
        if prod_id is None:
            return "SELECT A PRODUCT FIRST", None
        batch = self.batch_in.text().strip().upper()
        if not batch:
            return "ENTER A LOT / BATCH CODE", None
        expiry_raw = self.expiry_in.text().strip()
        if not expiry_raw:
            return "ENTER AN EXPIRY DATE  ·  YYYY-MM-DD", None
        try:
            expiry = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
        except ValueError:
            return "EXPIRY MUST BE YYYY-MM-DD  ·  e.g. 2027-06-30", None
        if expiry < datetime.now().date():
            return f"EXPIRY {expiry_raw} IS IN THE PAST", None
        try:
            qty = int(self.qty_in.text().strip())
        except ValueError:
            return "QUANTITY MUST BE A WHOLE NUMBER", None
        if qty <= 0:
            return "QUANTITY MUST BE GREATER THAN ZERO", None
        try:
            cost_ghs = float(self.cost_in.text().strip())
        except ValueError:
            return "COST MUST BE A NUMBER  ·  e.g. 12.50", None
        if cost_ghs < 0:
            return "COST CANNOT BE NEGATIVE", None
        return None, {
            "prod_id": prod_id,
            "batch": batch,
            "expiry": expiry_raw,
            "qty": qty,
            "cost_ghs": cost_ghs,
        }

    def process_ingest(self):
        msg, values = self._validate_fields()
        if msg:
            self._set_status(msg, "error")
            return
        try:
            prod_id = values["prod_id"]
            qty = values["qty"]
            cost_p = int(values["cost_ghs"] * 100)

            cursor = self.db.conn.cursor()

            cursor.execute(
                "SELECT id FROM product_versions WHERE product_id = ? AND is_current = 1",
                (prod_id,),
            )
            res = cursor.fetchone()
            if not res:
                cursor.execute(
                    "SELECT id FROM product_versions WHERE product_id = ? ORDER BY id DESC LIMIT 1",
                    (prod_id,),
                )
                res = cursor.fetchone()
            if not res:
                raise ValueError("Product missing version mapping. Re-add product in Registry.")
            version_id = res[0]

            on_hand = self.inv.get_on_hand(prod_id)
            cursor.execute(
                "SELECT cost_minor_per_unit FROM stock_ledger "
                "WHERE product_id = ? AND cost_minor_per_unit IS NOT NULL "
                "ORDER BY event_seq DESC LIMIT 1",
                (prod_id,),
            )
            ledger_res = cursor.fetchone()
            old_wac = ledger_res[0] if ledger_res and ledger_res[0] is not None else cost_p
            new_wac = calculate_wac(on_hand, old_wac, qty, cost_p)

            b_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO batches (uuid, product_version_id, batch_code, expiry_date, received_at) "
                "VALUES (?, ?, ?, ?, 'now')",
                (b_uuid, version_id, values["batch"], values["expiry"]),
            )
            batch_id = cursor.lastrowid

            self.inv.record_movement(prod_id, qty, "PURCHASE_IN", "po", 0, batch_id, new_wac)

            self.db.conn.commit()
            self.close()
            if self.on_complete:
                self.on_complete()

        except Exception as e:
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            self._set_status(f"INGEST FAILED  ·  {str(e)[:80]}", "error")
'''

EDITS = [
    (
        "datetime import added",
        "import uuid\nfrom PySide6.QtWidgets import (",
        "import uuid\nfrom datetime import datetime\nfrom PySide6.QtWidgets import (",
    ),
    (
        "QtCore import gains QTimer",
        "from PySide6.QtCore import Qt",
        "from PySide6.QtCore import Qt, QTimer",
    ),
    (
        "components import gains COLOR_OK + COLOR_DANGER",
        """    COLOR_BORDER, COLOR_MUTED,
)""",
        """    COLOR_BORDER, COLOR_MUTED,
    COLOR_OK, COLOR_DANGER,
)""",
    ),
    (
        "inline status label added under the WAC note",
        """        note = QLabel("WAC is recalculated on commit from on-hand + this receipt.")
        note.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        note.setWordWrap(True)
        body.addWidget(note)""",
        """        note = QLabel("WAC is recalculated on commit from on-hand + this receipt.")
        note.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        note.setWordWrap(True)
        body.addWidget(note)

        self.status_lbl = QLabel("BATCH ↵  EXPIRY ↵  QTY ↵  COST ↵  COMMITS")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 0.06em;"
        )
        body.addWidget(self.status_lbl)""",
    ),
    (
        "keyboard flow wired: batch->expiry->qty->cost->commit; product focused on open",
        """        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)""",
        """        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)

        # Keyboard flow: BATCH ↵ -> EXPIRY ↵ -> QTY ↵ -> COST ↵ commits
        self.batch_in.returnPressed.connect(self.expiry_in.setFocus)
        self.expiry_in.returnPressed.connect(self.qty_in.setFocus)
        self.qty_in.returnPressed.connect(self.cost_in.setFocus)
        self.cost_in.returnPressed.connect(self.process_ingest)
        QTimer.singleShot(0, self.prod_selector.setFocus)""",
    ),
    (
        "process_ingest replaced with validated version + inline errors",
        OLD_PROCESS,
        NEW_PROCESS,
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

    tmp = TARGET + ".ux004.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, TARGET)
    print(f"[DONE] {TARGET} patched. Next: python3 -m py_compile {TARGET}")


if __name__ == "__main__":
    main()
