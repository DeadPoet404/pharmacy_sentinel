#!/usr/bin/env python3
"""
Fix(UX): Resolve UX-017 — Barcode data model + scan-to-capture registry.

Changes four files:
  sentinel/db/schema.py
    - products table gains an additive `barcode TEXT` column (fresh DBs).
  sentinel/db/manager.py
    - initialize() now runs an idempotent migration: existing databases
      get `ALTER TABLE products ADD COLUMN barcode TEXT` if the column
      is missing. Existing data is untouched.
  sentinel/ui/registry.py
    - New BARCODE field (first in the form, auto-focused on open).
    - Scan-to-capture flow: scan (or type) barcode + Enter -> GENERIC,
      Enter -> BRAND, Enter -> COMMITS. After a successful commit the
      fields clear and focus returns to BARCODE for the next product.
    - Status label gives instant feedback (ADDED ... / error in red).
    - Catalog table gains a BARCODE column.
  sentinel/ui/pos.py
    - POS search now also matches an exact barcode, so a scanner at the
      till filters to the product immediately (Enter adds it).

Safety: every anchor must appear exactly once or the script aborts
before writing anything; all four files are validated before any write;
writes are atomic via os.replace.
Rollback: git checkout -- sentinel/db/schema.py sentinel/db/manager.py sentinel/ui/registry.py sentinel/ui/pos.py
"""
import os
import sys

