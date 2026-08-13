from PySide6.QtWidgets import (QPushButton, QFrame, QHBoxLayout, QLabel, QVBoxLayout, QGraphicsDropShadowEffect)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

COLOR_BG = "#F1F5F9"  # Lighter industrial blue-gray plane
COLOR_SIDEBAR = "#F1F5F9"
COLOR_BORDER = "#000000"
COLOR_ACCENT = "#FF4500"
COLOR_SUCCESS = "#16a34a"

GLOBAL_STYLE = f"""
    QWidget {{
        background-color: {COLOR_BG};
        font-family: 'Inter', 'monospace';
        color: black;
    }}
    QTableWidget {{
        background-color: white;
        border: 1px solid #CBD5E1;
        gridline-color: #F1F5F9;
        selection-background-color: {COLOR_ACCENT};
        selection-color: white;
        outline: none;
    }}
    QHeaderView::section {{
        background-color: black;
        color: white;
        padding: 8px;
        border: none;
        font-weight: 900;
        font-size: 11px;
    }}
    QLineEdit {{
        background-color: white;
        border: 1px solid #CBD5E1;
        padding: 12px;
        font-size: 14px;
    }}
    QLineEdit:focus {{
        border: 2px solid black;
    }}
"""

def apply_deep_elevation(widget, intensity="MEDIUM"):
    """High-end SaaS elevation with soft falloff"""
    shadow = QGraphicsDropShadowEffect(widget)
    if intensity == "HIGH":
        shadow.setBlurRadius(60)
        shadow.setOffset(0, 15)
        shadow.setColor(QColor(0, 0, 0, 60)) # More prominent
    else:
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 40))
    widget.setGraphicsEffect(shadow)
    return shadow

class IndustrialButton(QPushButton):
    def __init__(self, text, primary=True):
        super().__init__(text.upper())
        bg = COLOR_ACCENT if primary else "black"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                font-weight: 900;
                padding: 12px;
            }}
            QPushButton:hover {{ background-color: white; color: black; border: 2px solid black; }}
        """)
        apply_deep_elevation(self)

class TechnicalCard(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("border: 1px solid #CBD5E1; background: white;")
        apply_deep_elevation(self, "HIGH")

class SectionLabel(QLabel):
    def __init__(self, text):
        super().__init__(f"➔ {text.upper()}")
        self.setStyleSheet(f"font-weight: 900; font-size: 11px; color: {COLOR_ACCENT}; margin-bottom: 8px; background: transparent;")
