import sys
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QHeaderView, 
                             QPushButton, QComboBox, QFormLayout)
from PySide6.QtCore import Qt

class ProductRegistry(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        
        self.setWindowTitle("PRODUCT_BLUEPRINT_EDITOR")
        self.setFixedSize(900, 600)
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        
        # 1. Header
        self.header = QLabel("➔ SYSTEM_REGISTRY / NEW_ENTRY")
        self.header.setStyleSheet("background-color: black; color: #FF4500; padding: 5px; font-weight: bold;")
        self.layout.addWidget(self.header)

        # 2. Main Work Area (Split Pane)
        self.work_area = QHBoxLayout()
        
        # LEFT: Form
        self.form_pane = QFrame()
        self.form_pane.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        self.form_layout = QFormLayout(self.form_pane)
        self.form_layout.setSpacing(10)

        self.generic_in = QLineEdit()
        self.brand_in = QLineEdit()
        self.strength_in = QLineEdit()
        self.form_in = QComboBox()
        self.form_in.addItems(["TABLET", "CAPSULE", "SYRUP", "OINTMENT"])
        self.class_in = QComboBox()
        self.class_in.addItems(["OTC", "POM"])

        # Packaging Logic
        self.u_per_s = QLineEdit("10")
        self.s_per_b = QLineEdit("10")

        self.form_layout.addRow("GENERIC_MOLECULE:", self.generic_in)
        self.form_layout.addRow("BRAND_NAME:", self.brand_in)
        self.form_layout.addRow("STRENGTH:", self.strength_in)
        self.form_layout.addRow("DOSAGE_FORM:", self.form_in)
        self.form_layout.addRow("REG_CLASS:", self.class_in)
        self.form_layout.addRow("UNITS_PER_STRIP:", self.u_per_s)
        self.form_layout.addRow("STRIPS_PER_BOX:", self.s_per_b)

        self.save_btn = QPushButton("COMMIT_TO_REGISTRY ➔")
        self.save_btn.setFixedHeight(50)
        self.save_btn.setStyleSheet("background-color: #FF4500; color: black; border: 2px solid black; font-weight: bold;")
        self.save_btn.clicked.connect(self.save_product)
        self.form_layout.addRow(self.save_btn)

        # RIGHT: List
        self.list_pane = QFrame()
        self.list_pane.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        self.list_layout = QVBoxLayout(self.list_pane)
        self.prod_table = QTableWidget(0, 2)
        self.prod_table.setHorizontalHeaderLabels(["PRODUCT", "FORM"])
        self.prod_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.prod_table.setStyleSheet("border: none;")
        self.list_layout.addWidget(self.prod_table)

        self.work_area.addWidget(self.form_pane, 1)
        self.work_area.addWidget(self.list_pane, 1)
        self.layout.addLayout(self.work_area)
        
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
        # 1. Insert Product
        p_uuid = str(uuid.uuid4())
        now = "now"
        cursor = self.db.conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO products (uuid, generic_molecule, brand, strength, form, regulatory_class, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (p_uuid, self.generic_in.text().upper(), self.brand_in.text().upper(), 
                  self.strength_in.text(), self.form_in.currentText(), self.class_in.currentText(), now, now))
            
            prod_id = cursor.lastrowid
            
            # 2. Insert Product Version
            u_s = int(self.u_per_s.text())
            s_b = int(self.s_per_b.text())
            cursor.execute("""
                INSERT INTO product_versions (product_id, version_label, units_per_strip, strips_per_box, units_per_box, effective_date, created_at)
                VALUES (?, 'V1_INITIAL', ?, ?, ?, ?, ?)
            """, (prod_id, u_s, s_b, u_s * s_b, now, now))
            
            self.db.conn.commit()
            self.refresh_list()
            print(f"COMMITTED: {self.brand_in.text()}")
        except Exception as e:
            print(f"REGISTRY_ERROR: {e}")

from PySide6.QtWidgets import QTableWidgetItem
