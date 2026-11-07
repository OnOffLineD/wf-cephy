"""
Frameless & Draggable Dialog Base Class and Utilities (PyQt6 / PySide6).

Provides:
- FramelessWindowHint styling with Warframe Cephalon dark theme.
- Silky smooth mouse dragging from the header or card background.
- Aesthetic header bar with custom title, icon, and close button.
- Title synchronization on setWindowTitle.
"""
import os
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QDialog, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
    )
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QIcon, QPixmap
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
    )
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtGui import QIcon, QPixmap

from scripts.hud_widgets import load_icon_pixmap, HUD_CYAN, HUD_BG

FRAMELESS_CARD_STYLE = """
QFrame#framelessCard {
    background-color: #0c1017;
    border: 1.5px solid #00d2ff;
    border-radius: 16px;
    color: #e2e8f0;
}
QFrame#framelessCard QLabel {
    color: #e2e8f0;
}
"""

FRAMELESS_DIALOG_STYLE = """
QDialog {
    background-color: #0c1017;
    border: 1.5px solid #00d2ff;
    border-radius: 14px;
    color: #e2e8f0;
}
QLabel {
    color: #94a3b8;
    font-size: 12px;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #161e2e;
    color: #ffffff;
    border: 1px solid #24324d;
    border-radius: 6px;
    padding: 6px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #00d2ff;
}
QPushButton {
    border-radius: 6px;
    font-weight: bold;
    padding: 8px;
    color: #ffffff;
    background-color: #1e293b;
}
QPushButton:hover {
    background-color: #2e3e5c;
    border: 1px solid #00d2ff;
}
QTableWidget {
    background-color: #111722;
    color: #e2e8f0;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 4px;
    border: none;
}
"""

CLOSE_BTN_STYLE = """
QPushButton#framelessCloseBtn {
    background: transparent;
    color: #94a3b8;
    font-size: 15px;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    width: 28px;
    height: 28px;
}
QPushButton#framelessCloseBtn:hover {
    background: rgba(244, 63, 94, 0.2);
    color: #ff3366;
}
"""

class FramelessDialog(QDialog):
    """Base QDialog with frameless window hint, sleek Warframe dark theme card,
    draggable header bar, and close button.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_pos = QPoint()
        self.title_label = None
        self._frameless_title_label = None
        # StaysOnTop matches the always-on-top companion app so dragging does not
        # drop this dialog behind its parent (Z-order inversion / focus loss).
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Dialog
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(FRAMELESS_DIALOG_STYLE)

    def setWindowTitle(self, title: str):
        super().setWindowTitle(title)
        if getattr(self, 'title_label', None) is not None:
            self.title_label.setText(title)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos') and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # Always end the drag, then re-activate so child widgets accept clicks at once.
        self._drag_pos = QPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            if self.isVisible():
                self.activateWindow()
                self.raise_()
        else:
            super().mouseReleaseEvent(event)

    def bind_drag_events(self, widget: QWidget):
        """Route a container widget's mouse events to this dialog's drag handlers."""
        widget.mousePressEvent = self.mousePressEvent
        widget.mouseMoveEvent = self.mouseMoveEvent
        widget.mouseReleaseEvent = self.mouseReleaseEvent

    def create_title_bar(self, title: str = "", on_close=None, icon_name: Optional[str] = None, icon_path: Optional[str] = None) -> QFrame:
        """Create a draggable top bar with title, optional icon, and close button."""
        header = QFrame(self)
        header.setObjectName("framelessHeader")
        header.setStyleSheet("background: transparent; border-bottom: 1px solid rgba(0, 210, 255, 0.2); padding-bottom: 6px;")

        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(8)

        # Icon if available
        pix = load_icon_pixmap(icon_name=icon_name, icon_path=icon_path)
        if pix and not pix.isNull():
            icon_lbl = QLabel()
            icon_lbl.setPixmap(pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            icon_lbl.setFixedSize(22, 22)
            h_layout.addWidget(icon_lbl)

        # Title
        display_title = title or self.windowTitle()
        self.title_label = QLabel(display_title, header)
        self.title_label.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 13px;")
        self._frameless_title_label = self.title_label
        h_layout.addWidget(self.title_label)
        h_layout.addStretch()

        # Close button
        close_btn = QPushButton("✕", header)
        close_btn.setObjectName("framelessCloseBtn")
        close_btn.setStyleSheet(CLOSE_BTN_STYLE)
        close_btn.setToolTip("닫기")
        close_btn.clicked.connect(on_close or self.reject)
        h_layout.addWidget(close_btn)

        # Forward mouse events from header to the dialog's own drag handlers
        # (global coordinates are used, so header-local positions are irrelevant).
        self.bind_drag_events(header)

        return header


def apply_frameless_shell(dialog: QDialog, title: str = "", on_close=None, icon_name: Optional[str] = None) -> QFrame:
    """Helper to convert any existing QDialog into a frameless draggable dialog with custom header."""
    dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
    dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
    dialog._drag_pos = QPoint()

    orig_press = dialog.mousePressEvent
    orig_move = dialog.mouseMoveEvent
    orig_release = dialog.mouseReleaseEvent

    def press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            dialog._drag_pos = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
            event.accept()
        elif orig_press:
            orig_press(event)

    def move(event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(dialog, '_drag_pos') and not dialog._drag_pos.isNull():
            dialog.move(event.globalPosition().toPoint() - dialog._drag_pos)
            event.accept()
        elif orig_move:
            orig_move(event)

    def release(event):
        dialog._drag_pos = QPoint()
        if orig_release:
            orig_release(event)

    dialog.mousePressEvent = press
    dialog.mouseMoveEvent = move
    dialog.mouseReleaseEvent = release

    # Header bar
    header = QFrame(dialog)
    header.setObjectName("framelessHeader")
    header.setStyleSheet("background: transparent; border-bottom: 1px solid rgba(0, 210, 255, 0.2); padding-bottom: 6px;")
    h_layout = QHBoxLayout(header)
    h_layout.setContentsMargins(4, 2, 4, 2)
    h_layout.setSpacing(8)

    pix = load_icon_pixmap(icon_name=icon_name)
    if pix and not pix.isNull():
        icon_lbl = QLabel()
        icon_lbl.setPixmap(pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        icon_lbl.setFixedSize(22, 22)
        h_layout.addWidget(icon_lbl)

    title_label = QLabel(title or dialog.windowTitle(), header)
    title_label.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 13px;")
    dialog._frameless_title_label = title_label
    h_layout.addWidget(title_label)
    h_layout.addStretch()

    close_btn = QPushButton("✕", header)
    close_btn.setObjectName("framelessCloseBtn")
    close_btn.setStyleSheet(CLOSE_BTN_STYLE)
    close_btn.setToolTip("닫기")
    close_btn.clicked.connect(on_close or dialog.reject)
    h_layout.addWidget(close_btn)

    def header_press(event):
        if event.button() == Qt.MouseButton.LeftButton:
            dialog._drag_pos = event.globalPosition().toPoint() - dialog.frameGeometry().topLeft()
            event.accept()
    def header_move(event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(dialog, '_drag_pos') and not dialog._drag_pos.isNull():
            dialog.move(event.globalPosition().toPoint() - dialog._drag_pos)
            event.accept()
    def header_release(event):
        dialog._drag_pos = QPoint()

    header.mousePressEvent = header_press
    header.mouseMoveEvent = header_move
    header.mouseReleaseEvent = header_release

    return header
