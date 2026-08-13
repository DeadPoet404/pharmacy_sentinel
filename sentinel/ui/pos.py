import sys
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QHeaderView, 
                             QTableWidgetItem, QMessageBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap
from sentinel.ui.components import (GLOBAL_STYLE, IndustrialButton, SectionLabel, TechnicalCard, COLOR_ACCENT, apply_deep_elevation)
from sentinel.ui.registry import ProductRegistry
from sentinel.ui.purchasing import BatchIngest
from sentinel.ui.checkout import SettlementUI
from sentinel.logic.sales import SalesController

class BrutalistPOS(QWidget):
    def __init__(self, db_manager, user_id, user_name, session_id):
        super().__init__()
        self.db, self.user_id, self.session_id, self.user_name = db_manager, user_id, session_id, user_name
        self.current_uom = "UNIT"
        self.cart_items = []
        self.sales_ctrl = SalesController(db_manager, "DEV-001")
        self.assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
        
        self.setWindowTitle("SENTINEL")
        self.showMaximized()
        self.setStyleSheet(GLOBAL_STYLE)

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0,0,0,0)
        self.root.setSpacing(0)

        # 1. TOP NAV
        nav = QFrame()
        nav.setFixedHeight(60)
        nav.setStyleSheet("background: white; border-bottom: 1px solid #E2E8F0;")
        l = QHBoxLayout(nav); l.setContentsMargins(30, 0, 30, 0)
        l.addWidget(QLabel("➔ SENTINEL_SYSTEM", styleSheet="font-weight: 900; font-size: 14px; background: transparent;"))
        l.addStretch()
        l.addWidget(QLabel(f"OP_{self.user_name} // SESS_{self.session_id}", styleSheet="font-weight: bold; color: #64748b; font-size: 11px; background: transparent;"))
        self.root.addWidget(nav)

        # 2. WORKSPACE
        self.workspace = QHBoxLayout()
        self.workspace.setContentsMargins(40, 40, 40, 40)
        self.workspace.setSpacing(50)
        
        # LEFT: LEDGER (Floating Card)
        self.setup_ledger()
        
        # RIGHT: INTERACTION (Floating Modules)
        self.setup_interaction_pane()
        
        self.root.addLayout(self.workspace)
        self.setup_shortcuts()

    def setup_ledger(self):
        col = QVBoxLayout()
        col.addWidget(SectionLabel("Transaction_Ledger"))
        
        self.cart_table = QTableWidget(0, 3)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setHorizontalHeaderLabels(["ITEM", "QTY", "TOTAL"])
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        apply_deep_elevation(self.cart_table, "MEDIUM")
        col.addWidget(self.cart_table)
        
        self.total_card = QFrame()
        self.total_card.setStyleSheet("background: black; border-radius: 4px;")
        self.total_card.setFixedHeight(120)
        apply_deep_elevation(self.total_card, "HIGH")
        tl = QVBoxLayout(self.total_card)
        self.total_lbl = QLabel("0.00")
        self.total_lbl.setStyleSheet("color: white; font-size: 70px; font-weight: 900; letter-spacing: -4px; background: transparent;")
        self.total_lbl.setAlignment(Qt.AlignRight)
        tl.addWidget(self.total_lbl)
        col.addWidget(self.total_card)
        self.workspace.addLayout(col, 2)

    def setup_interaction_pane(self):
        col = QVBoxLayout()
        col.setSpacing(30)
        
        # Search Box with Elevation
        self.search_box = QLineEdit(); self.search_box.setPlaceholderText("QUERY...")
        apply_deep_elevation(self.search_box, "MEDIUM")
        col.addWidget(self.search_box)

        # Content Row
        mid_row = QHBoxLayout(); mid_row.setSpacing(30)
        self.search_table = QTableWidget(0, 2)
        self.search_table.setHorizontalHeaderLabels(["PRODUCT", "PRICE"])
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.search_table.itemDoubleClicked.connect(self.select_item)
        apply_deep_elevation(self.search_table, "MEDIUM")
        mid_row.addWidget(self.search_table, 3)
        
        self.viz_card = TechnicalCard() # TechnicalCard already has high elevation
        self.viz_card.setFixedSize(380, 380)
        vl = QVBoxLayout(self.viz_card)
        self.viz_img = QLabel(); self.viz_img.setAlignment(Qt.AlignCenter); self.viz_img.setStyleSheet("background: transparent;")
        self.mode_tag = QLabel(self.current_uom)
        self.mode_tag.setStyleSheet(f"font-size: 40px; font-weight: 900; color: {COLOR_ACCENT}; background: transparent;")
        self.mode_tag.setAlignment(Qt.AlignCenter)
        vl.addWidget(self.viz_img); vl.addWidget(self.mode_tag)
        mid_row.addWidget(self.viz_card, 2)
        col.addLayout(mid_row)
        
        # Action Row
        bot_row = QHBoxLayout()
        btn_in = IndustrialButton("F3_Stock", primary=False)
        btn_in.clicked.connect(self.open_ingest)
        btn_reg = IndustrialButton("F12_Reg", primary=False)
        btn_reg.clicked.connect(self.open_reg)
        bot_row.addWidget(btn_in); bot_row.addWidget(btn_reg); bot_row.addStretch()
        
        self.pay_btn = IndustrialButton("F8_Finalize")
        self.pay_btn.setFixedWidth(250); self.pay_btn.setFixedHeight(60)
        self.pay_btn.clicked.connect(self.open_checkout)
        bot_row.addWidget(self.pay_btn)
        col.addLayout(bot_row)
        
        self.workspace.addLayout(col, 3)
        self.search_box.textChanged.connect(self.run_search)

    def select_item(self, item):
        row = item.row(); it = self.search_table.item(row, 0)
        p_id, form, price = it.data(Qt.UserRole), it.data(Qt.UserRole+1).lower(), it.data(Qt.UserRole+2)
        img_path = os.path.join(self.assets_dir, f"{form}.webp")
        if os.path.exists(img_path):
            self.viz_img.setPixmap(QPixmap(img_path).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.cart_items.append({"id": p_id, "name": it.text(), "qty": 1, "price": price})
        self.update_ledger()

    def run_search(self):
        txt = self.search_box.text()
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT p.id, p.generic_molecule, p.form, (SELECT cost_minor_per_unit FROM stock_ledger WHERE product_id = p.id ORDER BY event_seq DESC LIMIT 1) as wac FROM products p WHERE p.generic_molecule LIKE ?", (f"%{txt}%",))
        res = cursor.fetchall(); self.search_table.setRowCount(0)
        for r in res:
            row = self.search_table.rowCount(); self.search_table.insertRow(row)
            self.search_table.setItem(row, 0, QTableWidgetItem(r[1].upper()))
            price = (r[3] / 100) if r[3] else 0.0; self.search_table.setItem(row, 1, QTableWidgetItem(f"{price:.2f}"))
            self.search_table.item(row, 0).setData(Qt.UserRole, r[0])
            self.search_table.item(row, 0).setData(Qt.UserRole + 1, r[2])
            self.search_table.item(row, 0).setData(Qt.UserRole + 2, price)

    def update_ledger(self):
        self.cart_table.setRowCount(0); total = 0.0
        for i in self.cart_items:
            r = self.cart_table.rowCount(); self.cart_table.insertRow(r)
            self.cart_table.setItem(r, 0, QTableWidgetItem(i['name']))
            self.cart_table.setItem(r, 1, QTableWidgetItem("1"))
            self.cart_table.setItem(r, 2, QTableWidgetItem(f"{i['price']:.2f}"))
            total += i['price']
        self.total_lbl.setText(f"{total:.2f}")

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F2"), self, self.search_box.setFocus)
        QShortcut(QKeySequence("F4"), self, self.cycle_uom)
        QShortcut(QKeySequence("F8"), self, self.open_checkout)

    def cycle_uom(self):
        order = ["UNIT", "STRIP", "BOX"]
        idx = (order.index(self.current_uom) + 1) % 3
        self.current_uom = order[idx]; self.mode_tag.setText(self.current_uom)

    def open_reg(self): self.reg = ProductRegistry(self.db); self.reg.show()
    def open_ingest(self): self.ingest = BatchIngest(self.db, "DEV-001", on_complete=self.run_search); self.ingest.show()
    def open_checkout(self):
        t = float(self.total_lbl.text()); self.checkout_ui = SettlementUI(t, self.finalize_sale); self.checkout_ui.show()
    def finalize_sale(self, method, tendered):
        if self.sales_ctrl.commit_sale(self.user_id, self.session_id, self.cart_items, float(self.total_lbl.text()), method, tendered):
            QMessageBox.information(self, "SUCCESS", "COMMITTED"); self.cart_items = []; self.update_ledger(); self.viz_img.clear()
