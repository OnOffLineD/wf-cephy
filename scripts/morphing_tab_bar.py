"""QPainter-rendered tab bar with an elastic-stretch morphing indicator.

The indicator edges (_l, _r) are floats in tab-index units. On a tab change the
leading edge moves fast (OutCubic) and the trailing edge follows slowly
(OutQuint), so the capsule stretches like a rubber band and then snaps back.
No setStyleSheet() is ever called; tab rects are cached so nothing reflows.
"""
import math

try:
    from PyQt6.QtWidgets import QWidget, QApplication, QSizePolicy
    from PyQt6.QtCore import pyqtSignal, Qt, QRectF, QPointF, QSize, QVariantAnimation, QEasingCurve
    from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
except ImportError:
    from PySide6.QtWidgets import QWidget, QApplication, QSizePolicy
    from PySide6.QtCore import Signal as pyqtSignal, Qt, QRectF, QPointF, QSize, QVariantAnimation, QEasingCurve
    from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics

try:
    from scripts.hud_widgets import HUD_CYAN, load_icon_pixmap, render_glyph, _mix
except ImportError:
    from hud_widgets import HUD_CYAN, load_icon_pixmap, render_glyph, _mix

BAR_BG = QColor(13, 19, 31)
BAR_BORDER = QColor(30, 41, 59)
IND_FILL = QColor(0, 40, 56, 170)
TEXT_ACTIVE = QColor(255, 255, 255)
TEXT_IDLE = QColor(226, 232, 240, int(0.6 * 255))
ICON_IDLE = QColor(148, 163, 184)
LEAD_MS = 190
TRAIL_MS = 310
BAR_HEIGHT = 34
MARGIN = 3
SPACING = 4
TAB_PAD = 14
ICON_SIZE = 16
ICON_GAP = 6


