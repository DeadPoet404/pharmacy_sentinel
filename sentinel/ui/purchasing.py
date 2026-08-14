import sys
import uuid
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QPushButton, QComboBox, QFormLayout, QMessageBox,
)
from PySide6.QtCore import Qt, QTimer
from sentinel.logic.pricing import calculate_wac
from sentinel.logic.inventory import InventoryController
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, SectionLabel,
    COLOR_ACCENT, COLOR_DIM, COLOR_TEXT, COLOR_SURFACE,
    COLOR_BORDER, COLOR_MUTED,
    COLOR_OK, COLOR_DANGER,
)


class BatchIngest(QWidget):
    def __init__(self, db_manager, device_id, on_complete=None):
        super().__init__()
        self.db = db_manager
        self.inv = InventoryController(db_manager, device_id)
        self.on_complete = on_complete

        self.setWindowTitle("Stock ingest")
        self.setFixedSize(520, 640)
        self.setStyleSheet(GLOBAL_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background: #0E1116; border-bottom: 1px solid {COLOR_BORDER};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(22, 0, 22, 0)
        mark = QLabel("●")
        mark.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px;")
        title = QLabel("STOCK IN  ·  BATCH INIT")
        title.setStyleSheet(
            f"color: {COLOR_TEXT}; font-weight: 800; font-size: 12px; letter-spacing: 0.2em;"
        )
        bl.addWidget(mark)
        bl.addWidget(title)
        bl.addStretch()
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 24)
        body.setSpacing(14)
        body.addWidget(SectionLabel("Receiving ticket"))

        self.form_card = QFrame()
        self.form_card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 14px;
            }}
            QLabel {{
                color: {COLOR_DIM};
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.14em;
            }}
            QComboBox {{
                min-height: 40px;
            }}
        """)
        form = QFormLayout(self.form_card)
        form.setContentsMargins(20, 18, 20, 18)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)

        self.prod_selector = QComboBox()
        self.refresh_products()

        self.batch_in = QLineEdit()
        self.batch_in.setPlaceholderText("LOT / BATCH CODE")
        self.expiry_in = QLineEdit()
        self.expiry_in.setPlaceholderText("YYYY-MM-DD")
        self.qty_in = QLineEdit()
        self.qty_in.setPlaceholderText("0")
        self.cost_in = QLineEdit()
        self.cost_in.setPlaceholderText("0.00")

        form.addRow("TARGET PRODUCT", self.prod_selector)
        form.addRow("BATCH ID", self.batch_in)
        form.addRow("EXPIRY", self.expiry_in)
        form.addRow("QTY  (UNITS)", self.qty_in)
        form.addRow("UNIT COST  (GHS)", self.cost_in)

        body.addWidget(self.form_card, 1)

        note = QLabel("WAC is recalculated on commit from on-hand + this receipt.")
        note.setStyleSheet(f"color: {COLOR_MUTED}; font-size: 11px;")
        note.setWordWrap(True)
        body.addWidget(note)

        self.status_lbl = QLabel("BATCH ↵  EXPIRY ↵  QTY ↵  COST ↵  COMMITS")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        self.status_lbl.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 11px; font-weight: 700; "
            "letter-spacing: 0.06em;"
        )
        body.addWidget(self.status_lbl)

        self.commit_btn = IndustrialButton("EXECUTE INGEST")
        self.commit_btn.setFixedHeight(58)
        self.commit_btn.clicked.connect(self.process_ingest)
        body.addWidget(self.commit_btn)

        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)

        # Keyboard flow: BATCH ↵ -> EXPIRY ↵ -> QTY ↵ -> COST ↵ commits
        self.batch_in.returnPressed.connect(self.expiry_in.setFocus)
        self.expiry_in.returnPressed.connect(self.qty_in.setFocus)
        self.qty_in.returnPressed.connect(self.cost_in.setFocus)
        self.cost_in.returnPressed.connect(self.process_ingest)
        QTimer.singleShot(0, self.prod_selector.setFocus)

    def refresh_products(self):
        self.prod_selector.clear()
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT id, generic_molecule, brand FROM products")
        for row in cursor.fetchall():
            self.prod_selector.addItem(f"{row[1]}  ·  {row[2]}", row[0])

    def _set_status(self, text, kind="info"):
        colors = {
            "info": COLOR_MUTED,
            "ok": COLOR_OK,
            "error": COLOR_DANGER,
        }
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(
            f"color: {colors.get(kind, COLOR_MUTED)}; font-size: 11px; "
            "font-weight: 700; letter-spacing: 0.06em;"
        )

    def _validate_fields(self):
        """Field-level validation with human messages. Returns (msg, values)."""
        prod_id = self.prod_selector.currentData()
        if prod_id is None:
            return "SELECT A PRODUCT FIRST", None
        batch = self.batch_in.text().strip().upper()
        if not batch:
            return "ENTER A LOT / BATCH CODE", None
        expiry_raw = self.expiry_in.text().strip()
        if not expiry_raw:
            return "ENTER AN EXPIRY DATE  ·  YYYY-MM-DD", None
        try:
            expiry = datetime.strptime(expiry_raw, "%Y-%m-%d").date()
        except ValueError:
            return "EXPIRY MUST BE YYYY-MM-DD  ·  e.g. 2027-06-30", None
        if expiry < datetime.now().date():
            return f"EXPIRY {expiry_raw} IS IN THE PAST", None
        try:
            qty = int(self.qty_in.text().strip())
        except ValueError:
            return "QUANTITY MUST BE A WHOLE NUMBER", None
        if qty <= 0:
            return "QUANTITY MUST BE GREATER THAN ZERO", None
        try:
            cost_ghs = float(self.cost_in.text().strip())
        except ValueError:
            return "COST MUST BE A NUMBER  ·  e.g. 12.50", None
        if cost_ghs < 0:
            return "COST CANNOT BE NEGATIVE", None
        return None, {
            "prod_id": prod_id,
            "batch": batch,
            "expiry": expiry_raw,
            "qty": qty,
            "cost_ghs": cost_ghs,
        }

    def process_ingest(self):
        msg, values = self._validate_fields()
        if msg:
            self._set_status(msg, "error")
            return
        try:
            prod_id = values["prod_id"]
            qty = values["qty"]
            cost_p = int(values["cost_ghs"] * 100)

            cursor = self.db.conn.cursor()

            cursor.execute(
                "SELECT id FROM product_versions WHERE product_id = ? AND is_current = 1",
                (prod_id,),
            )
            res = cursor.fetchone()
            if not res:
                cursor.execute(
                    "SELECT id FROM product_versions WHERE product_id = ? ORDER BY id DESC LIMIT 1",
                    (prod_id,),
                )
                res = cursor.fetchone()
            if not res:
                raise ValueError("Product missing version mapping. Re-add product in Registry.")
            version_id = res[0]

            on_hand = self.inv.get_on_hand(prod_id)
            cursor.execute(
                "SELECT cost_minor_per_unit FROM stock_ledger "
                "WHERE product_id = ? AND cost_minor_per_unit IS NOT NULL "
                "ORDER BY event_seq DESC LIMIT 1",
                (prod_id,),
            )
            ledger_res = cursor.fetchone()
            old_wac = ledger_res[0] if ledger_res and ledger_res[0] is not None else cost_p
            new_wac = calculate_wac(on_hand, old_wac, qty, cost_p)

            b_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO batches (uuid, product_version_id, batch_code, expiry_date, received_at) "
                "VALUES (?, ?, ?, ?, 'now')",
                (b_uuid, version_id, values["batch"], values["expiry"]),
            )
            batch_id = cursor.lastrowid

            self.inv.record_movement(prod_id, qty, "PURCHASE_IN", "po", 0, batch_id, new_wac)

            self.db.conn.commit()
            self.close()
            if self.on_complete:
                self.on_complete()

        except Exception as e:
            try:
                self.db.conn.rollback()
            except Exception:
                pass
            self._set_status(f"INGEST FAILED  ·  {str(e)[:80]}", "error")
