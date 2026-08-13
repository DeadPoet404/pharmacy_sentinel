"""SENTINEL shared UI kit — keep every name the rest of the app already imports."""

from PySide6.QtWidgets import QPushButton, QLabel, QFrame
from PySide6.QtCore import Qt

# ── palette (dark industrial) ──────────────────────────────────────────────
COLOR_BG = "#0B0D10"
COLOR_SURFACE = "#12151A"
COLOR_SURFACE_2 = "#181C23"
COLOR_CARD = "#12151A"
COLOR_SIDEBAR = "#0E1116"
COLOR_BORDER = "#2A3140"
COLOR_BORDER_SOFT = "#1E2430"
COLOR_TEXT = "#F4F1EA"
COLOR_MUTED = "#8B93A7"
COLOR_DIM = "#5C6478"
COLOR_ACCENT = "#E8B86D"
COLOR_ACCENT_DIM = "#C4923A"
COLOR_PRIMARY = COLOR_ACCENT
COLOR_DANGER = "#E07A5F"
COLOR_OK = "#7DCEA0"
COLOR_SUCCESS = COLOR_OK
COLOR_WARNING = "#E8B86D"
COLOR_WHITE = "#F4F1EA"
COLOR_BLACK = "#0B0D10"

GLOBAL_STYLE = f"""
QWidget {{
    background: {COLOR_BG};
    color: {COLOR_TEXT};
    font-family: "IBM Plex Sans", "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}}
QLabel {{
    background: transparent;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 500;
    color: {COLOR_TEXT};
    selection-background-color: {COLOR_ACCENT};
    selection-color: #111;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{
    border: 1px solid {COLOR_ACCENT};
}}
QTableWidget, QTableView, QTreeView, QListView {{
    background: {COLOR_SURFACE};
    alternate-background-color: {COLOR_SURFACE_2};
    border: 1px solid {COLOR_BORDER_SOFT};
    border-radius: 12px;
    gridline-color: {COLOR_BORDER_SOFT};
    outline: none;
    color: {COLOR_TEXT};
}}
QTableWidget::item, QTableView::item {{
    padding: 10px 14px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: #2A2418;
    color: {COLOR_ACCENT};
}}
QHeaderView::section {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_DIM};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    padding: 12px 14px;
    border: none;
    border-bottom: 1px solid {COLOR_BORDER};
}}
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 8px 2px;
}}
QScrollBar::handle:vertical {{
    background: {COLOR_BORDER};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0;
    width: 0;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}
QScrollBar::handle:horizontal {{
    background: {COLOR_BORDER};
    border-radius: 4px;
}}
QMessageBox {{
    background: {COLOR_SURFACE};
}}
QMessageBox QLabel {{
    color: {COLOR_TEXT};
}}
QComboBox QAbstractItemView {{
    background: {COLOR_SURFACE};
    border: 1px solid {COLOR_BORDER};
    selection-background-color: #2A2418;
    selection-color: {COLOR_ACCENT};
    color: {COLOR_TEXT};
    outline: none;
}}
QToolTip {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    padding: 6px 8px;
}}
QDialog {{
    background: {COLOR_BG};
}}
QFrame {{
    color: {COLOR_TEXT};
}}
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: 10px;
    background: {COLOR_SURFACE};
}}
QTabBar::tab {{
    background: {COLOR_SURFACE_2};
    color: {COLOR_MUTED};
    padding: 8px 16px;
    border: 1px solid {COLOR_BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
}}
QTabBar::tab:selected {{
    color: {COLOR_ACCENT};
    background: {COLOR_SURFACE};
}}
"""


def apply_deep_elevation(widget, level="MEDIUM"):
    extra = {
        "LOW": f"border: 1px solid {COLOR_BORDER_SOFT};",
        "MEDIUM": f"border: 1px solid {COLOR_BORDER};",
        "HIGH": f"border: 1px solid {COLOR_ACCENT_DIM};",
    }.get(level, f"border: 1px solid {COLOR_BORDER};")
    existing = widget.styleSheet() or ""
    widget.setStyleSheet(existing + extra)


class IndustrialButton(QPushButton):
    def __init__(self, text, primary=True, parent=None, danger=False):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(52)
        if danger:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLOR_DANGER};
                    color: #1A0C08;
                    border: none;
                    border-radius: 10px;
                    font-weight: 800;
                    font-size: 13px;
                    letter-spacing: 0.1em;
                    padding: 0 22px;
                }}
                QPushButton:hover {{ background: #E9927A; }}
            """)
        elif primary:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLOR_ACCENT};
                    color: #14110C;
                    border: none;
                    border-radius: 10px;
                    font-weight: 800;
                    font-size: 13px;
                    letter-spacing: 0.12em;
                    padding: 0 22px;
                }}
                QPushButton:hover {{ background: #F0C98A; }}
                QPushButton:pressed {{ background: {COLOR_ACCENT_DIM}; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {COLOR_SURFACE_2};
                    color: {COLOR_TEXT};
                    border: 1px solid {COLOR_BORDER};
                    border-radius: 10px;
                    font-weight: 700;
                    font-size: 12px;
                    letter-spacing: 0.1em;
                    padding: 0 18px;
                }}
                QPushButton:hover {{
                    border-color: {COLOR_ACCENT};
                    color: {COLOR_ACCENT};
                }}
            """)


class SectionLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(str(text).replace("_", " ").upper(), parent)
        self.setStyleSheet(f"""
            color: {COLOR_DIM};
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 0.22em;
            padding: 0 2px 8px 2px;
            background: transparent;
        """)


class TechnicalCard(QFrame):
    def __init__(self, parent=None, title=None):
        super().__init__(parent)
        self.setObjectName("TechnicalCard")
        self.setStyleSheet(f"""
            QFrame#TechnicalCard {{
                background: {COLOR_SURFACE};
                border: 1px solid {COLOR_BORDER};
                border-radius: 16px;
            }}
        """)
        if title:
            self.setToolTip(str(title))
