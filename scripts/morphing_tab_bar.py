try:
    from PyQt6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QApplication
    from PyQt6.QtCore import pyqtSignal, QPropertyAnimation, QRect, QEasingCurve, Qt
    from PyQt6.QtGui import QPalette, QColor, QFont
except ImportError:
    from PySide6.QtWidgets import QWidget, QPushButton, QHBoxLayout, QApplication
    from PySide6.QtCore import Signal as pyqtSignal, QPropertyAnimation, QRect, QEasingCurve, Qt
    from PySide6.QtGui import QPalette, QColor, QFont

class MorphingTabBar(QWidget):
    tab_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_index = -1
        self.buttons = []
        self._anim = None
        self.setFixedHeight(34)
        self.setStyleSheet("background: #0d131f; border-radius: 17px; border: 1px solid #1e293b;")

        self.btn_layout = QHBoxLayout(self)
        self.btn_layout.setContentsMargins(4, 3, 4, 3)
        self.btn_layout.setSpacing(4)

        self.indicator = QWidget(self)
        self.indicator.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088cc, stop:1 #00d2ff); border-radius: 14px;")
        self.indicator.hide()

    def add_tab(self, text: str):
        idx = len(self.buttons)
        btn = QPushButton(text, self)
        btn.setFixedHeight(28)
        btn.setStyleSheet("background: transparent; border: none; color: #94a3b8; font-size: 12px; font-weight: normal; padding: 0 14px;")
        btn.clicked.connect(lambda _, i=idx: self.switch_tab(i))
        self.buttons.append(btn)
        self.btn_layout.addWidget(btn)

    def switch_tab(self, index: int):
        if not (0 <= index < len(self.buttons)):
            return

        prev_index = self.active_index
        self.active_index = index

        for i, btn in enumerate(self.buttons):
            if i == index:
                btn.setStyleSheet("background: transparent; border: none; color: #ffffff; font-size: 12px; font-weight: bold; padding: 0 14px;")
            else:
                btn.setStyleSheet("background: transparent; border: none; color: #94a3b8; font-size: 12px; font-weight: normal; padding: 0 14px;")

        target = self.buttons[index].geometry()
        self.indicator.show()
        self.indicator.lower()

        if hasattr(QEasingCurve, 'Type'):
            easing = QEasingCurve.Type.OutCubic
        else:
            easing = getattr(QEasingCurve, 'OutCubic', None)

        if prev_index == -1 or not self.indicator.isVisible():
            self.indicator.setGeometry(target)
        else:
            if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
                self._anim.stop()
            self._anim = QPropertyAnimation(self.indicator, b"geometry", self)
            self._anim.setDuration(220)
            self._anim.setStartValue(self.indicator.geometry())
            self._anim.setEndValue(target)
            if easing:
                self._anim.setEasingCurve(easing)
            self._anim.start()

        self.tab_changed.emit(index)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if 0 <= self.active_index < len(self.buttons):
            self.indicator.setGeometry(self.buttons[self.active_index].geometry())

if __name__ == "__main__":
    app = QApplication([])
    bar = MorphingTabBar()
    bar.add_tab("Tab 1")
    bar.add_tab("Tab 2")
    bar.switch_tab(0)
