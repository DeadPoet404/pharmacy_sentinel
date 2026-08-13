import sys
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QHeaderView, 
                             QTableWidgetItem, QPushButton, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap
from sentinel.ui.registry import ProductRegistry
from sentinel.ui.purchasing import BatchIngest
from sentinel.ui.checkout import SettlementUI
from sentinel.ui.zreport import ZReportCeremony
from sentinel.logic.sales import SalesController

class BrutalistPOS(QWidget):
    def __init__(self, db_manager, user_id, user_name, session_id):
        super().__init__()
        self.db = db_manager
        self.user_id = user_id
        self.session_id = session_id
        self.user_name = user_name
        self.current_uom = "UNIT"
        self.cart_items = []
        self.device_id = "DEV-001"
        self.sales_ctrl = SalesController(db_manager, self.device_id)
        self.assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        
        self.setWindowTitle("SENTINEL_CONSOLE")
        self.showMaximized()
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        master = QVBoxLayout(self)
        frame = QFrame(); frame.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        layout = QVBoxLayout(frame); layout.setContentsMargins(0,0,0,0); layout.setSpacing(0)

        # UI Construction (Same as before)
        top = QFrame(); top.setFixedHeight(50); top.setStyleSheet("border-bottom: 2px solid black; background: white;")
        top_layout = QHBoxLayout(top)
        top_layout.addWidget(QLabel(f"➔ SENTINEL_CONSOLE // OP: {user_name.upper()} // SESS: {session_id}"))
        layout.addWidget(top)

        content = QHBoxLayout()
        left = QFrame(); left.setFixedWidth(400); left.setStyleSheet("border-right: 2px solid black;")
        l_layout = QVBoxLayout(left)
        self.search_box = QLineEdit(); self.search_box.setPlaceholderText("SEARCH_PRODUCT (F2)")
        self.search_box.setStyleSheet("border: 2px solid black; padding: 10px; background: white;")
        self.search_box.textChanged.connect(self.run_search); l_layout.addWidget(self.search_box)
        self.search_table = QTableWidget(0, 3); self.search_table.setHorizontalHeaderLabels(["PRODUCT", "PRICE", "STOCK"])
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.search_table.itemDoubleClicked.connect(self.select_item); l_layout.addWidget(self.search_table)
        self.cart_table = QTableWidget(0, 2); self.cart_table.setHorizontalHeaderLabels(["ITEM", "TOTAL"])
        l_layout.addWidget(self.cart_table); content.addWidget(left)

        center = QFrame(); center.setStyleSheet("background-color: #e0e0e0; border-right: 2px solid black;")
        c_layout = QVBoxLayout(center); c_layout.setAlignment(Qt.AlignCenter)
        self.viz_frame = QFrame(); self.viz_frame.setFixedSize(500, 500); self.viz_frame.setStyleSheet("border: 2px dashed black;")
        vf_layout = QVBoxLayout(self.viz_frame); self.img_label = QLabel(); self.img_label.setAlignment(Qt.AlignCenter); vf_layout.addWidget(self.img_label)
        self.name_label = QLabel("SYSTEM_READY"); self.name_label.setAlignment(Qt.AlignCenter); vf_layout.addWidget(self.name_label)
        c_layout.addWidget(self.viz_frame)
        self.uom_tag = QLabel(self.current_uom); self.uom_tag.setStyleSheet("background: black; color: #FF4500; font-size: 40px; font-weight: 900; padding: 10px 30px;")
        c_layout.addWidget(self.uom_tag); content.addWidget(center)

        right = QFrame(); right.setFixedWidth(300); r_layout = QVBoxLayout(right)
        self.total_lbl = QLabel("0.00"); self.total_lbl.setStyleSheet("font-size: 60px; font-weight: 900; border: 2px solid black; background: white; padding: 10px;")
        r_layout.addWidget(self.total_lbl); r_layout.addStretch()
        content.addWidget(right); layout.addLayout(content)

        footer = QFrame(); footer.setFixedHeight(40); footer.setStyleSheet("border-top: 2px solid black; background: black;")
        f_layout = QHBoxLayout(footer)
        f_label = QLabel("F2:SEARCH | F3:STOCK_IN | F4:UOM | F8:CHECKOUT | F11:Z_REPORT | F12:REGISTRY")
        f_label.setStyleSheet("color: white; font-size: 10px;")
        f_layout.addWidget(f_label); layout.addWidget(footer)
        master.addWidget(frame)

        QShortcut(QKeySequence("F8"), self, self.open_checkout)
        QShortcut(QKeySequence("F11"), self, self.open_zreport)
        QShortcut(QKeySequence("F3"), self, self.open_ingest)
        QShortcut(QKeySequence("F12"), self, self.open_reg)

    def open_reg(self): self.reg = ProductRegistry(self.db); self.reg.show()
    def open_ingest(self): self.ingest = BatchIngest(self.db, self.device_id, on_complete=self.run_search); self.ingest.show()

    def run_search(self):
        txt = self.search_box.text()
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT p.id, p.generic_molecule, p.form, 
            (SELECT SUM(qty_delta_atomic) FROM stock_ledger WHERE product_id = p.id) as stock,
            (SELECT cost_minor_per_unit FROM stock_ledger WHERE product_id = p.id ORDER BY event_seq DESC LIMIT 1) as wac
            FROM products p WHERE p.generic_molecule LIKE ?
        """, (f"%{txt}%",))
        res = cursor.fetchall()
        self.search_table.setRowCount(0)
        for r in res:
            row = self.search_table.rowCount(); self.search_table.insertRow(row)
            self.search_table.setItem(row, 0, QTableWidgetItem(r[1]))
            price = (r[4] / 100) if r[4] else 0.0
            self.search_table.setItem(row, 1, QTableWidgetItem(f"{price:.2f}"))
            self.search_table.setItem(row, 2, QTableWidgetItem(str(r[3] or 0)))
            self.search_table.item(row, 0).setData(Qt.UserRole, r[0]); self.search_table.item(row, 0).setData(Qt.UserRole + 1, r[2]); self.search_table.item(row, 0).setData(Qt.UserRole + 2, price)

    def select_item(self, item):
        row = item.row(); it = self.search_table.item(row, 0); p_id, form, price = it.data(Qt.UserRole), it.data(Qt.UserRole + 1).lower(), it.data(Qt.UserRole + 2)
        self.cart_items.append({"id": p_id, "name": it.text(), "qty": 1, "price": price}); self.update_ui(it.text(), form)

    def update_ui(self, name, form):
        img_path = os.path.join(self.assets_dir, f"{form}.webp")
        if os.path.exists(img_path): self.img_label.setPixmap(QPixmap(img_path).scaled(450, 450, Qt.KeepAspectRatio)); self.viz_frame.setStyleSheet("border: 2px solid black; background: white;")
        self.name_label.setText(name.upper()); self.cart_table.setRowCount(0); total = 0.0
        for i in self.cart_items:
            r = self.cart_table.rowCount(); self.cart_table.insertRow(r); self.cart_table.setItem(r, 0, QTableWidgetItem(i['name'])); self.cart_table.setItem(r, 1, QTableWidgetItem(f"{i['price']:.2f}")); total += i['price']
        self.total_lbl.setText(f"{total:.2f}")

    def open_checkout(self):
        total = float(self.total_lbl.text())
        if total <= 0: return
        self.checkout_ui = SettlementUI(total, self.finalize_sale); self.checkout_ui.show()

    def finalize_sale(self, method, tendered):
        success = self.sales_ctrl.commit_sale(self.user_id, self.session_id, self.cart_items, float(self.total_lbl.text()), method, tendered)
        if success:
            QMessageBox.information(self, "SUCCESS", "SALE_COMPLETE")
            self.cart_items = []; self.update_ui("SYSTEM_READY", "idle"); self.total_lbl.setText("0.00"); self.search_box.clear()
        else: QMessageBox.critical(self, "ERROR", "TRANSACTION_FAILED")

    def open_zreport(self):
        self.z_ui = ZReportCeremony(self.db, self.session_id, self.user_id, self.device_id)
        self.z_ui.show()
