import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QHeaderView, 
                             QComboBox, QFormLayout, QTableWidgetItem)
from sentinel.ui.components import GLOBAL_STYLE, IndustrialButton, TechnicalCard, SectionLabel

class ProductRegistry(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setWindowTitle("REGISTRY_BLUEPRINT")
        self.setFixedSize(1000, 700)
        self.setStyleSheet(GLOBAL_STYLE)

        l = QVBoxLayout(self); l.setContentsMargins(30,30,30,30)
        l.addWidget(SectionLabel("Product Registry & Blueprinting"))

        content = QHBoxLayout()
        form_card = TechnicalCard(); fl = QFormLayout(form_card); fl.setContentsMargins(20,20,20,20)
        self.generic_in = QLineEdit(); self.brand_in = QLineEdit()
        self.form_in = QComboBox(); self.form_in.addItems(["CAPSULE", "SYRUP", "STRIP", "PILL"])
        
        fl.addRow("GENERIC_NAME", self.generic_in)
        fl.addRow("BRAND_NAME", self.brand_in)
        fl.addRow("DOSAGE_FORM", self.form_in)
        
        self.save_btn = IndustrialButton("Commit_to_Ledger")
        self.save_btn.clicked.connect(self.save_product)
        fl.addRow(self.save_btn)
        
        content.addWidget(form_card, 2)

        self.table = QTableWidget(0, 2); self.table.setHorizontalHeaderLabels(["ITEM", "FORM"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        content.addWidget(self.table, 3)
        
        l.addLayout(content); self.refresh_list()

    def refresh_list(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT generic_molecule, form FROM products")
        prods = cursor.fetchall(); self.table.setRowCount(0)
        for p in prods:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(p[0])); self.table.setItem(r, 1, QTableWidgetItem(p[1]))

    def save_product(self):
        cursor = self.db.conn.cursor()
        try:
            p_uuid = str(uuid.uuid4())
            cursor.execute("INSERT INTO products (uuid, generic_molecule, brand, strength, form, regulatory_class, created_at, updated_at) VALUES (?, ?, ?, 'N/A', ?, 'OTC', 'now', 'now')", 
                         (p_uuid, self.generic_in.text().upper(), self.brand_in.text().upper(), self.form_in.currentText()))
            prod_id = cursor.lastrowid
            cursor.execute("INSERT INTO product_versions (product_id, version_label, units_per_strip, strips_per_box, units_per_box, effective_date, created_at) VALUES (?, 'V1', 10, 10, 100, 'now', 'now')", (prod_id,))
            self.db.conn.commit(); self.refresh_list(); self.generic_in.clear(); self.brand_in.clear()
        except Exception as e: print(e)
