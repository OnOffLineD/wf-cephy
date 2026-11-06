"""2-tone HUD glyph renderer and unfolding HudButton (PyQt6 / PySide6).

All animation is painted directly with QPainter: no setStyleSheet() and no
QGraphicsEffect while animating, so repaints stay cheap enough for 60fps.
"""
import os

try:
    from PyQt6.QtWidgets import QAbstractButton, QSizePolicy
    from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, QTimer, QVariantAnimation, QEasingCurve
    from PyQt6.QtGui import QPainter, QColor, QPen, QPixmap, QFontMetrics, QPainterPath
except ImportError:
    from PySide6.QtWidgets import QAbstractButton, QSizePolicy
    from PySide6.QtCore import Qt, QSize, QRectF, QPointF, QTimer, QVariantAnimation, QEasingCurve
    from PySide6.QtGui import QPainter, QColor, QPen, QPixmap, QFontMetrics, QPainterPath

ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")

HUD_CYAN = QColor(0, 229, 255)
HUD_BG = QColor(12, 16, 23, int(0.88 * 255))
HUD_BORDER_IDLE = QColor(30, 41, 59)
HUD_TEXT = QColor(226, 232, 240)

COMPACT_WIDTH = 32
BUTTON_HEIGHT = 30
ICON_SIZE = 18
LABEL_PAD = 12
HOVER_MS = 180
PRESS_MS = 320
BUSY_FRAME_MS = 16

_pixmap_cache = {}


def _lerp(a, b, t):
    return a + (b - a) * t


def _mix(c1, c2, t):
    return QColor(
        int(_lerp(c1.red(), c2.red(), t)),
        int(_lerp(c1.green(), c2.green(), t)),
        int(_lerp(c1.blue(), c2.blue(), t)),
        int(_lerp(c1.alpha(), c2.alpha(), t)),
    )


def load_icon_pixmap(icon_name=None, icon_path=None):
    """Return a QPixmap for icon_path or assets/icons/<icon_name>.png, or None if unavailable."""
    path = icon_path or (os.path.join(ICON_DIR, f"{icon_name}.png") if icon_name else None)
    if not path:
        return None
    if path not in _pixmap_cache:
        pm = QPixmap(path) if os.path.isfile(path) else QPixmap()
        _pixmap_cache[path] = None if pm.isNull() else pm
    return _pixmap_cache[path]


