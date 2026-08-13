import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QGridLayout, QHeaderView, QTableWidgetItem, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence
from sentinel.ui.registry import ProductRegistry

class BrutalistPOS(QWidget):
    def __init__(self, db_manager, user_id, user_name):
        super().__init__()
        self.db = db_manager
        self.user_id = user_id
        self.user_name = user_name
        self.current_uom = "UNIT"
        
        self.setWindowTitle(f"SENTINEL_CONSOLE // OPERATOR_{user_name.upper()}")
        self.showMaximized()
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        self.master_layout = QVBoxLayout(self)
        self.master_layout.setContentsMargins(10, 10, 10, 10)
        self.master_layout.setSpacing(0)

        self.outer_frame = QFrame()
        self.outer_frame.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        self.main_layout = QVBoxLayout(self.outer_frame)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Top Bar
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(50)
        self.top_bar.setStyleSheet("border-bottom: 2px solid black;")
        tb_layout = QHBoxLayout(self.top_bar)
        self.logo = QLabel(f"➔ PHARMACY_SENTINEL / BATCH_MODE: {self.current_uom}")
        self.logo.setStyleSheet("font-weight: 900; font-size: 14px; color: black;")
        tb_layout.addWidget(self.logo)
        tb_layout.addStretch()
        self.main_layout.addWidget(self.top_bar)

        # 2. Content
        self.content_area = QHBoxLayout()
        self.content_area.setSpacing(0)

        # LEFT: Search & Cart
        self.left_pane = QFrame()
        self.left_pane.setFixedWidth(400)
        self.left_pane.setStyleSheet("border-right: 2px solid black;")
        lp_layout = QVBoxLayout(self.left_pane)
        
        lp_layout.addWidget(QLabel("SEARCH_INPUT"))
        self.search_box = QLineEdit()
        self.search_box.setStyleSheet("border: 2px solid black; font-size: 18px; padding: 10px;")
        self.search_box.textChanged.connect(self.run_search)
        lp_layout.addWidget(self.search_box)
        
        self.search_results = QTableWidget(0, 2)
        self.search_results.setHorizontalHeaderLabels(["PRODUCT", "PRICE"])
        self.search_results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.search_results.setFixedHeight(200)
        self.search_results.setStyleSheet("border: 1px solid black;")
        lp_layout.addWidget(self.search_results)
        
        lp_layout.addWidget(QLabel("TRANSACTION_LOG"))
        self.cart = QTableWidget(0, 3)
        self.cart.setHorizontalHeaderLabels(["ITEM", "QTY", "TOTAL"])
        self.cart.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lp_layout.addWidget(self.cart)
        
        # CENTER: Visualizer
        self.center_pane = QFrame()
        self.center_pane.setStyleSheet("border-right: 2px solid black; background-color: #e0e0e0;")
        cp_layout = QVBoxLayout(self.center_pane)
        cp_layout.setAlignment(Qt.AlignCenter)
        self.viz_label = QLabel("SYSTEM_READY")
        self.viz_label.setStyleSheet("font-size: 24px; font-weight: 900; color: #666;")
        cp_layout.addWidget(self.viz_label)
        self.uom_tag = QLabel(self.current_uom)
        self.uom_tag.setStyleSheet("background-color: black; color: #FF4500; font-size: 40px; font-weight: 900; padding: 20px;")
        cp_layout.addWidget(self.uom_tag)

        # RIGHT: Totals
        self.right_pane = QFrame()
        self.right_pane.setFixedWidth(300)
        rp_layout = QVBoxLayout(self.right_pane)
        rp_layout.addWidget(QLabel("TOTAL_GHS"))
        self.total_display = QLabel("0.00")
        self.total_display.setStyleSheet("font-size: 60px; font-weight: 900; border: 2px solid black; padding: 10px; background: white;")
        rp_layout.addWidget(self.total_display)
        rp_layout.addStretch()
        self.checkout_btn = QPushButton("PROCESS_SALE")
        self.checkout_btn.setFixedHeight(80)
        self.checkout_btn.setStyleSheet("background-color: #FF4500; font-size: 20px; font-weight: bold; border: 2px solid black;")
        rp_layout.addWidget(self.checkout_btn)

        self.content_area.addWidget(self.left_pane)
        self.content_area.addWidget(self.center_pane)
        self.content_area.addWidget(self.right_pane)
        self.main_layout.addLayout(self.content_area)

        # FOOTER
        self.footer = QFrame()
        self.footer.setFixedHeight(40)
        self.footer.setStyleSheet("border-top: 2px solid black; background: black;")
        f_layout = QHBoxLayout(self.footer)
        f_label = QLabel("F2:SEARCH | F4:CYCLE_UOM | F12:REGISTRY | F10:LOCK")
        f_label.setStyleSheet("color: white; font-size: 10px;")
        f_layout.addWidget(f_label)
        self.main_layout.addWidget(self.footer)

        self.master_layout.addWidget(self.outer_frame)
        
        # Shortcuts
        QShortcut(QKeySequence("F4"), self, self.cycle_uom)
        QShortcut(QKeySequence("F12"), self, self.open_registry)

    def open_registry(self):
        self.reg = ProductRegistry(self.db)
        self.reg.show()

    def cycle_uom(self):
        order = ["UNIT", "STRIP", "BOX"]
        idx = (order.index(self.current_uom) + 1) % 3
        self.current_uom = order[idx]
        self.uom_tag.setText(self.current_uom)

    def run_search(self):
        text = self.search_box.text()
        if len(text) < 2: return
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT generic_molecule, brand, form FROM products WHERE generic_molecule LIKE ?", (f"%{text}%",))
        results = cursor.fetchall()
        self.search_results.setRowCount(0)
        for r in results:
            row = self.search_results.rowCount()
            self.search_results.insertRow(row)
            self.search_results.setItem(row, 0, QTableWidgetItem(f"{r[0]} ({r[1]})"))
            self.search_results.setItem(row, 1, QTableWidgetItem(r[2]))
