import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QTableWidget, QGridLayout, 
                             QHeaderView, QTableWidgetItem, QPushButton)
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
        self.cart_items = [] # Tracks [name, qty, price_minor]
        
        self.setWindowTitle(f"SENTINEL_CONSOLE // OPERATOR_{user_name.upper()}")
        self.showMaximized()
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        # Layout Setup
        self.master_layout = QVBoxLayout(self)
        self.master_layout.setContentsMargins(10, 10, 10, 10)
        self.master_layout.setSpacing(0)

        self.outer_frame = QFrame()
        self.outer_frame.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        self.main_layout = QVBoxLayout(self.outer_frame)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Header
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(50)
        self.top_bar.setStyleSheet("border-bottom: 2px solid black;")
        tb_layout = QHBoxLayout(self.top_bar)
        self.logo = QLabel(f"➔ PHARMACY_SENTINEL // MODE: {self.current_uom}")
        self.logo.setStyleSheet("font-weight: 900; font-size: 14px; color: black;")
        tb_layout.addWidget(self.logo)
        tb_layout.addStretch()
        self.main_layout.addWidget(self.top_bar)

        # 2. Triple-Pane Grid
        self.content_area = QHBoxLayout()
        self.content_area.setSpacing(0)

        # LEFT: SEARCH & CART
        self.left_pane = QFrame()
        self.left_pane.setFixedWidth(450)
        self.left_pane.setStyleSheet("border-right: 2px solid black;")
        lp_layout = QVBoxLayout(self.left_pane)
        
        lp_layout.addWidget(QLabel("PRODUCT_SEARCH (F2)"))
        self.search_box = QLineEdit()
        self.search_box.setStyleSheet("border: 2px solid black; font-size: 18px; padding: 10px; background: white;")
        self.search_box.textChanged.connect(self.run_search)
        lp_layout.addWidget(self.search_box)
        
        self.search_results = QTableWidget(0, 3)
        self.search_results.setHorizontalHeaderLabels(["PRODUCT", "FORM", "ADD"])
        self.search_results.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.search_results.setFixedHeight(250)
        self.search_results.setStyleSheet("border: 1px solid black; background: #eee;")
        self.search_results.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_results.itemDoubleClicked.connect(self.add_selected_to_cart)
        lp_layout.addWidget(self.search_results)
        
        lp_layout.addWidget(QLabel("TRANSACTION_LEDGER"))
        self.cart_table = QTableWidget(0, 3)
        self.cart_table.setHorizontalHeaderLabels(["ITEM", "QTY", "TOTAL"])
        self.cart_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cart_table.setStyleSheet("border: 2px solid black; background: white;")
        lp_layout.addWidget(self.cart_table)
        
        # CENTER: ISOMETRIC VISUALIZER
        self.center_pane = QFrame()
        self.center_pane.setStyleSheet("border-right: 2px solid black; background-color: #e0e0e0;")
        cp_layout = QVBoxLayout(self.center_pane)
        cp_layout.setAlignment(Qt.AlignCenter)
        
        self.viz_container = QFrame()
        self.viz_container.setFixedSize(300, 300)
        self.viz_container.setStyleSheet("border: 2px dashed #999; background: #dcdcdc;")
        self.viz_layout = QVBoxLayout(self.viz_container)
        self.viz_label = QLabel("NO_ACTIVE_SELECTION")
        self.viz_label.setAlignment(Qt.AlignCenter)
        self.viz_label.setStyleSheet("font-weight: 800; color: #666;")
        self.viz_layout.addWidget(self.viz_label)
        cp_layout.addWidget(self.viz_container)
        
        self.uom_tag = QLabel(self.current_uom)
        self.uom_tag.setStyleSheet("background-color: black; color: #FF4500; font-size: 40px; font-weight: 900; padding: 20px; margin-top: 20px;")
        self.uom_tag.setAlignment(Qt.AlignCenter)
        cp_layout.addWidget(self.uom_tag)

        # RIGHT: SETTLEMENT
        self.right_pane = QFrame()
        self.right_pane.setFixedWidth(350)
        rp_layout = QVBoxLayout(self.right_pane)
        
        rp_layout.addWidget(QLabel("DUE_AMOUNT_GHS"))
        self.total_display = QLabel("0.00")
        self.total_display.setStyleSheet("font-size: 70px; font-weight: 900; border: 2px solid black; padding: 10px; background: white; color: black;")
        self.total_display.setAlignment(Qt.AlignRight)
        rp_layout.addWidget(self.total_display)
        
        rp_layout.addStretch()
        self.checkout_btn = QPushButton("PROCESS_SALE (F8)")
        self.checkout_btn.setFixedHeight(100)
        self.checkout_btn.setStyleSheet("background-color: #FF4500; font-size: 24px; font-weight: bold; border: 2px solid black;")
        rp_layout.addWidget(self.checkout_btn)

        self.content_area.addWidget(self.left_pane)
        self.content_area.addWidget(self.center_pane)
        self.content_area.addWidget(self.right_pane)
        self.main_layout.addLayout(self.content_area)

        # 3. Footer
        self.footer = QFrame()
        self.footer.setFixedHeight(40)
        self.footer.setStyleSheet("border-top: 2px solid black; background: black;")
        f_layout = QHBoxLayout(self.footer)
        f_label = QLabel("F2:SEARCH | F4:CYCLE_UOM | F8:CHECKOUT | F10:LOCK | F12:BLUEPRINT_EDITOR")
        f_label.setStyleSheet("color: white; font-size: 11px;")
        f_layout.addWidget(f_label)
        self.main_layout.addWidget(self.footer)

        self.master_layout.addWidget(self.outer_frame)
        
        # Event bindings
        QShortcut(QKeySequence("F2"), self, self.search_box.setFocus)
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
        self.logo.setText(f"➔ PHARMACY_SENTINEL // MODE: {self.current_uom}")

    def run_search(self):
        text = self.search_box.text()
        if len(text) < 2:
            self.search_results.setRowCount(0)
            return
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, generic_molecule, brand, form FROM products WHERE generic_molecule LIKE ?", (f"%{text}%",))
        results = cursor.fetchall()
        self.search_results.setRowCount(0)
        for r in results:
            row = self.search_results.rowCount()
            self.search_results.insertRow(row)
            self.search_results.setItem(row, 0, QTableWidgetItem(f"{r[1]}"))
            self.search_results.setItem(row, 1, QTableWidgetItem(r[3]))
            self.search_results.setItem(row, 2, QTableWidgetItem("➔"))

    def add_selected_to_cart(self, item):
        row = item.row()
        name = self.search_results.item(row, 0).text()
        form = self.search_results.item(row, 1).text()
        
        # 1. Update Visualizer (Brutalist style)
        self.viz_container.setStyleSheet("border: 2px solid black; background: white;")
        self.viz_label.setText(f"SELECTED:\n{form}\n[ISOMETRIC_MAP]")
        self.viz_label.setStyleSheet("font-size: 20px; font-weight: 900; color: #FF4500;")
        
        # 2. Add to Ledger (Simulated Price for now)
        price_ghs = 5.50
        self.cart_items.append({"name": name, "qty": 1, "price": price_ghs})
        
        self.update_cart_display()
        self.search_box.clear()
        self.search_box.setFocus()

    def update_cart_display(self):
        self.cart_table.setRowCount(0)
        total = 0.0
        for item in self.cart_items:
            row = self.cart_table.rowCount()
            self.cart_table.insertRow(row)
            self.cart_table.setItem(row, 0, QTableWidgetItem(item['name']))
            self.cart_table.setItem(row, 1, QTableWidgetItem(str(item['qty'])))
            self.cart_table.setItem(row, 2, QTableWidgetItem(f"{item['price']:.2f}"))
            total += item['price']
        
        self.total_display.setText(f"{total:.2f}")

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from sentinel.db.manager import DatabaseManager
    app = QApplication(sys.argv)
    db = DatabaseManager("sentinel.db"); db.connect(); db.initialize()
    win = BrutalistPOS(db, 1, "Operator_Ama")
    win.show()
    sys.exit(app.exec())