def render_glyph(painter, name, rect, primary=HUD_CYAN, secondary=HUD_TEXT):
    """Vector 2-tone fallback glyph for icons without a PNG asset (e.g. 'close')."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    w = max(1.5, rect.width() / 9.0)
    c = rect.center()
    r = rect.width() / 2.0
    if name == "close":
        painter.setPen(QPen(secondary, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        d = r * 0.55
        painter.drawLine(QPointF(c.x() - d, c.y() - d), QPointF(c.x() + d, c.y() + d))
        painter.drawLine(QPointF(c.x() + d, c.y() - d), QPointF(c.x() - d, c.y() + d))
        painter.setPen(QPen(primary, w * 0.7))
        painter.drawEllipse(c, r * 0.95, r * 0.95)
    else:
        # Generic HUD diamond: secondary outline, primary core.
        path = QPainterPath()
        path.moveTo(c.x(), c.y() - r * 0.9)
        path.lineTo(c.x() + r * 0.9, c.y())
        path.lineTo(c.x(), c.y() + r * 0.9)
        path.lineTo(c.x() - r * 0.9, c.y())
        path.closeSubpath()
        painter.setPen(QPen(secondary, w * 0.8))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(primary)
        painter.drawEllipse(c, r * 0.3, r * 0.3)
    painter.restore()


class HudButton(QAbstractButton):
    """Capsule HUD button that unfolds from icon-only to icon + label on hover/focus."""

    def __init__(self, text="", parent=None, icon_name=None, icon_path=None, icon_only=True):
        super().__init__(parent)
        self.setText(text)
        self.setToolTip(text)
        self.icon_name = icon_name
        self.icon_path = icon_path
        self.icon_only = icon_only
        self._pixmap = load_icon_pixmap(icon_name, icon_path)
        self._hover_t = 0.0
        self._press_t = 0.0
        self._press_pos = QPointF(COMPACT_WIDTH / 2.0, BUTTON_HEIGHT / 2.0)
        self._busy = False
        self._busy_angle = 0.0

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)

        self._hover_anim = QVariantAnimation(self)
        self._hover_anim.setDuration(HOVER_MS)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hover_anim.valueChanged.connect(self._on_hover_value)

        self._press_anim = QVariantAnimation(self)
        self._press_anim.setDuration(PRESS_MS)
        self._press_anim.setStartValue(0.0)
        self._press_anim.setKeyValueAt(0.35, 1.0)
        self._press_anim.setEndValue(0.0)
        self._press_anim.valueChanged.connect(self._on_press_value)

        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(BUSY_FRAME_MS)
        self._busy_timer.timeout.connect(self._on_busy_tick)

    # ---- animated properties -------------------------------------------------
    @property
    def hover_t(self):
        return self._hover_t

    @hover_t.setter
    def hover_t(self, value):
        value = max(0.0, min(1.0, float(value)))
        if value == self._hover_t:
            return
        self._hover_t = value
        self.updateGeometry()
        self.update()

    @property
    def press_t(self):
        return self._press_t

    @property
    def is_busy(self):
        return self._busy

    def set_busy(self, busy):
        busy = bool(busy)
        if busy == self._busy:
            return
        self._busy = busy
        if busy:
            self._busy_timer.start()
        else:
            self._busy_timer.stop()
            self._busy_angle = 0.0
        self.update()

    def _on_hover_value(self, value):
        self.hover_t = value

    def _on_press_value(self, value):
        self._press_t = float(value)
        self.update()

    def _on_busy_tick(self):
        self._busy_angle = (self._busy_angle + 6.0) % 360.0
        self.update()

    def _animate_hover(self, target):
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_t)
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    # ---- geometry ------------------------------------------------------------
    def _expanded_width(self):
        if not self.text():
            return COMPACT_WIDTH
        return COMPACT_WIDTH + QFontMetrics(self.font()).horizontalAdvance(self.text()) + LABEL_PAD

    def sizeHint(self):
        full = self._expanded_width()
        t = self._hover_t if self.icon_only else 1.0
        return QSize(int(round(_lerp(COMPACT_WIDTH, full, t))), BUTTON_HEIGHT)

    def minimumSizeHint(self):
        return self.sizeHint()

    # ---- events --------------------------------------------------------------
    def enterEvent(self, event):
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.hasFocus():
            self._animate_hover(0.0)
        super().leaveEvent(event)

    def focusInEvent(self, event):
        self._animate_hover(1.0)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if not self.underMouse():
            self._animate_hover(0.0)
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        pos = event.position() if hasattr(event, "position") else QPointF(event.pos())
        self._press_pos = QPointF(pos)
        self._press_anim.stop()
        self._press_anim.start()
        super().mousePressEvent(event)

    # ---- painting ------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        t = self._hover_t
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = rect.height() / 2.0

        capsule = QPainterPath()
        capsule.addRoundedRect(rect, radius, radius)
        p.fillPath(capsule, HUD_BG)

        # Press ripple, clipped to the capsule.
        if self._press_t > 0.0:
            p.save()
            p.setClipPath(capsule)
            ripple = QColor(HUD_CYAN)
            ripple.setAlpha(int(70 * self._press_t))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ripple)
            rr = self._press_t * max(rect.width(), rect.height())
            p.drawEllipse(self._press_pos, rr, rr)
            p.restore()

        border = _mix(HUD_BORDER_IDLE, HUD_CYAN, t)
        p.setPen(QPen(border, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(capsule)

        if t > 0.01:
            self._paint_brackets(p, rect, t)

        icon_rect = QRectF((COMPACT_WIDTH - ICON_SIZE) / 2.0, (self.height() - ICON_SIZE) / 2.0,
                           ICON_SIZE, ICON_SIZE)
        if self._pixmap is not None:
            p.drawPixmap(icon_rect.toRect(), self._pixmap)
        else:
            render_glyph(p, self.icon_name or "", icon_rect)

        if self._busy:
            arc_rect = icon_rect.adjusted(-4, -4, 4, 4)
            p.setPen(QPen(HUD_CYAN, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawArc(arc_rect, int(-self._busy_angle * 16), 100 * 16)

        label_t = t if self.icon_only else 1.0
        if label_t > 0.01 and self.text():
            color = QColor(HUD_TEXT)
            color.setAlphaF(label_t)
            p.setPen(color)
            text_rect = QRectF(COMPACT_WIDTH - 2, 0, max(0.0, rect.width() - COMPACT_WIDTH), self.height())
            p.setClipRect(text_rect)
            p.drawText(text_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), self.text())
        p.end()

    def _paint_brackets(self, p, rect, t):
        """Tenno aiming brackets '⌐ ¬' fading in at the capsule corners."""
        c = QColor(HUD_CYAN)
        c.setAlphaF(t)
        p.setPen(QPen(c, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap))
        arm = 4.0
        inset = 3.0
        l, r = rect.left() + inset, rect.right() - inset
        top, bot = rect.top() + 1.5, rect.bottom() - 1.5
        for x, sx in ((l, 1), (r, -1)):
            p.drawLine(QPointF(x, top), QPointF(x + sx * arm, top))
            p.drawLine(QPointF(x, top), QPointF(x, top + arm))
            p.drawLine(QPointF(x, bot), QPointF(x + sx * arm, bot))
            p.drawLine(QPointF(x, bot), QPointF(x, bot - arm))
