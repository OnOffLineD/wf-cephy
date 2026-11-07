import os
import sys
import math
import random
from typing import Optional, Dict

try:
    from PyQt6.QtWidgets import QWidget, QApplication
    from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush, QFont, QRadialGradient
    from PyQt6.QtCore import QTimer, Qt, QRect, QPoint
except ImportError:
    from PySide6.QtWidgets import QWidget, QApplication
    from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush, QFont, QRadialGradient
    from PySide6.QtCore import QTimer, Qt, QRect, QPoint

from scripts.path_config import get_path

class LayeredPetRenderer(QWidget):
    def __init__(self, asset_dir: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.asset_dir = asset_dir or get_path("assets", "character")
        self.layers_dir = os.path.join(self.asset_dir, "layers")
        # Stat the disk once; paintEvent runs ~25x/s and Drive VFS stats are slow.
        self.has_layers = os.path.exists(self.layers_dir)

        self.mood = "idle"
        self.secondary_mood: Optional[str] = None
        self.intensity = 1
        self.vfx: Optional[str] = None

        self.is_talking = False
        self.is_blinking = False
        self.mouth_frame_index = 0
        self.tick = 0
        self.talk_tick = 0

        self.setFixedSize(140, 140)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # 1. Floating sine-wave bounce timer (40ms ~ 25 FPS)
        self.bounce_timer = QTimer(self)
        self.bounce_timer.timeout.connect(self._on_bounce_tick)
        self.bounce_timer.start(40)

        # 2. Eye blink timer (3~5s random interval)
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.blink)
        self._schedule_next_blink()

        # 3. Talking lip-sync timer (120ms mouth cycle)
        self.talk_timer = QTimer(self)
        self.talk_timer.timeout.connect(self._cycle_mouth_frame)

        # Preloaded pixmap cache
        self._cache: Dict[str, Optional[QPixmap]] = {}

    def _schedule_next_blink(self):
        next_interval = random.randint(3000, 5000)
        self.blink_timer.start(next_interval)

    def _on_bounce_tick(self):
        self.tick = (self.tick + 1) % 10000
        if self.is_talking:
            self.talk_tick = (self.talk_tick + 1) % 10000
        self.update()

    # ---- Multi-phase motion math (pure functions of state; testable headless) ----
    def _amplitude(self) -> float:
        return 2 + (self.intensity * 0.8)

    def _compute_gesture_offset(self) -> float:
        """Talking rhythm gesture for the right hand (0 when silent)."""
        if not self.is_talking:
            return 0.0
        return math.sin(self.talk_tick * 0.25) * 5

    def _compute_jitter(self):
        """High-frequency glitch tremor; (0, 0) unless mood is 'glitch'."""
        if self.mood != "glitch":
            return (0, 0)
        return (random.randint(-2, 2), random.randint(-2, 2))

    def _compute_body_transform(self, tick: int):
        """Returns (y_body, rot_body_degrees)."""
        amp = self._amplitude()
        y_body = math.sin(tick * 0.08) * amp
        rot_body = math.sin(tick * 0.04) * 1.5
        if self.is_talking:
            # Nodding: up to +1.5 deg extra tilt synced to the talk rhythm
            rot_body += 1.5 * abs(math.sin(self.talk_tick * 0.25))
        return y_body, rot_body

    def _compute_hand_offsets(self, tick: int):
        """Returns {'left': (x, y), 'right': (x, y)} with phase lag, gesture and jitter."""
        amp = self._amplitude()
        y_body, _ = self._compute_body_transform(tick)
        x_lh = math.cos(tick * 0.06 + 0.5) * 1.5
        y_lh = y_body * 0.4 + math.sin(tick * 0.10 + 1.4) * (amp * 1.3)
        x_rh = 0.0
        y_rh = y_body * 0.4 + math.sin(tick * 0.09 + 2.8) * (amp * 1.3)
        y_rh += self._compute_gesture_offset()

        jlx, jly = self._compute_jitter()
        jrx, jry = self._compute_jitter()
        return {
            "left": (x_lh + jlx, y_lh + jly),
            "right": (x_rh + jrx, y_rh + jry),
        }

    def _cycle_mouth_frame(self):
        if self.is_talking:
            self.mouth_frame_index = (self.mouth_frame_index + 1) % 3
            self.update()

    def blink(self):
        self.blink_timer.stop()
        self.is_blinking = True
        self.update()

        # 140ms later, open eyes and schedule next blink
        QTimer.singleShot(140, self._finish_blink)

    def _finish_blink(self):
        self.is_blinking = False
        self.update()
        self._schedule_next_blink()

    def set_mood(self, mood: str, intensity: int = 1, vfx: Optional[str] = None, secondary_mood: Optional[str] = None):
        norm_mood = mood.lower().strip() if mood else "idle"
        self.mood = norm_mood
        self.secondary_mood = secondary_mood.lower().strip() if secondary_mood else None
        self.intensity = max(1, min(3, intensity))
        self.vfx = vfx.lower().strip() if vfx else None
        self.update()

    def start_talking(self, duration_ms: int = 0):
        self.is_talking = True
        self.mouth_frame_index = 1
        self.talk_tick = 0
        if not self.talk_timer.isActive():
            self.talk_timer.start(120)

        if duration_ms > 0:
            QTimer.singleShot(duration_ms, self.stop_talking)
        self.update()

    def stop_talking(self):
        self.is_talking = False
        self.talk_timer.stop()
        self.mouth_frame_index = 0
        self.update()

    def _load_layer_pixmap(self, subfolder: str, filename: str) -> Optional[QPixmap]:
        key = f"{subfolder}/{filename}"
        if key in self._cache:
            return self._cache[key]

        fpath = os.path.join(self.layers_dir, subfolder, filename)
        if os.path.exists(fpath):
            pix = QPixmap(fpath)
            if not pix.isNull():
                self._cache[key] = pix
                return pix

        self._cache[key] = None
        return None

    def _load_single_fallback(self, mood: str) -> Optional[QPixmap]:
        key = f"single_{mood}"
        if key in self._cache:
            return self._cache[key]

        fpath = os.path.join(self.asset_dir, f"{mood}.png")
        if os.path.exists(fpath):
            pix = QPixmap(fpath)
            if not pix.isNull():
                self._cache[key] = pix
                return pix

        fpath_idle = os.path.join(self.asset_dir, "idle.png")
        if os.path.exists(fpath_idle):
            pix = QPixmap(fpath_idle)
            if not pix.isNull():
                self._cache[key] = pix
                return pix

        self._cache[key] = None
        return None

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        target_rect = QRect(6, 6, w - 12, h - 12)

        # 1. Multi-phase transforms: body (breath + tilt), hands (lagging inertia, gesture, jitter)
        cx, cy = w / 2.0, h / 2.0
        y_body, rot_body = self._compute_body_transform(self.tick)
        hand_offsets = self._compute_hand_offsets(self.tick)

        def apply_body_transform():
            painter.translate(cx, cy + y_body)
            painter.rotate(rot_body)
            painter.translate(-cx, -cy)

        painter.save()
        apply_body_transform()

        # Cached in __init__ to avoid a disk stat every frame
        has_layers = self.has_layers

        # 2. Try drawing multi-layer composable parts
        drawn_any = False
        if has_layers:
            # Layer A: Body
            body_pix = self._load_layer_pixmap("body", f"body_{self.mood}.png") or self._load_layer_pixmap("body", "body_idle.png")
            if body_pix:
                painter.drawPixmap(target_rect, body_pix)
                drawn_any = True

            # Layer B: Eyes (respect blinking)
            eye_mood = self.secondary_mood or self.mood
            if self.is_blinking:
                eye_pix = self._load_layer_pixmap("eyes", "eye_blink.png") or self._load_layer_pixmap("eyes", f"eye_{eye_mood}.png")
            else:
                eye_pix = self._load_layer_pixmap("eyes", f"eye_{eye_mood}.png") or self._load_layer_pixmap("eyes", "eye_idle.png")
            if eye_pix:
                painter.drawPixmap(target_rect, eye_pix)
                drawn_any = True

            # Layer C: Brows
            brow_mood = self.secondary_mood or self.mood
            brow_pix = self._load_layer_pixmap("brows", f"brow_{brow_mood}.png") or self._load_layer_pixmap("brows", "brow_idle.png")
            if brow_pix:
                painter.drawPixmap(target_rect, brow_pix)
                drawn_any = True

            # Layer D: Mouth (respect is_talking lip-sync)
            if self.is_talking:
                mouth_files = ["mouth_open_small.png", "mouth_open_big.png", "mouth_idle.png"]
                mouth_file = mouth_files[self.mouth_frame_index]
                mouth_pix = self._load_layer_pixmap("mouth", mouth_file) or self._load_layer_pixmap("mouth", f"mouth_{self.mood}.png")
            else:
                mouth_pix = self._load_layer_pixmap("mouth", f"mouth_{self.mood}.png") or self._load_layer_pixmap("mouth", "mouth_idle.png")
            if mouth_pix:
                painter.drawPixmap(target_rect, mouth_pix)
                drawn_any = True

        painter.restore()

        if has_layers:
            # Layer E: Hands (independent transforms outside the body transform)
            if self._draw_hands(painter, target_rect, hand_offsets):
                drawn_any = True

        painter.save()
        apply_body_transform()

        if has_layers:
            # Layer F: VFX (blush, sweat, tears, sparks)
            vfx_name = self.vfx or ("glitch" if self.mood == "glitch" else None)
            if vfx_name:
                vfx_pix = self._load_layer_pixmap("vfx", f"vfx_{vfx_name}.png")
                if vfx_pix:
                    painter.drawPixmap(target_rect, vfx_pix)
                    drawn_any = True

        # 3. Single Image Fallback (e.g. idle.png, glitch.png)
        if not drawn_any:
            single_pix = self._load_single_fallback(self.mood)
            if single_pix:
                painter.drawPixmap(target_rect, single_pix)
                drawn_any = True

        # 4. Procedural Chibi Vector Fallback (Always renders beautifully even with 0 assets!)
        if not drawn_any:
            self._draw_procedural_chibi(painter, target_rect)

        painter.restore()

    def _resolve_hand_pixmaps(self):
        """Returns (left, right, unified). Split L/R files take priority;
        mood-specific art wins over default art; unified hand_*.png is the fallback."""
        mood = self.mood
        left = self._load_layer_pixmap("hands", f"hand_left_{mood}.png")
        right = self._load_layer_pixmap("hands", f"hand_right_{mood}.png")
        if left and right:
            return left, right, None
        unified_mood = self._load_layer_pixmap("hands", f"hand_{mood}.png") if mood != "idle" else None
        if unified_mood:
            return None, None, unified_mood
        left = self._load_layer_pixmap("hands", "hand_left.png")
        right = self._load_layer_pixmap("hands", "hand_right.png")
        if left and right:
            return left, right, None
        return None, None, self._load_layer_pixmap("hands", "hand_idle.png")

    def _draw_hands(self, painter: QPainter, rect: QRect, offsets) -> bool:
        left, right, unified = self._resolve_hand_pixmaps()
        if left and right:
            for pix, (dx, dy) in ((left, offsets["left"]), (right, offsets["right"])):
                painter.save()
                painter.translate(dx, dy)
                painter.drawPixmap(rect, pix)
                painter.restore()
            return True
        if unified:
            (lx, ly), (rx, ry) = offsets["left"], offsets["right"]
            painter.save()
            painter.translate((lx + rx) / 2.0, (ly + ry) / 2.0)
            painter.drawPixmap(rect, unified)
            painter.restore()
            return True
        return False

    def _draw_procedural_chibi(self, p: QPainter, rect: QRect):
        cx = rect.center().x()
        cy = rect.center().y()
        r = min(rect.width(), rect.height()) // 2 - 8

        # Chibi Body / Hologram Cube-Sphere Glow
        glow_color = QColor(0, 210, 255, 180) if self.mood != "glitch" else QColor(255, 50, 80, 200)
        core_color = QColor(14, 24, 40, 230)

        p.setPen(QPen(glow_color, 2.5))
        p.setBrush(QBrush(core_color))
        p.drawRoundedRect(cx - r, cy - r, r * 2, r * 2, 28, 28)

        # Cephalon Ordis Crest / Floating Diamond
        p.setPen(QPen(glow_color, 1.8))
        crest_pts = [
            QPoint(cx, cy - r - 6),
            QPoint(cx + 6, cy - r),
            QPoint(cx, cy - r + 6),
            QPoint(cx - 6, cy - r)
        ]
        p.drawPolygon(crest_pts)

        # Eyes
        eye_y = cy - 8
        eye_spacing = 20
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow_color))

        if self.is_blinking:
            # Closed line eyes
            p.setPen(QPen(glow_color, 2.5))
            p.drawLine(cx - eye_spacing - 6, eye_y, cx - eye_spacing + 6, eye_y)
            p.drawLine(cx + eye_spacing - 6, eye_y, cx + eye_spacing + 6, eye_y)
        elif self.mood == "happy":
            # Curved crescent happy eyes ^ ^
            p.setPen(QPen(glow_color, 2.8))
            p.drawArc(cx - eye_spacing - 7, eye_y - 6, 14, 12, 30 * 16, 120 * 16)
            p.drawArc(cx + eye_spacing - 7, eye_y - 6, 14, 12, 30 * 16, 120 * 16)
        elif self.mood == "glitch":
            # Angry / red slit eyes
            p.setPen(QPen(glow_color, 3.0))
            p.drawLine(cx - eye_spacing - 7, eye_y - 3, cx - eye_spacing + 7, eye_y + 3)
            p.drawLine(cx + eye_spacing - 7, eye_y + 3, cx + eye_spacing + 7, eye_y - 3)
        else:
            # Round open eyes
            p.drawEllipse(cx - eye_spacing - 5, eye_y - 5, 10, 10)
            p.drawEllipse(cx + eye_spacing - 5, eye_y - 5, 10, 10)

        # Mouth (reacts to is_talking)
        mouth_y = cy + 16
        p.setPen(QPen(glow_color, 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)

        if self.is_talking:
            # Talking mouth open
            open_h = 6 + (self.mouth_frame_index * 4)
            p.setBrush(QBrush(QColor(0, 160, 220, 150)))
            p.drawEllipse(cx - 6, mouth_y - open_h // 2, 12, open_h)
        elif self.mood in ["happy", "proud"]:
            # Smile
            p.drawArc(cx - 9, mouth_y - 6, 18, 12, 200 * 16, 140 * 16)
        elif self.mood in ["sad", "worried"]:
            # Frown
            p.drawArc(cx - 9, mouth_y, 18, 12, 20 * 16, 140 * 16)
        else:
            # Neutral line
            p.drawLine(cx - 6, mouth_y, cx + 6, mouth_y)

        # VFX Overlays
        if self.vfx == "blush" or (self.mood == "happy" and self.intensity >= 2):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(255, 105, 180, 120)))
            p.drawEllipse(cx - eye_spacing - 4, eye_y + 10, 10, 5)
            p.drawEllipse(cx + eye_spacing - 6, eye_y + 10, 10, 5)
        elif self.vfx == "sweat" or self.mood == "worried":
            p.setPen(QPen(QColor(100, 200, 255), 1.5))
            p.setBrush(QBrush(QColor(100, 220, 255, 160)))
            p.drawEllipse(cx + r - 12, cy - r + 8, 5, 8)
