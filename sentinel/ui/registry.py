import uuid
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QTableWidget, QHeaderView, QComboBox, QFormLayout, QTableWidgetItem,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, TechnicalCard, SectionLabel,
    COLOR_ACCENT, COLOR_DIM, COLOR_TEXT, COLOR_BORDER, COLOR_MUTED,
)


class ProductRegistry(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        self.db = db_manager
        self.setWindowTitle("Product registry")
        self.setFixedSize(1040, 720)
        self.setStyleSheet(GLOBAL_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"background: #0E1116; border-bottom: 1px solid {COLOR_BORDER};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(24, 0, 24, 0)
        mark = QLabel("●")
        mark.setStyleSheet(f"color: {COLOR_ACCENT}; font-size: 12px;")
        title = QLabel("REGISTRY  ·  BLUEPRINT")
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
        body.addWidget(SectionLabel("Product registry & blueprinting"))

        content = QHBoxLayout()
        content.setSpacing(18)

        form_card = TechnicalCard()
        fl = QFormLayout(form_card)
        fl.setContentsMargins(22, 22, 22, 22)
        fl.setSpacing(14)
        fl.setLabelAlignment(Qt.AlignLeft)
        form_card.setStyleSheet(form_card.styleSheet() + f"""
            QLabel {{
                color: {COLOR_DIM};
                font-size: 10px;
                font-weight: 800;
                letter-spacing: 0.14em;
            }}
        """)

        self.generic_in = QLineEdit()
        self.generic_in.setPlaceholderText("e.g. AMOXICILLIN")
        self.brand_in = QLineEdit()
        self.brand_in.setPlaceholderText("e.g. AMOXIL")
        self.form_in = QComboBox()
        self.form_in.addItems(["CAPSULE", "SYRUP", "STRIP", "PILL"])

        fl.addRow("GENERIC NAME", self.generic_in)
        fl.addRow("BRAND NAME", self.brand_in)
        fl.addRow("DOSAGE FORM", self.form_in)

        self.save_btn = IndustrialButton("COMMIT TO LEDGER")
        self.save_btn.clicked.connect(self.save_product)
        fl.addRow(self.save_btn)
        content.addWidget(form_card, 2)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(SectionLabel("Catalog"))
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["ITEM", "FORM"])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(42)
        right.addWidget(self.table, 1)

        self.cat_empty = QLabel("No products in catalog")
        self.cat_empty.setAlignment(Qt.AlignCenter)
        self.cat_empty.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 11px; letter-spacing: 0.08em;"
        )
        right.addWidget(self.cat_empty)
        content.addLayout(right, 3)

        body.addLayout(content, 1)
        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)

        self.refresh_list()

    def refresh_list(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT generic_molecule, form FROM products")
        prods = cursor.fetchall()
        self.table.setRowCount(0)
        for p in prods:
            r = self.table.rowCount()
            self.table.insertRow(r)
            a = QTableWidgetItem(str(p[0]))
            b = QTableWidgetItem(str(p[1]))
            a.setForeground(QColor(COLOR_TEXT))
            b.setForeground(QColor(COLOR_MUTED))
            f = a.font()
            f.setWeight(QFont.DemiBold)
            a.setFont(f)
            self.table.setItem(r, 0, a)
            self.table.setItem(r, 1, b)
        self.cat_empty.setVisible(self.table.rowCount() == 0)

    def save_product(self):
        cursor = self.db.conn.cursor()
        try:
            p_uuid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO products (uuid, generic_molecule, brand, strength, form, "
                "regulatory_class, created_at, updated_at) VALUES (?, ?, ?, 'N/A', ?, 'OTC', 'now', 'now')",
                (
                    p_uuid,
                    self.generic_in.text().upper(),
                    self.brand_in.text().upper(),
                    self.form_in.currentText(),
                ),
            )
            prod_id = cursor.lastrowid
            try:
                cursor.execute(
                    "INSERT INTO product_versions (product_id, version_label, units_per_strip, "
                    "strips_per_box, units_per_box, effective_date, created_at, is_current) "
                    "VALUES (?, 'V1', 10, 10, 100, 'now', 'now', 1)",
                    (prod_id,),
                )
            except Exception:
                cursor.execute(
                    "INSERT INTO product_versions (product_id, version_label, units_per_strip, "
                    "strips_per_box, units_per_box, effective_date, created_at) "
                    "VALUES (?, 'V1', 10, 10, 100, 'now', 'now')",
                    (prod_id,),
                )
            self.db.conn.commit()
            self.refresh_list()
            self.generic_in.clear()
            self.brand_in.clear()
        except Exception as e:
            print(e)
