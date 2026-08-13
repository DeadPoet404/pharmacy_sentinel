import sys
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QHeaderView, 
                             QPushButton, QComboBox, QFormLayout, QTableWidgetItem)
from PySide6.QtCore import Qt

class ProductRegistry(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setWindowTitle("PRODUCT_BLUEPRINT_EDITOR")
        self.setFixedSize(900, 600)
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        layout = QVBoxLayout(self)
        header = QLabel("➔ SYSTEM_REGISTRY / NEW_ENTRY")
        header.setStyleSheet("background-color: black; color: #FF4500; padding: 5px; font-weight: bold;")
        layout.addWidget(header)

        work_area = QHBoxLayout()
        
        # LEFT: FORM
        form_pane = QFrame()
        form_pane.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        self.form_layout = QFormLayout(form_pane)
        
        self.generic_in = QLineEdit()
        self.brand_in = QLineEdit()
        self.form_in = QComboBox()
        self.form_in.addItems(["CAPSULE", "SYRUP", "STRIP", "PILL"])
        
        self.u_per_s = QLineEdit("10")
        self.s_per_b = QLineEdit("10")

        self.form_layout.addRow("GENERIC:", self.generic_in)
        self.form_layout.addRow("BRAND:", self.brand_in)
        self.form_layout.addRow("FORM (VISUAL):", self.form_in)
        self.form_layout.addRow("UNITS/STRIP:", self.u_per_s)
        self.form_layout.addRow("STRIPS/BOX:", self.s_per_b)

        save_btn = QPushButton("COMMIT_TO_REGISTRY ➔")
        save_btn.setFixedHeight(50)
        save_btn.setStyleSheet("background-color: #FF4500; border: 2px solid black; font-weight: bold;")
        save_btn.clicked.connect(self.save_product)
        self.form_layout.addRow(save_btn)

        # RIGHT: LIST
        list_pane = QFrame()
        list_pane.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        lp_layout = QVBoxLayout(list_pane)
        self.prod_table = QTableWidget(0, 2)
        self.prod_table.setHorizontalHeaderLabels(["PRODUCT", "FORM"])
        self.prod_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lp_layout.addWidget(self.prod_table)

        work_area.addWidget(form_pane, 1)
        work_area.addWidget(list_pane, 1)
        layout.addLayout(work_area)
        self.refresh_list()

    def refresh_list(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT generic_molecule, brand, form FROM products")
        prods = cursor.fetchall()
        self.prod_table.setRowCount(0)
        for p in prods:
            row = self.prod_table.rowCount()
            self.prod_table.insertRow(row)
            self.prod_table.setItem(row, 0, QTableWidgetItem(f"{p[0]} ({p[1]})"))
            self.prod_table.setItem(row, 1, QTableWidgetItem(p[2]))

    def save_product(self):
        p_uuid = str(uuid.uuid4())
        cursor = self.db.conn.cursor()
        try:
            # 1. Insert Product
            cursor.execute("""
                INSERT INTO products (uuid, generic_molecule, brand, strength, form, regulatory_class, created_at, updated_at)
                VALUES (?, ?, ?, 'N/A', ?, 'OTC', 'now', 'now')
            """, (p_uuid, self.generic_in.text().upper(), self.brand_in.text().upper(), self.form_in.currentText()))
            
            prod_id = cursor.lastrowid
            
            # 2. Insert mandatory version (Fix for Ingest Error)
            u_s = int(self.u_per_s.text())
            s_b = int(self.s_per_b.text())
            cursor.execute("""
                INSERT INTO product_versions (product_id, version_label, units_per_strip, strips_per_box, units_per_box, effective_date, created_at)
                VALUES (?, 'V1', ?, ?, ?, 'now', 'now')
            """, (prod_id, u_s, s_b, u_s * s_b))
            
            self.db.conn.commit()
            self.refresh_list()
            self.generic_in.clear()
            self.brand_in.clear()
        except Exception as e:
            print(f"REGISTRY_ERROR: {e}")
