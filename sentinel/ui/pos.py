import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QTableWidgetItem, QMessageBox, QSizePolicy,
    QApplication,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShortcut, QKeySequence, QPixmap, QColor, QFont
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, SectionLabel, TechnicalCard,
    COLOR_ACCENT, COLOR_MUTED, COLOR_DIM, COLOR_SURFACE, COLOR_BORDER,
    COLOR_TEXT, COLOR_BG, apply_deep_elevation,
    Toast,
)
from sentinel.ui.registry import ProductRegistry
from sentinel.ui.purchasing import BatchIngest
from sentinel.ui.checkout import SettlementUI
from sentinel.ui.zreport import ZReportCeremony
from sentinel.logic.sales import SalesController
from sentinel.logic.pricing import calculate_tier_prices


class CartTable(QTableWidget):
    """Cart table: qty-entry keys plus barcode-scan burst discrimination.

    Human quantity digits arrive slowly and are emitted one at a time
    through qty_key. A barcode scanner floods digits within milliseconds;
    once more than three digits accumulate they are treated as a scan and
    routed to the POS search box (scan_keys) so the scan lands in the
    product flow instead of corrupting a quantity.
    """

    qty_key = Signal(str)      # commands: DIGIT:x / ENTER / BACKSPACE / ESC
    scan_keys = Signal(str)    # detected barcode-scan digit string

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._burst = ""
        self._burst_timer = QTimer(self)
        self._burst_timer.setSingleShot(True)
        self._burst_timer.setInterval(50)
        self._burst_timer.timeout.connect(self._flush_burst)

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Return, Qt.Key_Enter):
            if self._burst:
                self.scan_keys.emit(self._burst)
                self._burst = ""
                self._burst_timer.stop()
            else:
                self.qty_key.emit("ENTER")
            event.accept()
            return
        if key == Qt.Key_Backspace:
            if self._burst:
                self._burst = self._burst[:-1]
                if not self._burst:
                    self._burst_timer.stop()
            else:
                self.qty_key.emit("BACKSPACE")
            event.accept()
            return
        if key == Qt.Key_Escape:
            if self._burst:
                self._burst = ""
                self._burst_timer.stop()
            self.qty_key.emit("ESC")
            event.accept()
            return
        if event.text().isdigit():
            self._burst += event.text()
            if len(self._burst) > 3:
                self.scan_keys.emit(self._burst)
                self._burst = ""
                self._burst_timer.stop()
            else:
                self._burst_timer.start()
            event.accept()
            return
        super().keyPressEvent(event)

    def _flush_burst(self):
        """Slow digits are human quantity entry — emit them one at a time."""
        digits = self._burst
        self._burst = ""
        for ch in digits:
            self.qty_key.emit(f"DIGIT:{ch}")


