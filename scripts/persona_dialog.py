import os
import sys
import threading
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QDialog, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication,
        QTabWidget, QWidget, QLineEdit, QFileDialog, QSpinBox, QComboBox, QCheckBox
    )
    from PyQt6.QtCore import Qt, QSize, QRectF, QVariantAnimation, QEasingCurve, pyqtSignal
    from PyQt6.QtGui import QIcon, QPainter, QPen
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication,
        QTabWidget, QWidget, QLineEdit, QFileDialog, QSpinBox, QComboBox, QCheckBox
    )
    from PySide6.QtCore import Qt, QSize, QRectF, QVariantAnimation, QEasingCurve, Signal as pyqtSignal
    from PySide6.QtGui import QIcon, QPainter, QPen

from scripts.persona_manager import PersonaManager, DEFAULT_PRESETS
from scripts.llm_providers import LOCAL_PROVIDER, PROVIDERS, ApiKeyStore, LLMClient
from scripts.hud_widgets import load_icon_pixmap, HUD_CYAN
from scripts.path_config import get_path
from scripts.frameless_dialog import FramelessDialog
from scripts.morphing_tab_bar import MorphingTabBar, BAR_BG, BAR_BORDER, IND_FILL, LEAD_MS, TRAIL_MS


class EdgeMorpher:
    """Capsule edges (lo, hi) in item-index units, animated like MorphingTabBar:
    the leading edge moves fast (OutCubic) and the trailing edge follows (OutQuint)."""

    def __init__(self, widget):
        self.widget = widget
        self.index = -1
        self.lo = self.hi = 0.0
        self.anim_lo, self.anim_hi = self._make_anim("lo"), self._make_anim("hi")

    def _make_anim(self, attr):
        anim = QVariantAnimation(self.widget)

        def _on_value(v, a=attr):
            setattr(self, a, float(v))
            self.widget.update()

        anim.valueChanged.connect(_on_value)
        return anim

    def morph_to(self, index, animate=True):
        prev, self.index = self.index, index
        if index >= 0 and (prev < 0 or not animate):
            self.anim_lo.stop()
            self.anim_hi.stop()
            self.lo = self.hi = float(index)
        elif index >= 0 and index != prev:
            lead, trail = (self.anim_hi, self.anim_lo) if index > prev else (self.anim_lo, self.anim_hi)
            for anim, ms, curve in ((lead, LEAD_MS, QEasingCurve.Type.OutCubic),
                                    (trail, TRAIL_MS, QEasingCurve.Type.OutQuint)):
                anim.stop()
                anim.setDuration(ms)
                anim.setEasingCurve(curve)
                anim.setStartValue(self.hi if anim is self.anim_hi else self.lo)
                anim.setEndValue(float(index))
                anim.start()
        self.widget.update()

    def span(self, edges):
        """edges: [(start, end)] pixel extents per item -> interpolated (start, end) of the capsule."""
        def at(pos, k):
            pos = min(max(pos, 0.0), len(edges) - 1.0)
            i = int(pos)
            j = min(i + 1, len(edges) - 1)
            return edges[i][k] + (edges[j][k] - edges[i][k]) * (pos - i)
        return at(self.lo, 0), at(self.hi, 1)


def draw_capsule(p, rect):
    """Cyan neon capsule (same look as the MorphingTabBar indicator)."""
    rad = min(rect.height(), rect.width()) / 2
    p.setPen(QPen(HUD_CYAN, 1.5))
    p.setBrush(IND_FILL)
    p.drawRoundedRect(rect.adjusted(0.75, 0.75, -0.75, -0.75), rad, rad)


class _MorphingButtonFrame(QFrame):
    """Dark HUD frame painting a morphing cyan capsule behind its checked child button."""
    VERTICAL = True
    INSET = 4.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = []
        self.morph = EdgeMorpher(self)

    def add_button(self, btn):
        self.buttons.append(btn)
        self.layout().addWidget(btn)
        btn.toggled.connect(self._sync)

    def _sync(self, *_):
        idx = next((i for i, b in enumerate(self.buttons) if b.isChecked()), -1)
        self.morph.morph_to(idx, animate=self.isVisible())

    def indicator_rect(self):
        if self.morph.index < 0 or not self.buttons:
            return QRectF()
        geos = [b.geometry() for b in self.buttons]
        if self.VERTICAL:
            a, b = self.morph.span([(g.top(), g.bottom() + 1) for g in geos])
            return QRectF(self.INSET, a, self.width() - 2 * self.INSET, b - a)
        a, b = self.morph.span([(g.left(), g.right() + 1) for g in geos])
        return QRectF(a, self.INSET, b - a, self.height() - 2 * self.INSET)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        outer = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = 10.0 if self.VERTICAL else outer.height() / 2
        p.setPen(QPen(BAR_BORDER, 1.0))
        p.setBrush(BAR_BG)
        p.drawRoundedRect(outer, rad, rad)
        ind = self.indicator_rect()
        if not ind.isEmpty():
            draw_capsule(p, ind)
        p.end()