class MorphingTabBar(QWidget):
    tab_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_index = -1
        self.tabs = []
        self._rects = []
        self._l = 0.0
        self._r = 0.0
        self.setFixedHeight(BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._font = QFont(self.font())
        self._font.setPixelSize(12)
        self._bold = QFont(self._font)
        self._bold.setBold(True)
        self._anim_l = self._make_anim("_l")
        self._anim_r = self._make_anim("_r")

    def _make_anim(self, attr):
        anim = QVariantAnimation(self)

        def _on_value(v, a=attr):
            setattr(self, a, float(v))
            self.update()

        anim.valueChanged.connect(_on_value)
        return anim

    # ---- public API -------------------------------------------------------
    def add_tab(self, text: str, icon_name=None):
        pixmap = load_icon_pixmap(icon_name) if icon_name else None
        self.tabs.append({"text": text, "icon_name": icon_name, "pixmap": pixmap})
        self._relayout()

    def switch_tab(self, index: int):
        if not (0 <= index < len(self.tabs)):
            return
        prev = self.active_index
        self.active_index = index
        if prev == -1:
            self._anim_l.stop()
            self._anim_r.stop()
            self._l = self._r = float(index)
        elif index != prev:
            forward = index > prev
            lead, trail = (self._anim_r, self._anim_l) if forward else (self._anim_l, self._anim_r)
            for anim, ms, curve in ((lead, LEAD_MS, QEasingCurve.Type.OutCubic),
                                    (trail, TRAIL_MS, QEasingCurve.Type.OutQuint)):
                anim.stop()
                start = self._r if anim is self._anim_r else self._l
                anim.setDuration(ms)
                anim.setEasingCurve(curve)
                anim.setStartValue(float(start))
                anim.setEndValue(float(index))
                anim.start()
        self.update()
        self.tab_changed.emit(index)

    # ---- geometry (cached) ------------------------------------------------
    def _relayout(self):
        fm = QFontMetrics(self._bold)  # bold width so active/idle never reflow
        x = float(MARGIN)
        h = BAR_HEIGHT - 2 * MARGIN
        self._rects = []
        for tab in self.tabs:
            w = fm.horizontalAdvance(tab["text"]) + 2 * TAB_PAD
            if tab["icon_name"]:
                w += ICON_SIZE + ICON_GAP
            self._rects.append(QRectF(x, MARGIN, w, h))
            x += w + SPACING
        width = int(math.ceil(x - SPACING + MARGIN)) if self.tabs else 2 * MARGIN
        self.setFixedWidth(width)
        self.update()

    def sizeHint(self):
        return QSize(self.width(), BAR_HEIGHT)

    def _edge_x(self, pos, right):
        n = len(self._rects)
        pos = min(max(pos, 0.0), n - 1.0)
        i = int(math.floor(pos))
        j = min(i + 1, n - 1)
        t = pos - i
        a, b = self._rects[i], self._rects[j]
        xa, xb = (a.right(), b.right()) if right else (a.left(), b.left())
        return xa + (xb - xa) * t

    def indicator_rect(self):
        if not self._rects or self.active_index < 0:
            return QRectF()
        left, right = self._edge_x(self._l, False), self._edge_x(self._r, True)
        return QRectF(left, MARGIN, max(0.0, right - left), BAR_HEIGHT - 2 * MARGIN)

    # ---- input / paint ----------------------------------------------------
    def mousePressEvent(self, event):
        p = event.position() if hasattr(event, "position") else QPointF(event.pos())
        for i, r in enumerate(self._rects):
            if r.contains(p):
                self.switch_tab(i)
                return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(BAR_BORDER, 1.0))
        p.setBrush(BAR_BG)
        p.drawRoundedRect(outer, outer.height() / 2, outer.height() / 2)

        ind = self.indicator_rect()
        if not ind.isEmpty():
            rad = ind.height() / 2
            p.setPen(QPen(HUD_CYAN, 1.5))
            p.setBrush(IND_FILL)
            p.drawRoundedRect(ind.adjusted(0.75, 0.75, -0.75, -0.75), rad, rad)
            accent = QColor(HUD_CYAN)
            accent.setAlpha(160)
            p.setPen(QPen(accent, 1.0))
            p.drawLine(QPointF(ind.left() + rad, ind.bottom() - 2.5), QPointF(ind.right() - rad, ind.bottom() - 2.5))

        center = (self._l + self._r) / 2.0
        for i, (tab, r) in enumerate(zip(self.tabs, self._rects)):
            t = max(0.0, 1.0 - abs(center - i)) if self.active_index >= 0 else 0.0
            text_rect = QRectF(r)
            if tab["icon_name"]:
                content_w = r.width() - 2 * TAB_PAD
                icon_rect = QRectF(r.left() + TAB_PAD, r.center().y() - ICON_SIZE / 2, ICON_SIZE, ICON_SIZE)
                if tab["pixmap"] is not None:
                    p.setOpacity(0.55 + 0.45 * t)
                    p.drawPixmap(icon_rect.toRect(), tab["pixmap"])
                    p.setOpacity(1.0)
                else:
                    render_glyph(p, tab["icon_name"], icon_rect, _mix(ICON_IDLE, HUD_CYAN, t), _mix(TEXT_IDLE, TEXT_ACTIVE, t))
                text_rect = QRectF(icon_rect.right() + ICON_GAP, r.top(), content_w - ICON_SIZE - ICON_GAP, r.height())
            p.setFont(self._bold if i == self.active_index else self._font)
            p.setPen(_mix(TEXT_IDLE, TEXT_ACTIVE, t))
            p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, tab["text"])
        p.end()


if __name__ == "__main__":
    app = QApplication([])
    bar = MorphingTabBar()
    bar.add_tab("채팅", icon_name="chat")
    bar.add_tab("숙제", icon_name="todo")
    bar.add_tab("현황", icon_name="status")
    bar.switch_tab(0)
    bar.show()
    app.exec()
