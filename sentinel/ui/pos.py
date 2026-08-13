import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap, QColor, QFont
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, SectionLabel, TechnicalCard,
    COLOR_ACCENT, COLOR_MUTED, COLOR_DIM, COLOR_SURFACE, COLOR_BORDER,
    COLOR_TEXT, COLOR_BG, apply_deep_elevation,
)
from sentinel.ui.registry import ProductRegistry
from sentinel.ui.purchasing import BatchIngest
from sentinel.ui.checkout import SettlementUI
from sentinel.logic.sales import SalesController


class BrutalistPOS(QWidget):
    def __init__(self, db_manager, user_id, user_name, session_id):
        super().__init__()
        self.db, self.user_id, self.session_id, self.user_name = (
            db_manager, user_id, session_id, user_name
        )
        self.current_uom = "UNIT"
        self.cart_items = []
        self.sales_ctrl = SalesController(db_manager, "DEV-001")
        self.assets_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

        self.setWindowTitle("SENTINEL")
        self.showMaximized()
        self.setStyleSheet(GLOBAL_STYLE)

        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.root.setSpacing(0)

        self._build_nav()

        body = QWidget()
        body.setStyleSheet(f"background: {COLOR_BG};")
        self.workspace = QHBoxLayout(body)
        self.workspace.setContentsMargins(28, 24, 28, 24)
        self.workspace.setSpacing(24)

        self.setup_ledger()
        self.setup_interaction_pane()

        self.root.addWidget(body, 1)
        self.setup_shortcuts()
        self.run_search()

    def _build_nav(self):
        nav = QFrame()
        nav.setFixedHeight(64)
        nav.setStyleSheet(f"""
            QFrame {{
                background: #0E1116;
                border: none;
                border-bottom: 1px solid {COLOR_BORDER};
            }}
        """)
        l = QHBoxLayout(nav)
        l.setContentsMargins(28, 0, 28, 0)
        l.setSpacing(16)

        mark = QLabel("●")
        mark.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 14px; background: transparent;")
        brand = QLabel("SENTINEL")
        brand.setStyleSheet(
            "font-weight: 900; font-size: 15px; letter-spacing: 0.28em; "
            "background: transparent; color: #F4F1EA;"
        )
        sub = QLabel("POINT OF SALE")
        sub.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.2em; background: transparent; padding-top: 2px;"
        )

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(mark)
        brand_row.addWidget(brand)
        brand_col.addLayout(brand_row)

        l.addLayout(brand_col)
        l.addWidget(sub)
        l.addStretch()

        chip = QFrame()
        chip.setStyleSheet(f"""
            QFrame {{
                background: #181C23;
                border: 1px solid {COLOR_BORDER};
                border-radius: 8px;
            }}
        """)
        cl = QHBoxLayout(chip)
        cl.setContentsMargins(14, 6, 14, 6)
        cl.setSpacing(18)
        op = QLabel(f"OP  {self.user_name}")
        op.setStyleSheet(f"color: {COLOR_TEXT}; font-weight: 700; font-size: 11px; letter-spacing: 0.08em;")
        sess = QLabel(f"SESS  {self.session_id}")
        sess.setStyleSheet(f"color: {COLOR_MUTED}; font-weight: 600; font-size: 11px; letter-spacing: 0.08em;")
        live = QLabel("LIVE")
        live.setStyleSheet(f"color: {COLOR_ACCENT}; font-weight: 800; font-size: 10px; letter-spacing: 0.16em;")
        cl.addWidget(op)
        cl.addWidget(sess)
        cl.addWidget(live)
        l.addWidget(chip)

        self.root.addWidget(nav)

    def setup_ledger(self):
        col = QVBoxLayout()
        col.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(SectionLabel("Transaction ledger"))
        head.addStretch()
        count = QLabel("CART")
        count.setObjectName("cartHint")
        count.setStyleSheet(f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 0.16em;")
        self.cart_count = count
        head.addWidget(count)
        col.addLayout(head)

        self.cart_table = QTableWidget(0, 3)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setHorizontalHeaderLabels(["ITEM", "QTY", "TOTAL"])
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setShowGrid(False)
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setFocusPolicy(Qt.NoFocus)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        hdr = self.cart_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(1, 72)
        self.cart_table.setColumnWidth(2, 110)
        self.cart_table.verticalHeader().setDefaultSectionSize(48)
        apply_deep_elevation(self.cart_table, "MEDIUM")
        col.addWidget(self.cart_table, 1)

        self.total_card = QFrame()
        self.total_card.setFixedHeight(132)
        self.total_card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #16120C, stop:1 #0C0D10);
                border: 1px solid {COLOR_ACCENT};
                border-radius: 14px;
            }}
        """)
        tl = QVBoxLayout(self.total_card)
        tl.setContentsMargins(22, 16, 22, 16)
        cap = QLabel("AMOUNT DUE")
        cap.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 10px; font-weight: 800; "
            "letter-spacing: 0.24em; background: transparent;"
        )
        self.total_lbl = QLabel("0.00")
        self.total_lbl.setStyleSheet(
            "color: #FFF8EC; font-size: 56px; font-weight: 800; "
            "letter-spacing: -2px; background: transparent;"
        )
        self.total_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tl.addWidget(cap)
        tl.addWidget(self.total_lbl, 1)
        col.addWidget(self.total_card)

        self.workspace.addLayout(col, 5)

    def setup_interaction_pane(self):
        col = QVBoxLayout()
        col.setSpacing(14)

        search_wrap = QFrame()
        search_wrap.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 12px;
            }}
        """)
        sw = QVBoxLayout(search_wrap)
        sw.setContentsMargins(4, 4, 4, 4)
        hint = QLabel("  F2  SEARCH CATALOG")
        hint.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.18em; padding: 8px 12px 0 8px;"
        )
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Molecule, SKU, or barcode…")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                padding: 10px 16px 16px 16px;
                font-size: 18px;
                font-weight: 500;
            }}
        """)
        sw.addWidget(hint)
        sw.addWidget(self.search_box)
        col.addWidget(search_wrap)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)

        results = QVBoxLayout()
        results.setSpacing(8)
        results.addWidget(SectionLabel("Matches"))
        self.search_table = QTableWidget(0, 2)
        self.search_table.setHorizontalHeaderLabels(["PRODUCT", "PRICE"])
        self.search_table.verticalHeader().setVisible(False)
        self.search_table.setShowGrid(False)
        self.search_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search_table.setAlternatingRowColors(True)
        self.search_table.itemDoubleClicked.connect(self.select_item)
        sh = self.search_table.horizontalHeader()
        sh.setSectionResizeMode(0, QHeaderView.Stretch)
        sh.setSectionResizeMode(1, QHeaderView.Fixed)
        self.search_table.setColumnWidth(1, 96)
        self.search_table.verticalHeader().setDefaultSectionSize(44)
        apply_deep_elevation(self.search_table, "MEDIUM")
        results.addWidget(self.search_table, 1)
        mid_row.addLayout(results, 3)

        viz_col = QVBoxLayout()
        viz_col.setSpacing(8)
        viz_col.addWidget(SectionLabel("Unit of measure"))
        self.viz_card = TechnicalCard()
        self.viz_card.setMinimumSize(260, 280)
        self.viz_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        vl = QVBoxLayout(self.viz_card)
        vl.setContentsMargins(20, 20, 20, 20)
        self.viz_img = QLabel("No item\nselected")
        self.viz_img.setAlignment(Qt.AlignCenter)
        self.viz_img.setStyleSheet(
            f"background: #0B0D10; border-radius: 10px; color: {COLOR_DIM}; "
            "font-size: 12px; letter-spacing: 0.08em;"
        )
        self.viz_img.setMinimumHeight(160)
        self.mode_tag = QLabel(self.current_uom)
        self.mode_tag.setStyleSheet(
            f"font-size: 28px; font-weight: 900; color: {COLOR_ACCENT}; "
            "background: transparent; letter-spacing: 0.18em;"
        )
        self.mode_tag.setAlignment(Qt.AlignCenter)
        hint_uom = QLabel("F4  CYCLE")
        hint_uom.setAlignment(Qt.AlignCenter)
        hint_uom.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 0.2em;"
        )
        vl.addWidget(self.viz_img, 1)
        vl.addWidget(self.mode_tag)
        vl.addWidget(hint_uom)
        viz_col.addWidget(self.viz_card, 1)
        mid_row.addLayout(viz_col, 2)

        col.addLayout(mid_row, 1)

        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)
        btn_in = IndustrialButton("F3  STOCK", primary=False)
        btn_in.clicked.connect(self.open_ingest)
        btn_reg = IndustrialButton("F12  REGISTRY", primary=False)
        btn_reg.clicked.connect(self.open_reg)
        bot_row.addWidget(btn_in)
        bot_row.addWidget(btn_reg)
        bot_row.addStretch()

        self.pay_btn = IndustrialButton("F8  FINALIZE")
        self.pay_btn.setFixedWidth(240)
        self.pay_btn.setFixedHeight(56)
        self.pay_btn.clicked.connect(self.open_checkout)
        bot_row.addWidget(self.pay_btn)
        col.addLayout(bot_row)

        self.workspace.addLayout(col, 7)
        self.search_box.textChanged.connect(self.run_search)

    def _style_item(self, item, align_right=False, muted=False):
        item.setForeground(QColor(COLOR_MUTED if muted else COLOR_TEXT))
        if align_right:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f = item.font()
        f.setWeight(QFont.DemiBold)
        item.setFont(f)

    def select_item(self, item):
        row = item.row()
        it = self.search_table.item(row, 0)
        p_id, form, price = it.data(Qt.UserRole), it.data(Qt.UserRole + 1).lower(), it.data(Qt.UserRole + 2)
        img_path = os.path.join(self.assets_dir, f"{form}.webp")
        if os.path.exists(img_path):
            self.viz_img.setPixmap(
                QPixmap(img_path).scaled(280, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
        else:
            self.viz_img.setText(it.text())
            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_TEXT}; "
                "font-size: 16px; font-weight: 700; letter-spacing: 0.04em;"
            )
        self.cart_items.append({"id": p_id, "name": it.text(), "qty": 1, "price": price})
        self.update_ledger()

    def run_search(self):
        txt = self.search_box.text()
        if not hasattr(self.db, "conn") or self.db.conn is None:
            self._demo_search(txt)
            return
        cursor = self.db.conn.cursor()
        cursor.execute(
            "SELECT p.id, p.generic_molecule, p.form, "
            "(SELECT cost_minor_per_unit FROM stock_ledger WHERE product_id = p.id "
            "ORDER BY event_seq DESC LIMIT 1) as wac FROM products p "
            "WHERE p.generic_molecule LIKE ?",
            (f"%{txt}%",),
        )
        res = cursor.fetchall()
        self._fill_search(res)

    def _demo_search(self, txt):
        catalog = [
            (1, "AMOXICILLIN", "capsule", 1850),
            (2, "PARACETAMOL", "tablet", 420),
            (3, "IBUPROFEN", "tablet", 680),
            (4, "METFORMIN", "tablet", 910),
            (5, "ATORVASTATIN", "tablet", 2140),
            (6, "OMEPRAZOLE", "capsule", 1560),
            (7, "AZITHROMYCIN", "tablet", 3200),
            (8, "CETIRIZINE", "tablet", 350),
        ]
        q = (txt or "").upper()
        res = [r for r in catalog if q in r[1]]
        self._fill_search(res)

    def _fill_search(self, res):
        self.search_table.setRowCount(0)
        for r in res:
            row = self.search_table.rowCount()
            self.search_table.insertRow(row)
            name = QTableWidgetItem(str(r[1]).upper())
            price = (r[3] / 100) if r[3] else 0.0
            price_item = QTableWidgetItem(f"{price:.2f}")
            self._style_item(name)
            self._style_item(price_item, align_right=True, muted=True)
            self.search_table.setItem(row, 0, name)
            self.search_table.setItem(row, 1, price_item)
            name.setData(Qt.UserRole, r[0])
            name.setData(Qt.UserRole + 1, r[2])
            name.setData(Qt.UserRole + 2, price)

    def update_ledger(self):
        self.cart_table.setRowCount(0)
        total = 0.0
        for i in self.cart_items:
            r = self.cart_table.rowCount()
            self.cart_table.insertRow(r)
            n = QTableWidgetItem(i["name"])
            q = QTableWidgetItem(str(i.get("qty", 1)))
            p = QTableWidgetItem(f"{i['price']:.2f}")
            self._style_item(n)
            self._style_item(q, align_right=True, muted=True)
            self._style_item(p, align_right=True)
            self.cart_table.setItem(r, 0, n)
            self.cart_table.setItem(r, 1, q)
            self.cart_table.setItem(r, 2, p)
            total += i["price"] * i.get("qty", 1)
        self.total_lbl.setText(f"{total:,.2f}")
        n = len(self.cart_items)
        self.cart_count.setText(f"{n} LINE{'S' if n != 1 else ''}")

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F2"), self, self.search_box.setFocus)
        QShortcut(QKeySequence("F4"), self, self.cycle_uom)
        QShortcut(QKeySequence("F8"), self, self.open_checkout)
        QShortcut(QKeySequence("F3"), self, self.open_ingest)
        QShortcut(QKeySequence("F12"), self, self.open_reg)

    def cycle_uom(self):
        order = ["UNIT", "STRIP", "BOX"]
        idx = (order.index(self.current_uom) + 1) % 3
        self.current_uom = order[idx]
        self.mode_tag.setText(self.current_uom)

    def open_reg(self):
        self.reg = ProductRegistry(self.db)
        self.reg.show()

    def open_ingest(self):
        self.ingest = BatchIngest(self.db, "DEV-001", on_complete=self.run_search)
        self.ingest.show()

    def open_checkout(self):
        raw = self.total_lbl.text().replace(",", "")
        t = float(raw or 0)
        self.checkout_ui = SettlementUI(t, self.finalize_sale)
        self.checkout_ui.show()

    def finalize_sale(self, method, tendered):
        if self.sales_ctrl.commit_sale(
            self.user_id, self.session_id, self.cart_items,
            float(self.total_lbl.text().replace(",", "") or 0), method, tendered,
        ):
            QMessageBox.information(self, "SUCCESS", "Sale committed.")
            self.cart_items = []
            self.update_ledger()
            self.viz_img.clear()
            self.viz_img.setText("No item\nselected")
            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_DIM}; "
                "font-size: 12px; letter-spacing: 0.08em;"
            )
