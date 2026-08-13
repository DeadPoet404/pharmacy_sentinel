import sys
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QPushButton, QComboBox, 
                             QFormLayout, QMessageBox)
from PySide6.QtCore import Qt
from sentinel.logic.pricing import calculate_wac
from sentinel.logic.inventory import InventoryController

class BatchIngest(QWidget):
    def __init__(self, db_manager, device_id, on_complete=None):
        super().__init__()
        self.db = db_manager
        self.inv = InventoryController(db_manager, device_id)
        self.on_complete = on_complete
        
        self.setWindowTitle("BATCH_INGEST_CONTROL")
        self.setFixedSize(500, 600)
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        layout = QVBoxLayout(self)
        header = QLabel("➔ STOCK_IN / BATCH_INITIALIZATION")
        header.setStyleSheet("background-color: black; color: #FF4500; padding: 5px; font-weight: bold;")
        layout.addWidget(header)

        self.form_card = QFrame()
        self.form_card.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        form = QFormLayout(self.form_card)
        form.setSpacing(15)

        self.prod_selector = QComboBox()
        self.refresh_products()
        
        self.batch_in = QLineEdit()
        self.expiry_in = QLineEdit()
        self.qty_in = QLineEdit()
        self.cost_in = QLineEdit()

        form.addRow("TARGET_PRODUCT:", self.prod_selector)
        form.addRow("BATCH_ID:", self.batch_in)
        form.addRow("EXPIRY (YYYY-MM-DD):", self.expiry_in)
        form.addRow("QTY (UNITS):", self.qty_in)
        form.addRow("UNIT_COST (GHS):", self.cost_in)

        self.commit_btn = QPushButton("EXECUTE_INGEST ➔")
        self.commit_btn.setFixedHeight(60)
        self.commit_btn.setStyleSheet("background-color: #FF4500; border: 2px solid black; font-weight: bold;")
        self.commit_btn.clicked.connect(self.process_ingest)
        form.addRow(self.commit_btn)

        layout.addWidget(self.form_card)

    def refresh_products(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, generic_molecule, brand FROM products")
        for row in cursor.fetchall():
            self.prod_selector.addItem(f"{row[1]} ({row[2]})", row[0])

    def process_ingest(self):
        try:
            prod_id = self.prod_selector.currentData()
            qty = int(self.qty_in.text())
            cost_ghs = float(self.cost_in.text())
            cost_p = int(cost_ghs * 100)

            cursor = self.db.conn.cursor()
            
            # 1. Find Current Version
            cursor.execute("SELECT id FROM product_versions WHERE product_id = ? AND is_current = 1", (prod_id,))
            res = cursor.fetchone()
            if not res:
                raise ValueError("Product missing version mapping. Re-add product in Registry.")
            version_id = res[0]

            # 2. Calculate WAC
            on_hand = self.inv.get_on_hand(prod_id)
            cursor.execute("SELECT cost_minor_per_unit FROM stock_ledger WHERE product_id = ? ORDER BY event_seq DESC LIMIT 1", (prod_id,))
            ledger_res = cursor.fetchone()
            old_wac = ledger_res[0] if ledger_res else cost_p
            new_wac = calculate_wac(on_hand, old_wac, qty, cost_p)

            # 3. Insert Batch
            b_uuid = str(uuid.uuid4())
            cursor.execute("INSERT INTO batches (uuid, product_version_id, batch_code, expiry_date, received_at) VALUES (?, ?, ?, ?, 'now')", 
                         (b_uuid, version_id, self.batch_in.text(), self.expiry_in.text()))
            batch_id = cursor.lastrowid

            # 4. Record Ledger
            self.inv.record_movement(prod_id, qty, 'PURCHASE_IN', 'po', 0, batch_id, new_wac)
            
            self.db.conn.commit()
            QMessageBox.information(self, "SUCCESS", "STOCK INGESTED")
            self.close()
            if self.on_complete: self.on_complete()

        except Exception as e:
            QMessageBox.critical(self, "INGEST_ERROR", str(e))