FILES = [
    ("sentinel/db/schema.py", [
        (
            "products gains barcode column (fresh databases)",
            """  form TEXT NOT NULL,
  regulatory_class TEXT NOT NULL CHECK(regulatory_class IN ('POM','OTC','OTHER')),""",
            """  form TEXT NOT NULL,
  barcode TEXT,
  regulatory_class TEXT NOT NULL CHECK(regulatory_class IN ('POM','OTC','OTHER')),""",
        ),
    ]),
    ("sentinel/db/manager.py", [
        (
            "initialize() runs the idempotent barcode migration",
            """    def initialize(self):
        if self.conn is None: self.connect()
        c = self.conn.cursor()
        c.executescript(SCHEMA_DDL)
        self.conn.commit()
""",
            """    def initialize(self):
        if self.conn is None: self.connect()
        c = self.conn.cursor()
        c.executescript(SCHEMA_DDL)
        self._migrate()
        self.conn.commit()

    def _migrate(self):
        \"\"\"Additive, idempotent migrations for databases created earlier.\"\"\"
        c = self.conn.cursor()
        cols = {row[1] for row in c.execute("PRAGMA table_info(products)").fetchall()}
        if "barcode" not in cols:
            c.execute("ALTER TABLE products ADD COLUMN barcode TEXT")
            print("[MIGRATE] products.barcode added")
""",
        ),
    ]),
    ("sentinel/ui/registry.py", [
        (
            "QtCore import gains QTimer",
            "from PySide6.QtCore import Qt",
            "from PySide6.QtCore import Qt, QTimer",
        ),
        (
            "components import gains COLOR_OK + COLOR_DANGER",
            """    COLOR_ACCENT, COLOR_DIM, COLOR_TEXT, COLOR_BORDER, COLOR_MUTED,
)""",
            """    COLOR_ACCENT, COLOR_DIM, COLOR_TEXT, COLOR_BORDER, COLOR_MUTED,
    COLOR_OK, COLOR_DANGER,
)""",
        ),
        (
            "BARCODE field added as the first form row",
            """        self.generic_in = QLineEdit()
        self.generic_in.setPlaceholderText("e.g. AMOXICILLIN")
        self.brand_in = QLineEdit()
        self.brand_in.setPlaceholderText("e.g. AMOXIL")
        self.form_in = QComboBox()
        self.form_in.addItems(["CAPSULE", "SYRUP", "STRIP", "PILL"])

        fl.addRow("GENERIC NAME", self.generic_in)
        fl.addRow("BRAND NAME", self.brand_in)
        fl.addRow("DOSAGE FORM", self.form_in)""",
            """        self.barcode_in = QLineEdit()
        self.barcode_in.setPlaceholderText("SCAN  ·  or type barcode")
        self.generic_in = QLineEdit()
        self.generic_in.setPlaceholderText("e.g. AMOXICILLIN")
        self.brand_in = QLineEdit()
        self.brand_in.setPlaceholderText("e.g. AMOXIL")
        self.form_in = QComboBox()
        self.form_in.addItems(["CAPSULE", "SYRUP", "STRIP", "PILL"])

        fl.addRow("BARCODE", self.barcode_in)
        fl.addRow("GENERIC NAME", self.generic_in)
        fl.addRow("BRAND NAME", self.brand_in)
        fl.addRow("DOSAGE FORM", self.form_in)""",
        ),
        (
            "status label added under the save button",
            """        self.save_btn = IndustrialButton("COMMIT TO LEDGER")
        self.save_btn.clicked.connect(self.save_product)
        fl.addRow(self.save_btn)""",
            """        self.save_btn = IndustrialButton("COMMIT TO LEDGER")
        self.save_btn.clicked.connect(self.save_product)
        fl.addRow(self.save_btn)

        self.status_lbl = QLabel("SCAN  →  NAME  →  BRAND ↵  COMMITS")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 0.08em; padding-top: 6px;"
        )
        fl.addRow(self.status_lbl)""",
        ),
        (
            "catalog table gains a BARCODE column",
            """        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["ITEM", "FORM"])""",
            """        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ITEM", "FORM", "BARCODE"])""",
        ),
        (
            "third column resize mode",
            """        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)""",
            """        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)""",
        ),
        (
            "scan-to-capture keyboard flow wired after refresh_list",
            """        self.refresh_list()

    def refresh_list(self):""",
            """        self.refresh_list()

        # Scan-to-capture flow: scan ↵ -> name ↵ -> brand ↵ commits
        self.barcode_in.returnPressed.connect(self.generic_in.setFocus)
        self.generic_in.returnPressed.connect(self.brand_in.setFocus)
        self.brand_in.returnPressed.connect(self.save_product)
        QTimer.singleShot(0, self.barcode_in.setFocus)

    def refresh_list(self):""",
        ),
        (
            "refresh_list reads and renders barcode",
            """        cursor.execute("SELECT generic_molecule, form FROM products")
        prods = cursor.fetchall()
        self.table.setRowCount(0)
        for p in prods:
            r = self.table.rowCount()
            self.table.insertRow(r)
            a = QTableWidgetItem(str(p[0]))
            b = QTableWidgetItem(str(p[1]))
            a.setForeground(QColor(COLOR_TEXT))
            b.setForeground(QColor(COLOR_MUTED))
            f = a.font()
            f.setWeight(QFont.DemiBold)
            a.setFont(f)
            self.table.setItem(r, 0, a)
            self.table.setItem(r, 1, b)""",
            """        cursor.execute("SELECT generic_molecule, form, barcode FROM products")
        prods = cursor.fetchall()
        self.table.setRowCount(0)
        for p in prods:
            r = self.table.rowCount()
            self.table.insertRow(r)
            a = QTableWidgetItem(str(p[0]))
            b = QTableWidgetItem(str(p[1]))
            c = QTableWidgetItem(str(p[2]) if p[2] else "—")
            a.setForeground(QColor(COLOR_TEXT))
            b.setForeground(QColor(COLOR_MUTED))
            c.setForeground(QColor(COLOR_MUTED))
            f = a.font()
            f.setWeight(QFont.DemiBold)
            a.setFont(f)
            self.table.setItem(r, 0, a)
            self.table.setItem(r, 1, b)
            self.table.setItem(r, 2, c)""",
        ),
        (
            "save_product persists the barcode",
            """            cursor.execute(
                "INSERT INTO products (uuid, generic_molecule, brand, strength, form, "
                "regulatory_class, created_at, updated_at) VALUES (?, ?, ?, 'N/A', ?, 'OTC', 'now', 'now')",
                (
                    p_uuid,
                    self.generic_in.text().upper(),
                    self.brand_in.text().upper(),
                    self.form_in.currentText(),
                ),
            )""",
            """            cursor.execute(
                "INSERT INTO products (uuid, generic_molecule, brand, strength, form, barcode, "
                "regulatory_class, created_at, updated_at) VALUES (?, ?, ?, 'N/A', ?, ?, 'OTC', 'now', 'now')",
                (
                    p_uuid,
                    self.generic_in.text().upper(),
                    self.brand_in.text().upper(),
                    self.form_in.currentText(),
                    self.barcode_in.text().strip().upper() or None,
                ),
            )""",
        ),
        (
            "success feedback + refocus loop; failures surface on the status label",
            """            self.db.conn.commit()
            self.refresh_list()
            self.generic_in.clear()
            self.brand_in.clear()
        except Exception as e:
            print(e)""",
            """            self.db.conn.commit()
            self.refresh_list()
            self.status_lbl.setText(f"ADDED  ·  {self.generic_in.text().upper()}")
            self.status_lbl.setStyleSheet(
                f"color: {COLOR_OK}; font-size: 11px; font-weight: 800; "
                "letter-spacing: 0.08em; padding-top: 6px;"
            )
            self.generic_in.clear()
            self.brand_in.clear()
            self.barcode_in.clear()
            self.barcode_in.setFocus()
        except Exception as e:
            self.status_lbl.setText(str(e))
            self.status_lbl.setStyleSheet(
                f"color: {COLOR_DANGER}; font-size: 11px; font-weight: 800; "
                "letter-spacing: 0.08em; padding-top: 6px;"
            )""",
        ),
    ]),
    ("sentinel/ui/pos.py", [
        (
            "POS search matches an exact barcode too (scanner at the till)",
            """        cursor.execute(
            "SELECT p.id, p.generic_molecule, p.form, "
            "(SELECT cost_minor_per_unit FROM stock_ledger WHERE product_id = p.id "
            "ORDER BY event_seq DESC LIMIT 1) as wac FROM products p "
            "WHERE p.generic_molecule LIKE ?",
            (f"%{txt}%",),
        )""",
            """        cursor.execute(
            "SELECT p.id, p.generic_molecule, p.form, "
            "(SELECT cost_minor_per_unit FROM stock_ledger WHERE product_id = p.id "
            "ORDER BY event_seq DESC LIMIT 1) as wac FROM products p "
            "WHERE p.generic_molecule LIKE ? OR p.barcode = ?",
            (f"%{txt}%", txt),
        )""",
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
        tmp = path + ".ux017.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    print("[DONE] Patch applied.")
    print("Next: python3 -m py_compile sentinel/db/schema.py sentinel/db/manager.py sentinel/ui/registry.py sentinel/ui/pos.py")


if __name__ == "__main__":
    main()
