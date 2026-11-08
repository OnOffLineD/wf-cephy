"""Ordis speech bubble; paintEvent paints the opaque body itself (EXP-015) so DWM never shows through."""
try:
    from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPointF, pyqtSignal
    from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath
    from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
except ImportError:
    from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPointF, Signal as pyqtSignal
    from PySide6.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath
    from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

BORDER_W, RADIUS, TAIL_H, TAIL_HALF_W, BUBBLE_WIDTH, FADE_MS = 1.5, 12.0, 10, 8, 260, 180


class PetSpeechBubbleWidget(QWidget):
    closed = pyqtSignal(object)   # emits self once fully hidden

    def __init__(self, text, duration_ms=5000, on_click_action=None, parent=None):
        super().__init__(parent)
        self.duration_ms = self._remaining_ms = max(0, int(duration_ms))
        self.on_click_action = on_click_action
        self._closing = False
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.label = QLabel(text, self)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #e2e8f0; font-size: 12px; background: transparent;")
        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self.label)
        self.setFixedWidth(BUBBLE_WIDTH)
        self.set_tail("bottom", BUBBLE_WIDTH // 2)
        self.dismiss_timer = QTimer(self)
        self.dismiss_timer.setSingleShot(True)
        self.dismiss_timer.timeout.connect(self.dismiss)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(FADE_MS)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade.finished.connect(lambda: self._closing and self._finish_close())

    def set_tail(self, side, tail_x):   # side: 'bottom' | 'top'; tail_x in bubble coords
        self.tail_side, self.tail_x = side, int(tail_x)
        top = TAIL_H if side == "top" else 0
        self._layout.setContentsMargins(12, 9 + top, 12, 9 + TAIL_H - top)
        self.adjustSize()
        self.update()

    def show_bubble(self):
        self._closing = False
        self.setWindowOpacity(0.0)
        self.show()
        self._animate(0.0, 1.0)
        if self.duration_ms > 0:
            self.dismiss_timer.start(self.duration_ms)

    def dismiss(self, animate=True):
        if self._closing:
            return
        self._closing = True
        self.dismiss_timer.stop()
        if animate and self.isVisible():
            self._animate(self.windowOpacity(), 0.0)
        else:
            self._fade.stop()
            self._finish_close()

    def _animate(self, start, end):
        self._fade.stop()
        self._fade.setStartValue(start)
        self._fade.setEndValue(end)
        self._fade.start()

    def _finish_close(self):
        self.hide()
        self.closed.emit(self)
        self.deleteLater()

    def enterEvent(self, event):   # hover pauses the countdown
        if self.dismiss_timer.isActive():
            self._remaining_ms = max(1, self.dismiss_timer.remainingTime())
            self.dismiss_timer.stop()

    def leaveEvent(self, event):   # leaving resumes the remainder
        if not self._closing and self.duration_ms > 0 and not self.dismiss_timer.isActive():
            self.dismiss_timer.start(self._remaining_ms)

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        action = None if self._closing else self.on_click_action
        self.dismiss()
        if action is not None:
            action()
        event.accept()

    def bubble_path(self):
        h = BORDER_W / 2
        r = QRectF(self.rect()).adjusted(h, h, -h, -h)
        top = self.tail_side == "top"
        body = r.adjusted(0, TAIL_H, 0, 0) if top else r.adjusted(0, 0, 0, -TAIL_H)
        base_y, tip_y = (body.top() + 1, r.top()) if top else (body.bottom() - 1, r.bottom())
        path, tail, x = QPainterPath(), QPainterPath(), float(self.tail_x)
        path.addRoundedRect(body, RADIUS, RADIUS)
        tail.moveTo(QPointF(x - TAIL_HALF_W, base_y))
        tail.lineTo(QPointF(x, tip_y))
        tail.lineTo(QPointF(x + TAIL_HALF_W, base_y))
        tail.closeSubpath()
        return path.united(tail)

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(QColor("#00e5ff"), BORDER_W))   # neon cyan border
            painter.setBrush(QBrush(QColor("#0c1017")))           # opaque dark body
            painter.drawPath(self.bubble_path())
        finally:
            painter.end()