class SearchLineEdit(QLineEdit):
    """Search input that keeps focus while the POS navigates results with arrows."""

    up_pressed = Signal()
    down_pressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.up_pressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key_Down:
            self.down_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class BrutalistPOS(QWidget):
    def __init__(self, db_manager, user_id, user_name, session_id):
        super().__init__()
        self.db = db_manager
        self.user_id = user_id
        self.session_id = session_id
        self.user_name = user_name
        self.current_uom = "UNIT"
        self.qty_buffer = ""
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
        QTimer.singleShot(0, self.search_box.setFocus)
        self.toast = Toast(self)

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

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        brand_row.addWidget(mark)
        brand_row.addWidget(brand)

        l.addLayout(brand_row)
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
        op.setStyleSheet(
            f"color: {COLOR_TEXT}; font-weight: 700; font-size: 11px; letter-spacing: 0.08em;"
        )
        sess = QLabel(f"SESS  {self.session_id}")
        sess.setStyleSheet(
            f"color: {COLOR_MUTED}; font-weight: 600; font-size: 11px; letter-spacing: 0.08em;"
        )
        live = QLabel("LIVE")
        live.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-weight: 800; font-size: 10px; letter-spacing: 0.16em;"
        )
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
        self.cart_count = QLabel("CART")
        self.cart_count.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 0.16em;"
        )
        head.addWidget(self.cart_count)
        col.addLayout(head)

        self.cart_table = CartTable(0, 4)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.setHorizontalHeaderLabels(["ITEM", "UOM", "QTY", "TOTAL"])
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setShowGrid(False)
        self.cart_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cart_table.setFocusPolicy(Qt.StrongFocus)
        self.cart_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.cart_table.itemDoubleClicked.connect(self.remove_cart_line)
        self.cart_table.itemSelectionChanged.connect(self._clear_qty_buffer)
        hdr = self.cart_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.cart_table.setColumnWidth(1, 72)
        self.cart_table.setColumnWidth(2, 56)
        self.cart_table.setColumnWidth(3, 100)
        self.cart_table.verticalHeader().setDefaultSectionSize(48)
        apply_deep_elevation(self.cart_table, "MEDIUM")

        ledger_stack = QFrame()
        ledger_stack.setStyleSheet("background: transparent; border: none;")
        ls = QVBoxLayout(ledger_stack)
        ls.setContentsMargins(0, 0, 0, 0)
        ls.addWidget(self.cart_table, 1)
        self.cart_empty = QLabel("Empty  ·  type to search, ↵ adds top match  ·  ↑↓ pick  ·  Del removes  ·  +/− qty")
        self.cart_empty.setAlignment(Qt.AlignCenter)
        self.cart_empty.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 12px; letter-spacing: 0.06em; "
            "padding: 8px 0 4px 0; background: transparent;"
        )
        ls.addWidget(self.cart_empty)

        cart_ops = QHBoxLayout()
        cart_ops.setSpacing(8)
        btn_minus = IndustrialButton("−", primary=False)
        btn_plus = IndustrialButton("+", primary=False)
        btn_rm = IndustrialButton("REMOVE", primary=False)
        btn_minus.setFixedWidth(56)
        btn_plus.setFixedWidth(56)
        btn_minus.clicked.connect(lambda: self.nudge_qty(-1))
        btn_plus.clicked.connect(lambda: self.nudge_qty(1))
        btn_rm.clicked.connect(self.remove_cart_line)
        cart_ops.addWidget(btn_minus)
        cart_ops.addWidget(btn_plus)
        cart_ops.addWidget(btn_rm)
        cart_ops.addStretch()
        self.qty_hint = QLabel("F5 QTY  ·  TYPE qty ↵")
        self.qty_hint.setMinimumWidth(190)
        self.qty_hint.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.qty_hint.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 0.1em; background: transparent;"
        )
        cart_ops.addWidget(self.qty_hint)
        ls.addLayout(cart_ops)
        col.addWidget(ledger_stack, 1)

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
        self.workspace.addLayout(col, 4)

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
        hint = QLabel("  F2  SEARCH  ·  TYPE  ·  ↑↓ PICK  ·  ↵ ADD")
        hint.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; "
            "letter-spacing: 0.18em; padding: 8px 12px 0 8px;"
        )
        self.search_box = SearchLineEdit()
        self.search_box.setPlaceholderText("Molecule, SKU, or barcode…")
        self.search_box.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                padding: 10px 16px 16px 16px;
                font-size: 18px;
                font-weight: 500;
            }
        """)
        sw.addWidget(hint)
        sw.addWidget(self.search_box)
        col.addWidget(search_wrap)

        mid_row = QHBoxLayout()
        mid_row.setSpacing(16)

        results = QVBoxLayout()
        results.setSpacing(8)
        results.addWidget(SectionLabel("Matches"))
        self.search_table = QTableWidget(0, 3)
        self.search_table.setHorizontalHeaderLabels(["PRODUCT", "OH", f"PRICE / {self.current_uom}"])
        self.search_table.verticalHeader().setVisible(False)
        self.search_table.setShowGrid(False)
        self.search_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.search_table.setAlternatingRowColors(True)
        self.search_table.itemDoubleClicked.connect(self.select_item)
        self.search_table.itemActivated.connect(self.select_item)
        sh = self.search_table.horizontalHeader()
        sh.setMinimumSectionSize(80)
        sh.setSectionResizeMode(0, QHeaderView.Stretch)
        sh.setSectionResizeMode(1, QHeaderView.Fixed)
        sh.setSectionResizeMode(2, QHeaderView.Fixed)
        self.search_table.setColumnWidth(1, 92)
        self.search_table.setColumnWidth(2, 148)
        self.search_table.setTextElideMode(Qt.ElideNone)
        self.search_table.verticalHeader().setDefaultSectionSize(44)
        apply_deep_elevation(self.search_table, "MEDIUM")
        results.addWidget(self.search_table, 1)
        self.search_empty = QLabel("No molecules match")
        self.search_empty.setAlignment(Qt.AlignCenter)
        self.search_empty.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 11px; letter-spacing: 0.08em; padding-bottom: 4px;"
        )
        self.search_empty.hide()
        results.addWidget(self.search_empty)
        mid_row.addLayout(results, 5)

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
        vl.addWidget(self.viz_img, 1)
        vl.addWidget(self.mode_tag)
        uom_row = QHBoxLayout()
        uom_row.setSpacing(6)
        self.uom_btns = {}
        for label in ("UNIT", "STRIP", "BOX"):
            b = IndustrialButton(label, primary=False)
            b.setFixedHeight(40)
            b.clicked.connect(lambda checked=False, u=label: self.set_uom(u))
            uom_row.addWidget(b)
            self.uom_btns[label] = b
        vl.addLayout(uom_row)
        hint_uom = QLabel("CLICK  ·  OR F4")
        hint_uom.setAlignment(Qt.AlignCenter)
        hint_uom.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 700; letter-spacing: 0.2em;"
        )
        vl.addWidget(hint_uom)
        self._paint_uom_btns()
        viz_col.addWidget(self.viz_card, 1)
        mid_row.addLayout(viz_col, 2)
        col.addLayout(mid_row, 1)

        bot_row = QHBoxLayout()
        bot_row.setSpacing(10)
        btn_in = IndustrialButton("F3  STOCK", primary=False)
        btn_in.clicked.connect(self.open_ingest)
        btn_reg = IndustrialButton("F12  REGISTRY", primary=False)
        btn_reg.clicked.connect(self.open_reg)
        btn_z = IndustrialButton("F10  Z-REPORT", primary=False)
        btn_z.clicked.connect(self.open_zreport)
        bot_row.addWidget(btn_in)
        bot_row.addWidget(btn_reg)
        bot_row.addWidget(btn_z)
        bot_row.addStretch()

        self.pay_btn = IndustrialButton("F8  FINALIZE")
        self.pay_btn.setFixedWidth(240)
        self.pay_btn.setFixedHeight(56)
        self.pay_btn.clicked.connect(self.open_checkout)
        bot_row.addWidget(self.pay_btn)
        col.addLayout(bot_row)

        self.workspace.addLayout(col, 7)
        self.search_box.textChanged.connect(self.run_search)
        self.cart_table.qty_key.connect(self._on_cart_qty_key)
        self.cart_table.scan_keys.connect(self._on_cart_scan)
        self.search_box.returnPressed.connect(self._search_return_pressed)
        self.search_box.down_pressed.connect(lambda: self._move_search_selection(1))
        self.search_box.up_pressed.connect(lambda: self._move_search_selection(-1))

    def _style_item(self, item, align_right=False, muted=False):
        item.setForeground(QColor(COLOR_MUTED if muted else COLOR_TEXT))
        if align_right:
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        f = item.font()
        f.setWeight(QFont.DemiBold)
        item.setFont(f)

    def _pack_size(self, prod_id):
        if not hasattr(self.db, "conn") or self.db.conn is None:
            return 10, 10
        cursor = self.db.conn.cursor()
        row = None
        try:
            cursor.execute(
                "SELECT units_per_strip, strips_per_box FROM product_versions "
                "WHERE product_id = ? AND is_current = 1",
                (prod_id,),
            )
            row = cursor.fetchone()
        except Exception:
            row = None
        if not row:
            cursor.execute(
                "SELECT units_per_strip, strips_per_box FROM product_versions "
                "WHERE product_id = ? ORDER BY id DESC LIMIT 1",
                (prod_id,),
            )
            row = cursor.fetchone()
        if not row:
            return 10, 10
        return max(int(row[0] or 10), 1), max(int(row[1] or 10), 1)

    def _quote(self, wac_pesewas, ups, spb, uom=None):
        uom = uom or self.current_uom
        wac = int(wac_pesewas or 0)
        tiers = calculate_tier_prices(wac, ups, spb)
        key = uom.lower()
        pesewas = tiers.get(key, tiers["unit"])
        atoms = 1
        if uom == "STRIP":
            atoms = ups
        elif uom == "BOX":
            atoms = ups * spb
        return pesewas / 100.0, atoms, tiers

    def select_item(self, item):
        row = item.row()
        it = self.search_table.item(row, 0)
        p_id = it.data(Qt.UserRole)
        form = str(it.data(Qt.UserRole + 1) or "pill").lower()
        price = it.data(Qt.UserRole + 2) or 0.0
        atoms = it.data(Qt.UserRole + 3) or 1
        form_key = {
            "pill": "pill", "tablet": "pill", "pills": "pill",
            "capsule": "capsule", "cap": "capsule",
            "syrup": "syrup", "liquid": "syrup",
            "strip": "strip", "blister": "strip",
        }.get(form, form)
        img_path = os.path.join(self.assets_dir, f"{form_key}.webp")
        if os.path.exists(img_path):
            self.viz_img.setPixmap(
                QPixmap(img_path).scaled(280, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.viz_img.setText("")
        else:
            self.viz_img.setPixmap(QPixmap())
            self.viz_img.setText(it.text())
            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_TEXT}; "
                "font-size: 16px; font-weight: 700; letter-spacing: 0.04em;"
            )
        uom = self.current_uom
        for line in self.cart_items:
            if line["id"] == p_id and line.get("uom") == uom:
                line["qty"] = line.get("qty", 1) + 1
                line["qty_atomic"] = line["qty"] * line.get("atoms_per", 1)
                self.update_ledger()
                return
        self.cart_items.append({
            "id": p_id,
            "name": it.text(),
            "qty": 1,
            "price": price,
            "uom": uom,
            "atoms_per": atoms,
            "qty_atomic": atoms,
        })
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
            "WHERE p.generic_molecule LIKE ? OR p.barcode = ?",
            (f"%{txt}%", txt),
        )
        self._fill_search(cursor.fetchall())

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
        self._fill_search([r for r in catalog if q in r[1]])

    def _fill_search(self, res):
        self.search_table.setHorizontalHeaderLabels(
            ["PRODUCT", f"OH {self.current_uom}", "PRICE"]
        )
        self.search_table.setRowCount(0)
        for r in res:
            row = self.search_table.rowCount()
            self.search_table.insertRow(row)
            name = QTableWidgetItem(str(r[1]).upper())
            ups, spb = self._pack_size(r[0])
            price, atoms, _ = self._quote(r[3], ups, spb)
            if hasattr(self.sales_ctrl, "inv") and hasattr(self.db, "conn") and self.db.conn:
                oh = int(self.sales_ctrl.inv.get_on_hand(r[0]) or 0)
            else:
                oh = 24
            pack = max(int(atoms), 1)
            packs, rem = oh // pack, oh % pack
            if self.current_uom == "UNIT":
                oh_txt = str(oh)
            elif rem:
                oh_txt = f"{packs}+{rem}u"
            else:
                oh_txt = str(packs)
            oh_item = QTableWidgetItem(oh_txt)
            price_item = QTableWidgetItem(f"{price:.2f}")
            self._style_item(name)
            self._style_item(oh_item, align_right=True, muted=oh > 0)
            if oh <= 0:
                oh_item.setForeground(QColor("#E07A5F"))
            self._style_item(price_item, align_right=True, muted=True)
            self.search_table.setItem(row, 0, name)
            self.search_table.setItem(row, 1, oh_item)
            self.search_table.setItem(row, 2, price_item)
            name.setData(Qt.UserRole, r[0])
            name.setData(Qt.UserRole + 1, r[2])
            name.setData(Qt.UserRole + 2, price)
            name.setData(Qt.UserRole + 3, atoms)
        self.search_empty.setVisible(self.search_table.rowCount() == 0)

    def _move_search_selection(self, delta):
        """Arrow-key navigation over the results list while typing continues."""
        rows = self.search_table.rowCount()
        if rows == 0:
            return
        cur = self.search_table.currentRow()
        if cur < 0:
            new_row = 0 if delta > 0 else rows - 1
        else:
            new_row = max(0, min(rows - 1, cur + delta))
        self.search_table.selectRow(new_row)
        self.search_table.scrollToItem(self.search_table.item(new_row, 0))

    def _search_return_pressed(self):
        """Enter adds the selected result (or top match), clears and refocuses.

        Signals are blocked while clearing so we do not re-query the whole
        catalog after every add — the list stays put until the operator types
        the next item.
        """
        txt = self.search_box.text().strip()
        if not txt:
            return
        rows = self.search_table.rowCount()
        if rows == 0:
            return
        r = self.search_table.currentRow()
        if r < 0 or r >= rows:
            r = 0
        it = self.search_table.item(r, 0)
        if it is None:
            return
        self.select_item(it)
        self.search_box.blockSignals(True)
        self.search_box.clear()
        self.search_box.blockSignals(False)
        self.search_box.setFocus()

    def update_ledger(self):
        self.cart_table.setRowCount(0)
        total = 0.0
        for i in self.cart_items:
            r = self.cart_table.rowCount()
            self.cart_table.insertRow(r)
            n = QTableWidgetItem(i["name"])
            u = QTableWidgetItem(i.get("uom", "UNIT"))
            q = QTableWidgetItem(str(i.get("qty", 1)))
            p = QTableWidgetItem(f"{i['price'] * i.get('qty', 1):.2f}")
            self._style_item(n)
            self._style_item(u, muted=True)
            self._style_item(q, align_right=True, muted=True)
            self._style_item(p, align_right=True)
            self.cart_table.setItem(r, 0, n)
            self.cart_table.setItem(r, 1, u)
            self.cart_table.setItem(r, 2, q)
            self.cart_table.setItem(r, 3, p)
            total += i["price"] * i.get("qty", 1)
        self.total_lbl.setText(f"{total:,.2f}")
        n = len(self.cart_items)
        self.cart_count.setText("CART" if n == 0 else f"{n} LINE{'S' if n != 1 else ''}")
        self.cart_empty.setVisible(n == 0)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("F2"), self, self.search_box.setFocus)
        QShortcut(QKeySequence("F5"), self, self.focus_cart)
        QShortcut(QKeySequence("F3"), self, self.open_ingest)
        QShortcut(QKeySequence("F4"), self, self.cycle_uom)
        QShortcut(QKeySequence("F8"), self, self.open_checkout)
        QShortcut(QKeySequence("F10"), self, self.open_zreport)
        QShortcut(QKeySequence("F12"), self, self.open_reg)

        def bind(seq, fn):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(fn)

        bind(Qt.Key_Delete, self.remove_cart_line)
        bind("+", lambda: self.nudge_qty(1))
        bind("=", lambda: self.nudge_qty(1))
        bind("-", lambda: self.nudge_qty(-1))

    def _paint_uom_btns(self):
        if not hasattr(self, "uom_btns"):
            return
        for label, b in self.uom_btns.items():
            on = label == self.current_uom
            b.setStyleSheet(
                f"""
                QPushButton {{
                    background: {"#E8B86D" if on else "#181C23"};
                    color: {"#14110C" if on else "#F4F1EA"};
                    border: 1px solid {"#E8B86D" if on else "#2A3140"};
                    border-radius: 10px;
                    font-weight: 800;
                    font-size: 11px;
                    letter-spacing: 0.1em;
                }}
                """
            )

    def set_uom(self, uom):
        self.current_uom = uom
        self.mode_tag.setText(uom)
        self._paint_uom_btns()
        self.run_search()

    def cycle_uom(self):
        order = ["UNIT", "STRIP", "BOX"]
        idx = (order.index(self.current_uom) + 1) % 3
        self.set_uom(order[idx])

    def open_reg(self):
        self.reg = ProductRegistry(self.db)
        self.reg.show()

    def open_ingest(self):
        def _done():
            self.run_search()
            self.toast.show_message("STOCK INGESTED", "success")

        self.ingest = BatchIngest(self.db, "DEV-001", on_complete=_done)
        self.ingest.show()

    def _selected_cart_row(self):
        if not self.cart_items:
            return None
        r = self.cart_table.currentRow()
        if r < 0 or r >= len(self.cart_items):
            return len(self.cart_items) - 1
        return r

    def keyPressEvent(self, event):
        """Global routing: scans/typing land in the search box even when
        focus has drifted onto a button or the window itself."""
        if self.search_box.hasFocus() and event.text().isalpha():
            return super().keyPressEvent(event)
        key = event.key()
        if key in (Qt.Key_Delete, Qt.Key_Backspace) and not self.search_box.hasFocus():
            self.remove_cart_line()
            return
        if key in (Qt.Key_Plus, Qt.Key_Equal):
            self.nudge_qty(1)
            return
        if key == Qt.Key_Minus:
            self.nudge_qty(-1)
            return
        # UX-016: Enter with search text adds the match, even when focus
        # has drifted (prevents a focused button from swallowing the Enter
        # that belongs to a scan waiting in the search box).
        if key in (Qt.Key_Return, Qt.Key_Enter) and self.search_box.text().strip():
            self._search_return_pressed()
            return
        # UX-016: printable input outside an editable field -> search box
        text = event.text()
        if (
            text
            and text.strip()
            and text.isprintable()
            and not isinstance(QApplication.focusWidget(), QLineEdit)
        ):
            self.search_box.setFocus()
            self.search_box.insert(text)
            return
        super().keyPressEvent(event)

    def remove_cart_line(self, *args):
        r = self._selected_cart_row()
        if r is None:
            return
        del self.cart_items[r]
        self.update_ledger()

    def nudge_qty(self, delta):
        r = self._selected_cart_row()
        if r is None:
            return
        q = self.cart_items[r].get("qty", 1) + delta
        if q <= 0:
            del self.cart_items[r]
        else:
            self.cart_items[r]["qty"] = q
            self.cart_items[r]["qty_atomic"] = q * self.cart_items[r].get("atoms_per", 1)
        self.update_ledger()


    def _paint_qty_hint(self):
        """Refresh the qty-entry status label next to the cart controls."""
        if not hasattr(self, "qty_hint"):
            return
        if self.qty_buffer:
            self.qty_hint.setText(f"QTY  →  {self.qty_buffer}  ↵")
            self.qty_hint.setStyleSheet(
                f"color: {COLOR_ACCENT}; font-size: 12px; font-weight: 800; "
                "letter-spacing: 0.12em; background: transparent;"
            )
        else:
            self.qty_hint.setText("F5 QTY  ·  TYPE qty ↵")
            self.qty_hint.setStyleSheet(
                f"color: {COLOR_DIM}; font-size: 11px; font-weight: 700; "
                "letter-spacing: 0.1em; background: transparent;"
            )

    def _clear_qty_buffer(self):
        self.qty_buffer = ""
        self._paint_qty_hint()

    def _commit_qty_buffer(self):
        """Apply the pending quantity to the selected cart line."""
        if not self.qty_buffer:
            # Empty Enter while the cart is focused returns to the search box.
            self.search_box.setFocus()
            return
        r = self._selected_cart_row()
        if r is None:
            self._clear_qty_buffer()
            return
        qty = max(1, int(self.qty_buffer))
        self.cart_items[r]["qty"] = qty
        self.cart_items[r]["qty_atomic"] = qty * self.cart_items[r].get("atoms_per", 1)
        self.qty_buffer = ""
        self._paint_qty_hint()
        self.update_ledger()

    def _on_cart_qty_key(self, cmd):
        """Route cart-table key commands for quantity fast-entry."""
        if cmd == "ENTER":
            self._commit_qty_buffer()
        elif cmd == "ESC":
            self._clear_qty_buffer()
        elif cmd == "BACKSPACE":
            if self.qty_buffer:
                self.qty_buffer = self.qty_buffer[:-1]
                self._paint_qty_hint()
            else:
                self.remove_cart_line()
        elif cmd.startswith("DIGIT:"):
            self.qty_buffer = (self.qty_buffer + cmd[6:])[-3:]
            self._paint_qty_hint()

    def _on_cart_scan(self, digits):
        """A barcode scan arrived while the cart was focused — route to search."""
        self.search_box.setFocus()
        self.search_box.setText(digits)

    def focus_cart(self):
        """F5 — move keyboard focus to the cart for quantity fast-entry."""
        if not self.cart_items:
            return
        rows = self.cart_table.rowCount()
        r = self.cart_table.currentRow()
        if r < 0 or r >= rows:
            r = rows - 1
        self.cart_table.selectRow(r)
        self.cart_table.setFocus()
        self._paint_qty_hint()

    def open_zreport(self):
        ans = QMessageBox.question(
            self,
            "END OF DAY",
            "This encrypts the ledger, closes the session, and exits SENTINEL.\nContinue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans != QMessageBox.Yes:
            return
        self.z_ui = ZReportCeremony(self.db, self.session_id, self.user_id, "DEV-001")
        self.z_ui.show()

    def open_checkout(self):
        if not self.cart_items:
            self.toast.show_message("LEDGER EMPTY  ·  ADD A LINE FIRST", "error")
            return
        raw = self.total_lbl.text().replace(",", "")
        t = float(raw or 0)
        self.checkout_ui = SettlementUI(t, self.finalize_sale)
        self.checkout_ui.show()

    def finalize_sale(self, method, tendered):
        if self.sales_ctrl.commit_sale(
            self.user_id,
            self.session_id,
            self.cart_items,
            float(self.total_lbl.text().replace(",", "") or 0),
            method,
            tendered,
        ):
            change = tendered - float(self.total_lbl.text().replace(",", "") or 0)
            self.toast.show_message(f"SALE COMMITTED  ·  CHANGE {change:,.2f}", "success")
            self.cart_items = []
            self.update_ledger()
            self.run_search()
            self.search_box.setFocus()
            self.viz_img.clear()
            self.viz_img.setText("No item\nselected")
            self.viz_img.setStyleSheet(
                f"background: #0B0D10; border-radius: 10px; color: {COLOR_DIM}; "
                "font-size: 12px; letter-spacing: 0.08em;"
            )
        else:
            self.toast.show_message(
                "SALE FAILED  ·  CART PRESERVED  ·  PRESS F8 TO RETRY",
                "error",
                duration_ms=5000,
            )
        else:
            self.toast.show_message(
                "SALE FAILED  ·  CART PRESERVED  ·  PRESS F8 TO RETRY",
                "error",
                duration_ms=5000,
            )
        else:
            self.toast.show_message(
                "SALE FAILED  ·  CART PRESERVED  ·  PRESS F8 TO RETRY",
                "error",
                duration_ms=5000,
            )
