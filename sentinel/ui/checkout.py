import sys
import uuid
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, QFrame,
    QFormLayout, QMessageBox, QGraphicsDropShadowEffect,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from sentinel.ui.components import (
    GLOBAL_STYLE, IndustrialButton, SectionLabel,
    COLOR_ACCENT, COLOR_DIM, COLOR_MUTED, COLOR_TEXT,
    COLOR_SURFACE, COLOR_BORDER, COLOR_BG, COLOR_DANGER,
)


class SettlementUI(QWidget):
    def __init__(self, total_ghs, on_complete):
        super().__init__()
        self.total_ghs = float(total_ghs or 0)
        self.on_complete = on_complete

        self.setWindowTitle("Settlement")
        self.setFixedSize(440, 560)
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
        title = QLabel("TRANSACTION SETTLEMENT")
        title.setStyleSheet(
            f"color: {COLOR_TEXT}; font-weight: 800; font-size: 12px; letter-spacing: 0.2em;"
        )
        bl.addWidget(mark)
        bl.addWidget(title)
        bl.addStretch()
        root.addWidget(bar)

        body = QVBoxLayout()
        body.setContentsMargins(24, 22, 24, 24)
        body.setSpacing(16)

        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 #16120C, stop:1 #0C0D10);
                border: 1px solid {COLOR_ACCENT};
                border-radius: 14px;
            }}
        """)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 18)
        due_cap = QLabel("TOTAL DUE  ·  GHS")
        due_cap.setStyleSheet(
            f"color: {COLOR_ACCENT}; font-size: 10px; font-weight: 800; letter-spacing: 0.22em;"
        )
        self.val_due = QLabel(f"{self.total_ghs:,.2f}")
        self.val_due.setStyleSheet(
            "color: #FFF8EC; font-size: 52px; font-weight: 800; letter-spacing: -2px;"
        )
        self.val_due.setAlignment(Qt.AlignRight)
        cl.addWidget(due_cap)
        cl.addWidget(self.val_due)
        body.addWidget(card)

        body.addWidget(SectionLabel("Tender"))

        form_card = QFrame()
        form_card.setStyleSheet(f"""
            QFrame {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 14px;
            }}
        """)
        fl = QVBoxLayout(form_card)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(10)

        lbl = QLabel("AMOUNT TENDERED")
        lbl.setStyleSheet(
            f"color: {COLOR_DIM}; font-size: 10px; font-weight: 800; letter-spacing: 0.18em;"
        )
        self.tendered_in = QLineEdit()
        self.tendered_in.setPlaceholderText("0.00")
        self.tendered_in.setAlignment(Qt.AlignRight)
        self.tendered_in.setStyleSheet(f"""
            QLineEdit {{
                background: #0B0D10;
                border: 1px solid {COLOR_BORDER};
                border-radius: 10px;
                font-size: 28px;
                font-weight: 700;
                padding: 14px 16px;
                letter-spacing: -0.5px;
            }}
            QLineEdit:focus {{ border: 1px solid {COLOR_ACCENT}; }}
        """)
        self.tendered_in.textChanged.connect(self.calc_change)

        self.change_out = QLabel("CHANGE   0.00")
        self.change_out.setAlignment(Qt.AlignRight)
        self.change_out.setStyleSheet(
            f"color: {COLOR_MUTED}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
        )

        fl.addWidget(lbl)
        fl.addWidget(self.tendered_in)

        quick = QHBoxLayout()
        quick.setSpacing(8)
        for label, fn in (
            ("EXACT", self.fill_exact),
            ("50", lambda: self.fill_amount(50)),
            ("100", lambda: self.fill_amount(100)),
            ("200", lambda: self.fill_amount(200)),
        ):
            b = IndustrialButton(label, primary=False)
            b.setFixedHeight(40)
            b.clicked.connect(fn)
            quick.addWidget(b)
        fl.addLayout(quick)
        fl.addWidget(self.change_out)
        body.addWidget(form_card)

        body.addStretch()

        self.btn_cash = IndustrialButton("COMPLETE CASH SALE")
        self.btn_cash.setFixedHeight(58)
        self.btn_cash.clicked.connect(lambda: self.finish("CASH"))
        body.addWidget(self.btn_cash)

        hint = QLabel("Enter tender  ·  Enter to confirm")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(f"color: {COLOR_DIM}; font-size: 10px; letter-spacing: 0.14em;")
        body.addWidget(hint)

        wrap = QWidget()
        wrap.setLayout(body)
        root.addWidget(wrap, 1)

        self.tendered_in.returnPressed.connect(lambda: self.finish("CASH"))
        self.tendered_in.setFocus()

    def calc_change(self):
        try:
            tendered = float(self.tendered_in.text().replace(",", "") or 0)
            change = tendered - self.total_ghs
            if change < 0:
                self.change_out.setText(f"SHORT   {abs(change):,.2f}")
                self.change_out.setStyleSheet(
                    f"color: {COLOR_DANGER}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
                )
            else:
                self.change_out.setText(f"CHANGE   {change:,.2f}")
                self.change_out.setStyleSheet(
                    f"color: {COLOR_ACCENT}; font-size: 16px; font-weight: 700; letter-spacing: 0.08em; padding-top: 4px;"
                )
        except ValueError:
            pass

    def finish(self, method):
        try:
            tendered = float(self.tendered_in.text().replace(",", "") or 0)
            if tendered < self.total_ghs:
                QMessageBox.warning(self, "LOW FUNDS", "Tendered amount is less than total due.")
                return
            self.on_complete(method, tendered)
            self.close()
        except ValueError:
            QMessageBox.warning(self, "INVALID", "Enter a valid tender amount.")