class MorphingSelectFrame(_MorphingButtonFrame):
    """Vertical radio list (persona modes) with a morphing selection capsule."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_top, self._anim_bot = self.morph.anim_lo, self.morph.anim_hi
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(4)


class MorphingPresetFrame(_MorphingButtonFrame):
    """Horizontal capsule bar (context presets) with a morphing selection capsule."""
    VERTICAL = False
    INSET = 3.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._anim_left, self._anim_right = self.morph.anim_lo, self.morph.anim_hi
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)

ACCENT_BUTTON_STYLE = """
    QPushButton {
        background: rgba(0, 229, 255, 0.08);
        color: #00e5ff;
        border: 1px solid rgba(0, 229, 255, 0.45);
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 11px;
        font-weight: bold;
    }
    QPushButton:hover {
        background: rgba(0, 229, 255, 0.18);
        color: #ffffff;
        border: 1px solid #00e5ff;
    }
    QPushButton:pressed {
        background: rgba(0, 229, 255, 0.28);
    }
    QPushButton:disabled {
        color: #475569;
        border: 1px solid #334155;
    }
"""

REMOTE_DESCRIPTION_CLOUD = ("질문과 대화 내용이 {label} 서버로 전송되며 사용량만큼 요금이 부과될 수 있습니다. "
                            "키는 Windows 계정으로 암호화해 이 PC에만 저장합니다.")
REMOTE_DESCRIPTIONS = {
    "ollama": "외부(또는 이 PC)에서 실행 중인 Ollama 서버의 주소와 API 키를 입력합니다. "
              "키는 Bearer 헤더로 보내며 이 PC에만 암호화해 저장합니다. 인증 없는 서버면 키는 비워 두십시오.",
    "openai_compat": "OpenAI 호환 주소를 입력합니다. 예: https://openrouter.ai/api/v1, https://api.groq.com/openai/v1, "
                     "http://localhost:1234/v1 (LM Studio). 키는 이 PC에만 암호화해 저장합니다.",
}


class OrdisPersonaDialog(FramelessDialog):
    """WF-Companion Settings & Cephalon Ordis Persona Customization Dialog.
    Frameless, draggable, and themed for Warframe dark HUD aesthetics.
    """
    # (ok, message, installed Ollama models or None), from the connection-test thread.
    connection_tested = pyqtSignal(bool, str, object)

    def __init__(self, persona_manager: Optional[PersonaManager] = None, parent=None,
                 api_keys: Optional[ApiKeyStore] = None):
        super().__init__(parent)
        self.persona_manager = persona_manager or PersonaManager()
        self.api_keys = api_keys or ApiKeyStore()
        # Unsaved address/model/key per hosted provider, so flipping the engine combo loses no typing.
        self._remote_drafts = {}
        self._shown_provider = None
        self.init_ui()
        self.connection_tested.connect(self._on_connection_tested)

    def init_ui(self):
        self.setWindowTitle("워프레임 컴패니언 설정 (Settings)")
        # 720 tall: the engine tab's sections need ~520px; at 680 the inputs were squeezed. Still fits a 768px screen.
        self.setFixedSize(540, 720)

        self.setStyleSheet("""
            QDialog {
                background: transparent;
            }
            QFrame#mainCard {
                background-color: #0c1017;
                border: 1.5px solid #00d2ff;
                border-radius: 18px;
                color: #e2e8f0;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 12px;
            }
            QTabWidget::pane {
                border: 1px solid rgba(0, 210, 255, 0.25);
                border-radius: 10px;
                background: rgba(14, 20, 31, 0.7);
                top: -1px;
            }
            QTabBar::tab {
                background: #111722;
                color: #94a3b8;
                border: 1px solid #1e293b;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 8px 18px;
                font-size: 12px;
                font-weight: bold;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #182234;
                color: #00e5ff;
                border: 1px solid #00d2ff;
                border-bottom: 1px solid #182234;
            }
            QTabBar::tab:hover:!selected {
                color: #e2e8f0;
                background: #162030;
            }
            QRadioButton {
                color: #cbd5e1;
                font-size: 13px;
                padding: 4px;
            }
            QRadioButton:hover {
                color: #00e5ff;
            }
            QRadioButton:checked {
                color: #ffffff;
            }
            QRadioButton::indicator {
                width: 16px;
                height: 16px;
                border-radius: 8px;
                border: 1.5px solid #334155;
                background: #161e2e;
            }
            QRadioButton::indicator:checked {
                background: #00d2ff;
                border: 1.5px solid #ffffff;
            }
            QLineEdit, QSpinBox, QComboBox {
                background-color: #111722;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #f8fafc;
                font-size: 12px;
                padding: 6px 10px;
            }
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
                border: 1px solid #00d2ff;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QTextEdit {
                background-color: #111722;
                border: 1px solid #1e293b;
                border-radius: 8px;
                color: #f8fafc;
                font-size: 12px;
                padding: 8px;
            }
            QTextEdit:focus {
                border: 1px solid #00d2ff;
            }
        """)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)

        main_card = QFrame()
        main_card.setObjectName("mainCard")
        self.main_card = main_card
        # No drag binding on the card: hijacking its mouse events cancelled clicks on
        # radios/tabs/buttons. The window is moved only via the title bar header.
        card_layout = QVBoxLayout(main_card)
        card_layout.setContentsMargins(16, 12, 16, 16)
        card_layout.setSpacing(10)

        # 1. Custom Frameless Titlebar (using FramelessDialog SSOT title bar)
        header = self.create_title_bar(
            title="워프레임 컴패니언 설정 (WF-Companion Settings)",
            on_close=self.reject,
            icon_name="settings"
        )
        card_layout.addWidget(header)

        # 2. Tabs Widget: Tab 1 = Persona, Tab 2 = Local Model & Engine.
        # The native tab bar is hidden; the chat window's MorphingTabBar drives it instead.
        self.morphing_tab_bar = MorphingTabBar(self)
        card_layout.addWidget(self.morphing_tab_bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.tab_widget = QTabWidget()
        self.tab_widget.setIconSize(QSize(18, 18))
        self.tab_widget.tabBar().hide()
        card_layout.addWidget(self.tab_widget)

        # -------------------------------------------------------------
        # TAB 1: 세팔론 오디스 성격 커스터마이징
        # -------------------------------------------------------------
        persona_tab = QWidget()
        pt_layout = QVBoxLayout(persona_tab)
        pt_layout.setContentsMargins(12, 12, 12, 12)
        pt_layout.setSpacing(10)

        # Cephalon Ordis Logo & Header Banner
        banner_frame = QFrame()
        banner_frame.setStyleSheet("background: rgba(18, 24, 38, 0.7); border: 1px solid rgba(0, 210, 255, 0.25); border-radius: 10px; padding: 6px;")
        banner_layout = QHBoxLayout(banner_frame)
        banner_layout.setContentsMargins(8, 6, 8, 6)
        banner_layout.setSpacing(12)
        banner_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # Logo Image (vertically centered with the banner text)
        logo_lbl = QLabel()
        logo_pix = load_icon_pixmap("ordis_logo")
        if logo_pix and not logo_pix.isNull():
            logo_lbl.setPixmap(logo_pix.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        logo_lbl.setFixedSize(58, 58)
        logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner_layout = banner_layout
        self.banner_logo_lbl = logo_lbl
        banner_layout.addWidget(logo_lbl, alignment=Qt.AlignmentFlag.AlignVCenter)

        # Title + Description in banner
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title_lbl = QLabel("세팔론 오디스 성격 및 말투 커스터마이징")
        title_lbl.setStyleSheet("color: #00e5ff; font-size: 14px; font-weight: bold;")
        text_col.addWidget(title_lbl)

        sub_lbl = QLabel("오디스가 대화나 조언 시 사용할 기본 페르소나와 성격 모드를 선택하십시오.")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sub_lbl.setWordWrap(True)
        text_col.addWidget(sub_lbl)
        banner_layout.addLayout(text_col)
        banner_layout.setAlignment(text_col, Qt.AlignmentFlag.AlignVCenter)

        pt_layout.addWidget(banner_frame)

        # Radio button selection frame (morphing cyan capsule follows the checked radio)
        radio_frame = MorphingSelectFrame()
        self.radio_frame = radio_frame

        self.btn_group = QButtonGroup(self)
        self.radio_random = QRadioButton("[랜덤 변주]  매번 3가지 성격 중 무작위 변신")
        self.radio_caretaker = QRadioButton("[충성스러운 집사]  오퍼레이터 안전 최우선 다정한 말투")
        self.radio_glitch = QRadioButton("[글리치 모드]  살벌한 속마음이 튀어나오는 원작 오디스")
        self.radio_tactical = QRadioButton("[냉철한 전술장교]  군더더기 없는 신속 정확한 전황 보고")
        self.radio_custom = QRadioButton("[사용자 직접 설정]  나만의 프롬프트 지침 입력")

        self.btn_group.addButton(self.radio_random, 0)
        self.btn_group.addButton(self.radio_caretaker, 1)
        self.btn_group.addButton(self.radio_glitch, 2)
        self.btn_group.addButton(self.radio_tactical, 3)
        self.btn_group.addButton(self.radio_custom, 4)

        for btn in [self.radio_random, self.radio_caretaker, self.radio_glitch, self.radio_tactical, self.radio_custom]:
            radio_frame.add_button(btn)
            btn.toggled.connect(self.on_mode_changed)

        pt_layout.addWidget(radio_frame)

        # Description / Preview Box
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet("background: #141c2b; border: 1px solid #233147; border-radius: 8px; padding: 8px; color: #38bdf8; font-size: 11px; line-height: 1.4;")
        self.lbl_preview.setWordWrap(True)
        pt_layout.addWidget(self.lbl_preview)

        # Custom Prompt Edit Area
        self.lbl_custom_title = QLabel("사용자 지정 프롬프트 (오디스에게 부여할 성격 지침):")
        self.lbl_custom_title.setStyleSheet("color: #e2e8f0; font-weight: bold; font-size: 11px;")
        pt_layout.addWidget(self.lbl_custom_title)

        self.edit_custom = QTextEdit()
        self.edit_custom.setPlaceholderText("예: 당신은 츤데레 성격의 오디스입니다. 겉으로는 툴툴대면서도 오퍼레이터를 누구보다 챙겨주며 답변하세요.")
        self.edit_custom.setText(self.persona_manager.get_custom_prompt())
        self.edit_custom.setFixedHeight(75)
        pt_layout.addWidget(self.edit_custom)

        self.tab_widget.addTab(persona_tab, self._tab_icon("persona"), "성격 및 페르소나")

        # -------------------------------------------------------------
        # TAB 2: AI 엔진(로컬 llama.cpp / Ollama / 외부 API) & 모델 설정
        # -------------------------------------------------------------
        model_tab = QWidget()
        mt_layout = QVBoxLayout(model_tab)
        mt_layout.setContentsMargins(14, 14, 14, 14)
        mt_layout.setSpacing(12)

        # Master switch: OFF frees the VRAM; diagnosis and damage math keep working without the LLM.
        # The engine choice shares its row, so the local-only layout keeps its old height.
        engine_row = QHBoxLayout()
        self.cb_llm_enabled = QCheckBox("AI 대화 엔진 활성화")
        self.cb_llm_enabled.setChecked(self.persona_manager.get_llm_enabled())
        self.cb_llm_enabled.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: bold;")
        engine_lbl = QLabel("엔진:")
        engine_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        self.provider_combo = QComboBox()
        for provider_id, meta in PROVIDERS.items():
            self.provider_combo.addItem(meta["label"], provider_id)
        self.provider_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.provider_combo.setMinimumContentsLength(14)
        self.provider_combo.view().setMinimumWidth(330)
        engine_row.addWidget(self.cb_llm_enabled)
        engine_row.addStretch()
        engine_row.addWidget(engine_lbl)
        engine_row.addWidget(self.provider_combo, 1)
        mt_layout.addLayout(engine_row)

        # Section 1: GGUF Model Path Selection (bundled engine only)
        self.local_model_box = self._section_box()
        lm_layout = self.local_model_box.layout()
        mt_layout.addWidget(self.local_model_box)
        self.sec1_header, self.sec1_icon, self.sec1_title = self._make_section_header(
            "model", "로컬 GGUF 모델 파일 지정")
        lm_layout.addWidget(self.sec1_header)

        sec1_desc = QLabel("원하는 llama.cpp 호환 `.gguf` 모델 파일을 지정하면 오디스 대화 엔진에 즉시 적용됩니다.")
        sec1_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sec1_desc.setWordWrap(True)
        lm_layout.addWidget(sec1_desc)

        # Preset / detected models combo
        combo_box = QHBoxLayout()
        combo_lbl = QLabel("감지된 모델:")
        combo_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; min-width: 70px;")
        self.model_combo = QComboBox()
        self._populate_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_combo_selected)
        combo_box.addWidget(combo_lbl)
        combo_box.addWidget(self.model_combo)
        lm_layout.addLayout(combo_box)

        # Path input line + Browse button
        path_box = QHBoxLayout()
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setText(self.persona_manager.get_model_path())
        self.model_path_edit.setPlaceholderText("GGUF 모델 파일 전체 경로 (예: models/my_model.gguf)")
        self.btn_browse = QPushButton(" 찾아보기")
        browse_pix = load_icon_pixmap("browse")
        if browse_pix and not browse_pix.isNull():
            self.btn_browse.setIcon(QIcon(browse_pix))
            self.btn_browse.setIconSize(QSize(18, 18))
        self.btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_browse.setStyleSheet("""
            QPushButton {
                background: rgba(0, 229, 255, 0.08);
                color: #00e5ff;
                border: 1px solid rgba(0, 229, 255, 0.45);
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(0, 229, 255, 0.18);
                color: #ffffff;
                border: 1px solid #00e5ff;
            }
            QPushButton:pressed {
                background: rgba(0, 229, 255, 0.28);
            }
        """)
        self.btn_browse.clicked.connect(self.browse_model_file)
        path_box.addWidget(self.model_path_edit)
        path_box.addWidget(self.btn_browse)
        lm_layout.addLayout(path_box)

        # Section 1b: Ollama / hosted API connection (replaces section 1 and 3 when chosen)
        self.remote_box = self._section_box()
        self._build_remote_section(self.remote_box.layout())
        mt_layout.addWidget(self.remote_box)

        # Section 2: Context Length (n_ctx) - the bundled engine and Ollama (num_ctx) use it
        self.context_box = self._section_box()
        ctx_layout = self.context_box.layout()
        mt_layout.addWidget(self.context_box)
        self.sec2_header, self.sec2_icon, self.sec2_title = self._make_section_header(
            "context", "컨텍스트 길이 (Context Size / Token Window)", top_margin=10)
        ctx_layout.addWidget(self.sec2_header)

        sec2_desc = QLabel("대화 기억 및 공략 문맥 길이를 조절합니다. (4096 = 기본 권장, 8192/16384 = 대용량 컨텍스트)")
        sec2_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sec2_desc.setWordWrap(True)
        ctx_layout.addWidget(sec2_desc)

        ctx_box = QHBoxLayout()
        self.context_size_spin = QSpinBox()
        self.context_size_spin.setRange(512, 65536)
        self.context_size_spin.setSingleStep(1024)
        self.context_size_spin.setValue(self.persona_manager.get_context_size())
        self.context_size_spin.setSuffix(" 토큰")

        # Quick preset buttons inside a capsule bar with a morphing selection capsule
        self.preset_frame = self.preset_bar = MorphingPresetFrame()
        self.ctx_preset_buttons = {}
        for val in [2048, 4096, 8192, 16384]:
            btn = QPushButton(f"{val}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #94a3b8;
                    border: none;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover { color: #00e5ff; }
                QPushButton:checked { color: #ffffff; }
            """)
            # Re-sync after setValue: re-clicking the active preset must not leave it unchecked.
            btn.clicked.connect(lambda _, v=val: (self.context_size_spin.setValue(v), self._sync_ctx_presets(v)))
            self.ctx_preset_buttons[val] = btn
            self.preset_bar.add_button(btn)
        self.context_size_spin.valueChanged.connect(self._sync_ctx_presets)
        self._sync_ctx_presets(self.context_size_spin.value())

        ctx_box.addWidget(self.context_size_spin)
        ctx_box.addWidget(self.preset_bar)
        ctx_layout.addLayout(ctx_box)

        # Section 3: GPU Offload Layers (bundled engine only)
        self.gpu_box = self._section_box()
        gpu_layout = self.gpu_box.layout()
        mt_layout.addWidget(self.gpu_box)
        self.sec3_header, self.sec3_icon, self.sec3_title = self._make_section_header(
            "gpu", "GPU 가속 레이어 수 (n_gpu_layers)", top_margin=10)
        gpu_layout.addWidget(self.sec3_header)

        gpu_box = QHBoxLayout()
        self.gpu_layers_spin = QSpinBox()
        self.gpu_layers_spin.setRange(0, 128)
        self.gpu_layers_spin.setValue(self.persona_manager.get_gpu_layers())
        self.gpu_layers_spin.setSuffix(" 레이어")
        gpu_hint = QLabel("💡 99 = 전체 GPU 가속 (가장 빠름), 0 = CPU 전용")
        gpu_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        gpu_box.addWidget(self.gpu_layers_spin)
        gpu_box.addWidget(gpu_hint)
        gpu_box.addStretch()
        gpu_layout.addLayout(gpu_box)

        # Section 4: In-game input-driven pet motion (opt-in/out, zero-trace when OFF)
        self.cb_motion = QCheckBox("워프레임 인게임 입력 연동 펫 반응 모션 활성화 (WASD / Space / E / 마우스)")
        self.cb_motion.setChecked(self.persona_manager.get_motion_enabled())
        self.cb_motion.setStyleSheet("color: #e2e8f0; font-size: 12px; margin-top: 10px;")
        mt_layout.addWidget(self.cb_motion)
        motion_hint = QLabel("💡 워프레임 창 활성화 시에만 키를 감지해 펫이 점프/참격 모션을 취합니다. "
                             "비활성화 시 모든 키 감지 폴링(GetAsyncKeyState)과 백그라운드 타이머가 완전히 차단(OFF)됩니다.")
        motion_hint.setWordWrap(True)
        motion_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        mt_layout.addWidget(motion_hint)

        mt_layout.addStretch()
        self.tab_widget.addTab(model_tab, self._tab_icon("model"), "AI 엔진 & 모델")

        # Show the sections of the saved engine; the combo signal is connected after, so this load is silent.
        saved_provider = self.persona_manager.get_llm_provider()
        self.provider_combo.setCurrentIndex(max(0, self.provider_combo.findData(saved_provider)))
        self._show_provider(saved_provider)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        # Two-way sync: morphing bar <-> QTabWidget (indices/icons/texts stay owned by tab_widget)
        self.morphing_tab_bar.add_tab("성격 및 페르소나", icon_name="persona")
        self.morphing_tab_bar.add_tab("AI 엔진 & 모델", icon_name="model")
        self.morphing_tab_bar.tab_changed.connect(self.tab_widget.setCurrentIndex)
        self.tab_widget.currentChanged.connect(self._on_tab_widget_changed)
        self.morphing_tab_bar.switch_tab(self.tab_widget.currentIndex())

        # -------------------------------------------------------------
        # 3. Bottom Action Buttons (Save & Apply / Cancel)
        # -------------------------------------------------------------
        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        # Cancel button with project-matching icon
        self.btn_cancel = QPushButton(" 취소")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setMinimumWidth(110)
        cancel_pix = load_icon_pixmap("btn_cancel")
        if cancel_pix and not cancel_pix.isNull():
            self.btn_cancel.setIcon(QIcon(cancel_pix))
            self.btn_cancel.setIconSize(QSize(20, 20))
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 12px;
                font-weight: bold;
                padding: 0 14px;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
                border: 1px solid #64748b;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        # Save and Apply button with project-matching icon
        self.btn_save = QPushButton(" 저장 및 적용")
        self.btn_save.setFixedHeight(38)
        self.btn_save.setMinimumWidth(140)
        save_pix = load_icon_pixmap("btn_save")
        if save_pix and not save_pix.isNull():
            self.btn_save.setIcon(QIcon(save_pix))
            self.btn_save.setIconSize(QSize(20, 20))
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088cc, stop:1 #00d2ff);
                color: #0c1017;
                font-weight: bold;
                border-radius: 8px;
                border: none;
                font-size: 12px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00a0e9, stop:1 #38bdf8);
                color: #ffffff;
            }
        """)
        self.btn_save.clicked.connect(self.save)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        card_layout.addLayout(btn_box)

        root_layout.addWidget(main_card)

        # Initialize current persona state
        current_mode = self.persona_manager.get_mode()
        mode_map = {
            "random": self.radio_random,
            "caretaker": self.radio_caretaker,
            "glitch": self.radio_glitch,
            "tactical": self.radio_tactical,
            "custom": self.radio_custom
        }
        target_btn = mode_map.get(current_mode, self.radio_random)
        target_btn.setChecked(True)
        self.on_mode_changed()

    @staticmethod
    def _tab_icon(icon_name) -> QIcon:
        """Cyan HUD glyph from assets/icons as a tab QIcon (empty QIcon if missing)."""
        pix = load_icon_pixmap(icon_name)
        if pix and not pix.isNull():
            return QIcon(pix)
        return QIcon()

    def _make_section_header(self, icon_name, text, top_margin=0):
        """Build a HUD section header: glyph icon from assets/icons + cyan title label."""
        header = QWidget()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, top_margin, 0, 0)
        h_layout.setSpacing(8)
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(20, 20)
        pix = load_icon_pixmap(icon_name)
        if pix and not pix.isNull():
            icon_lbl.setPixmap(pix.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        title_lbl = QLabel(text)
        title_lbl.setStyleSheet("color: #00e5ff; font-weight: bold; font-size: 13px;")
        h_layout.addWidget(icon_lbl)
        h_layout.addWidget(title_lbl)
        h_layout.addStretch()
        return header, icon_lbl, title_lbl

    @staticmethod
    def _section_box() -> QWidget:
        """A margin-free container, so a whole section can be shown or hidden with the engine choice."""
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        return box

    def _build_remote_section(self, layout):
        self.sec_remote_header, self.sec_remote_icon, self.sec_remote_title = self._make_section_header(
            "status", "외부 AI 엔진 연결 (Ollama / API)")
        layout.addWidget(self.sec_remote_header)

        self.lbl_remote_desc = QLabel()
        self.lbl_remote_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        self.lbl_remote_desc.setWordWrap(True)
        layout.addWidget(self.lbl_remote_desc)

        self.base_url_edit = QLineEdit()
        self.remote_model_combo = QComboBox()
        self.remote_model_combo.setEditable(True)
        self.remote_model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        for text, widget in (("API 주소", self.base_url_edit), ("모델", self.remote_model_combo), ("API 키", self.api_key_edit)):
            row = QHBoxLayout()
            lbl = QLabel(f"{text}:")
            lbl.setFixedWidth(62)
            lbl.setStyleSheet("color: #cbd5e1; font-size: 11px;")
            row.addWidget(lbl)
            row.addWidget(widget, 1)
            layout.addLayout(row)

        test_row = QHBoxLayout()
        self.btn_test_connection = QPushButton(" 연결 테스트")
        refresh_pix = load_icon_pixmap("refresh")
        if refresh_pix and not refresh_pix.isNull():
            self.btn_test_connection.setIcon(QIcon(refresh_pix))
            self.btn_test_connection.setIconSize(QSize(16, 16))
        self.btn_test_connection.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_test_connection.setStyleSheet(ACCENT_BUTTON_STYLE)
        self.btn_test_connection.clicked.connect(self.test_connection)
        self.lbl_connection_status = QLabel("")
        self.lbl_connection_status.setWordWrap(True)
        self.lbl_connection_status.setStyleSheet("color: #94a3b8; font-size: 11px;")
        test_row.addWidget(self.btn_test_connection, alignment=Qt.AlignmentFlag.AlignTop)
        test_row.addWidget(self.lbl_connection_status, 1)
        layout.addLayout(test_row)

    def _on_provider_changed(self, idx):
        self._stash_remote_fields()
        self._show_provider(self.provider_combo.itemData(idx))

    def _show_provider(self, provider):
        is_local = provider == LOCAL_PROVIDER
        self.local_model_box.setVisible(is_local)
        self.gpu_box.setVisible(is_local)
        self.remote_box.setVisible(not is_local)
        # Ollama takes the context size per request (num_ctx); hosted APIs size it themselves.
        self.context_box.setVisible(is_local or PROVIDERS[provider]["protocol"] == "ollama")
        self._shown_provider = provider
        self._set_connection_status("", None)
        if not is_local:
            self._load_remote_fields(provider)

    def _load_remote_fields(self, provider):
        meta = PROVIDERS[provider]
        pm = self.persona_manager
        draft = self._remote_drafts.get(provider) or {
            "base_url": pm.get_llm_base_url(provider),
            "model": pm.get_llm_model(provider),
            "key": self.api_keys.saved(provider),
        }
        self.base_url_edit.setText(draft["base_url"])
        self.base_url_edit.setPlaceholderText(meta["base_url"] or "https://.../v1")

        self.remote_model_combo.clear()
        self.remote_model_combo.addItems(list(meta["models"]))
        self.remote_model_combo.setCurrentText(draft["model"])
        self.remote_model_combo.lineEdit().setPlaceholderText("모델 이름 (예: provider/model-name)")

        env = self.api_keys.env_name(provider)
        self.api_key_edit.setText(draft["key"])
        if env:
            placeholder = f"비워 두면 환경 변수 {env} 사용"
        elif meta["needs_key"]:
            placeholder = "API 키 입력"
        elif meta["protocol"] == "ollama":
            placeholder = "서버에 인증이 걸려 있으면 입력 (Bearer)"
        else:
            placeholder = "필요한 경우에만 입력"
        self.api_key_edit.setPlaceholderText(placeholder)
        self.lbl_remote_desc.setText(REMOTE_DESCRIPTIONS.get(provider) or REMOTE_DESCRIPTION_CLOUD.format(label=meta["label"]))

    def _stash_remote_fields(self):
        provider = self._shown_provider
        if provider and provider != LOCAL_PROVIDER:
            self._remote_drafts[provider] = {
                "base_url": self.base_url_edit.text().strip(),
                "model": self.remote_model_combo.currentText().strip(),
                "key": self.api_key_edit.text().strip(),
            }

    def _client_from_fields(self) -> LLMClient:
        provider = self.provider_combo.currentData()
        draft = self._remote_drafts.get(provider, {})
        env = self.api_keys.env_name(provider)
        key = draft.get("key") or (os.environ.get(env, "") if env else "")
        return LLMClient(provider, base_url=draft.get("base_url", ""), model=draft.get("model", ""),
                         api_key=key, context_size=self.context_size_spin.value())

    def _set_connection_status(self, text, ok):
        color = "#94a3b8" if ok is None else ("#4ade80" if ok else "#f87171")
        self.lbl_connection_status.setStyleSheet(f"color: {color}; font-size: 11px;")
        self.lbl_connection_status.setText(text)

    def test_connection(self):
        """Checks the fields as typed (not yet saved) in a worker thread; the result comes back via connection_tested."""
        self._stash_remote_fields()
        client = self._client_from_fields()
        if client.is_local:
            return
        provider = client.provider
        self.btn_test_connection.setEnabled(False)
        self._set_connection_status("연결 확인 중...", None)

        def work():
            models = client.list_models() if client.protocol == "ollama" else None
            ok, message = client.test_connection()
            try:
                self.connection_tested.emit(ok, message, {"provider": provider, "models": models})
            except RuntimeError:  # The dialog was closed and deleted meanwhile.
                pass

        threading.Thread(target=work, daemon=True).start()

    def _on_connection_tested(self, ok, message, extra):
        self.btn_test_connection.setEnabled(True)
        extra = extra or {}
        # The engine was switched while the test ran: the result is about another provider.
        if extra.get("provider") != self.provider_combo.currentData():
            return
        models = extra.get("models")
        if models:
            current = self.remote_model_combo.currentText()
            self.remote_model_combo.clear()
            self.remote_model_combo.addItems(models)
            self.remote_model_combo.setCurrentText(current)
        self._set_connection_status(f"{'연결 성공' if ok else '연결 실패'}: {message}", ok)

    def _on_tab_widget_changed(self, index):
        if index != self.morphing_tab_bar.active_index:
            self.morphing_tab_bar.switch_tab(index)

    def _sync_ctx_presets(self, value):
        for val, btn in self.ctx_preset_buttons.items():
            btn.setChecked(val == value)

    def _populate_model_combo(self):
        self.model_combo.clear()
        self.model_combo.addItem("직접 지정 / 외부 파일", "")

        models_dir = get_path("models")
        if os.path.exists(models_dir):
            for fname in os.listdir(models_dir):
                if fname.lower().endswith(".gguf"):
                    rel_p = f"models/{fname}"
                    self.model_combo.addItem(fname, rel_p)

        curr = self.persona_manager.get_model_path()
        for i in range(self.model_combo.count()):
            if self.model_combo.itemData(i) == curr:
                self.model_combo.setCurrentIndex(i)
                break

    def _on_model_combo_selected(self, idx):
        path = self.model_combo.itemData(idx)
        if path:
            self.model_path_edit.setText(path)

    def browse_model_file(self):
        curr_dir = os.path.dirname(self.model_path_edit.text() or get_path("models"))
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "GGUF 모델 파일 선택",
            curr_dir,
            "GGUF Models (*.gguf);;All Files (*.*)"
        )
        if file_path:
            # Prefer relative path if inside project root
            root = get_path()
            if file_path.startswith(root):
                rel_path = os.path.relpath(file_path, root).replace("\\", "/")
                self.model_path_edit.setText(rel_path)
            else:
                self.model_path_edit.setText(file_path)

    def on_mode_changed(self):
        is_custom = self.radio_custom.isChecked()
        self.edit_custom.setEnabled(is_custom)
        self.lbl_custom_title.setStyleSheet(
            "color: #00e5ff; font-weight: bold; font-size: 11px;" if is_custom
            else "color: #64748b; font-weight: normal; font-size: 11px;"
        )

        if self.radio_random.isChecked():
            self.lbl_preview.setText(
                "💬 <b>[랜덤 모드]</b>: 오디스가 매 대화마다 집사, 글리치, 전술장교 성격을 무작위로 오가며 다채로운 매력을 선보입니다."
            )
        elif self.radio_caretaker.isChecked():
            p = DEFAULT_PRESETS["caretaker"]
            self.lbl_preview.setText(f"💬 <b>[{p['name']}]</b>: {p['desc']}<br><i>\"오퍼레이터님, 다치신 곳은 없으십니까? 항상 안전이 최우선입니다!\"</i>")
        elif self.radio_glitch.isChecked():
            p = DEFAULT_PRESETS["glitch"]
            self.lbl_preview.setText(f"💬 <b>[{p['name']}]</b>: {p['desc']}<br><i>\"함선 시스템 정상 작동 중입니다... --적들의 뼈를 으스러뜨리십시오!-- ...오퍼레이터님?\"</i>")
        elif self.radio_tactical.isChecked():
            p = DEFAULT_PRESETS["tactical"]
            self.lbl_preview.setText(f"💬 <b>[{p['name']}]</b>: {p['desc']}<br><i>\"전장 분석 완료. 목표 지점 약점 타격 시 클리어 시간 35% 단축 예상됩니다.\"</i>")
        elif self.radio_custom.isChecked():
            self.lbl_preview.setText(
                "💬 <b>[사용자 직접 설정]</b>: 아래 입력란에 작성하신 성격 지침 및 말투를 오디스가 100% 충실히 반영하여 대화합니다."
            )

    def save(self):
        # 1. Save Persona Mode & Prompt
        if self.radio_random.isChecked():
            mode = "random"
        elif self.radio_caretaker.isChecked():
            mode = "caretaker"
        elif self.radio_glitch.isChecked():
            mode = "glitch"
        elif self.radio_tactical.isChecked():
            mode = "tactical"
        else:
            mode = "custom"

        custom_prompt = self.edit_custom.toPlainText().strip()
        self.persona_manager.set_mode(mode, custom_prompt)

        # 2. Save Model & Context Settings
        model_path = self.model_path_edit.text().strip()
        if model_path:
            self.persona_manager.set_model_path(model_path)

        context_size = self.context_size_spin.value()
        self.persona_manager.set_context_size(context_size)

        gpu_layers = self.gpu_layers_spin.value()
        self.persona_manager.set_gpu_layers(gpu_layers)

        self.persona_manager.set_motion_enabled(self.cb_motion.isChecked())
        self.persona_manager.set_llm_enabled(self.cb_llm_enabled.isChecked())

        # 3. Save the engine choice and every hosted provider the user looked at
        self._stash_remote_fields()
        for provider, draft in self._remote_drafts.items():
            self.persona_manager.set_llm_base_url(provider, draft["base_url"])
            self.persona_manager.set_llm_model(provider, draft["model"])
            if draft["key"] != self.api_keys.saved(provider):
                self.api_keys.set(provider, draft["key"])
        self.persona_manager.set_llm_provider(self.provider_combo.currentData())

        self.accept()


# Alias for unified naming
SettingsDialog = OrdisPersonaDialog

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = OrdisPersonaDialog()
    dlg.show()
    sys.exit(app.exec())
