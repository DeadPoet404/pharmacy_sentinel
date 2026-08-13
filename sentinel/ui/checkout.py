import sys
import uuid
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                             QLabel, QFrame, QPushButton, QFormLayout, QMessageBox)
from PySide6.QtCore import Qt

class SettlementUI(QWidget):
    def __init__(self, total_ghs, on_complete):
        super().__init__()
        self.total_ghs = total_ghs
        self.on_complete = on_complete
        
        self.setWindowTitle("SETTLEMENT_CONTROL")
        self.setFixedSize(400, 500)
        self.setStyleSheet("background-color: #e0e0e0; font-family: monospace;")

        layout = QVBoxLayout(self)
        
        header = QLabel("➔ TRANSACTION_SETTLEMENT")
        header.setStyleSheet("background-color: black; color: #FF4500; padding: 5px; font-weight: bold;")
        layout.addWidget(header)

        # Totals Card
        card = QFrame()
        card.setStyleSheet("border: 2px solid black; background-color: #f4f4f4;")
        c_layout = QVBoxLayout(card)
        
        lbl_due = QLabel("TOTAL_DUE_GHS")
        lbl_due.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.val_due = QLabel(f"{total_ghs:.2f}")
        self.val_due.setStyleSheet("font-size: 50px; font-weight: 900; color: black;")
        
        c_layout.addWidget(lbl_due)
        c_layout.addWidget(self.val_due)
        layout.addWidget(card)

        # Input Area
        form_frame = QFrame()
        form_layout = QFormLayout(form_frame)
        
        self.tendered_in = QLineEdit()
        self.tendered_in.setPlaceholderText("0.00")
        self.tendered_in.setStyleSheet("border: 2px solid black; font-size: 24px; padding: 10px; background: white;")
        self.tendered_in.textChanged.connect(self.calc_change)
        
        self.change_out = QLabel("CHANGE: 0.00")
        self.change_out.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF4500;")

        form_layout.addRow("AMOUNT_TENDERED:", self.tendered_in)
        form_layout.addRow(self.change_out)
        layout.addWidget(form_frame)

        # Actions
        self.btn_cash = QPushButton("COMPLETE_CASH_SALE")
        self.btn_cash.setFixedHeight(60)
        self.btn_cash.setStyleSheet("background-color: #FF4500; border: 2px solid black; font-weight: bold;")
        self.btn_cash.clicked.connect(lambda: self.finish("CASH"))
        
        layout.addWidget(self.btn_cash)
        
        self.tendered_in.setFocus()

    def calc_change(self):
        try:
            tendered = float(self.tendered_in.text() or 0)
            change = tendered - self.total_ghs
            self.change_out.setText(f"CHANGE: {max(0, change):.2f}")
        except: pass

    def finish(self, method):
        try:
            tendered = float(self.tendered_in.text() or 0)
            if tendered < self.total_ghs:
                QMessageBox.warning(self, "LOW_FUNDS", "Tendered amount less than total due.")
                return
            self.on_complete(method, tendered)
            self.close()
        except: pass
