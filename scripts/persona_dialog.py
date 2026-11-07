import os
import sys
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QDialog, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication,
        QTabWidget, QWidget, QLineEdit, QFileDialog, QSpinBox, QComboBox
    )
    from PyQt6.QtCore import Qt, QPoint, QSize
    from PyQt6.QtGui import QIcon, QPixmap
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication,
        QTabWidget, QWidget, QLineEdit, QFileDialog, QSpinBox, QComboBox
    )
    from PySide6.QtCore import Qt, QPoint, QSize
    from PySide6.QtGui import QIcon, QPixmap

from scripts.persona_manager import PersonaManager, DEFAULT_PRESETS
from scripts.hud_widgets import load_icon_pixmap, ICON_DIR
from scripts.path_config import get_path
from scripts.frameless_dialog import FramelessDialog

class OrdisPersonaDialog(FramelessDialog):
    """WF-Companion Settings & Cephalon Ordis Persona Customization Dialog.
    Frameless, draggable, and themed for Warframe dark HUD aesthetics.
    """
    def __init__(self, persona_manager: Optional[PersonaManager] = None, parent=None):
        super().__init__(parent)
        self.persona_manager = persona_manager or PersonaManager()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("워프레임 컴패니언 설정 (Settings)")
        self.setFixedSize(540, 680)

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
        # Card margins drag the dialog; child buttons/tabs consume their own clicks first.
        self.bind_drag_events(main_card)
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

        # 2. Tabs Widget: Tab 1 = Persona, Tab 2 = Local Model & Engine
        self.tab_widget = QTabWidget()
        self.tab_widget.setIconSize(QSize(18, 18))
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

        pt_layout.addWidget(banner_frame)

        # Radio button selection frame
        radio_frame = QFrame()
        radio_frame.setStyleSheet("background: rgba(18, 24, 38, 0.5); border: 1px solid #1e293b; border-radius: 10px; padding: 6px;")
        rf_layout = QVBoxLayout(radio_frame)
        rf_layout.setSpacing(6)

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
            rf_layout.addWidget(btn)
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
        # TAB 2: 로컬 모델 & LLM 엔진 설정
        # -------------------------------------------------------------
        model_tab = QWidget()
        mt_layout = QVBoxLayout(model_tab)
        mt_layout.setContentsMargins(14, 14, 14, 14)
        mt_layout.setSpacing(12)

        # Section 1: GGUF Model Path Selection
        self.sec1_header, self.sec1_icon, self.sec1_title = self._make_section_header(
            "model", "로컬 GGUF 모델 파일 지정")
        mt_layout.addWidget(self.sec1_header)

        sec1_desc = QLabel("원하는 llama.cpp 호환 `.gguf` 모델 파일을 지정하면 오디스 대화 엔진에 즉시 적용됩니다.")
        sec1_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sec1_desc.setWordWrap(True)
        mt_layout.addWidget(sec1_desc)

        # Preset / detected models combo
        combo_box = QHBoxLayout()
        combo_lbl = QLabel("감지된 모델:")
        combo_lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; min-width: 70px;")
        self.model_combo = QComboBox()
        self._populate_model_combo()
        self.model_combo.currentIndexChanged.connect(self._on_model_combo_selected)
        combo_box.addWidget(combo_lbl)
        combo_box.addWidget(self.model_combo)
        mt_layout.addLayout(combo_box)

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
        mt_layout.addLayout(path_box)

        # Section 2: Context Length (n_ctx)
        self.sec2_header, self.sec2_icon, self.sec2_title = self._make_section_header(
            "context", "컨텍스트 길이 (Context Size / Token Window)", top_margin=10)
        mt_layout.addWidget(self.sec2_header)

        sec2_desc = QLabel("대화 기억 및 공략 문맥 길이를 조절합니다. (4096 = 기본 권장, 8192/16384 = 대용량 컨텍스트)")
        sec2_desc.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sec2_desc.setWordWrap(True)
        mt_layout.addWidget(sec2_desc)

        ctx_box = QHBoxLayout()
        self.context_size_spin = QSpinBox()
        self.context_size_spin.setRange(512, 65536)
        self.context_size_spin.setSingleStep(1024)
        self.context_size_spin.setValue(self.persona_manager.get_context_size())
        self.context_size_spin.setSuffix(" 토큰")

        # Quick preset buttons
        preset_box = QHBoxLayout()
        preset_box.setSpacing(6)
        self.ctx_preset_buttons = {}
        for val in [2048, 4096, 8192, 16384]:
            btn = QPushButton(f"{val}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #162030;
                    color: #94a3b8;
                    border: 1px solid #24324d;
                    border-radius: 10px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #24324d;
                    color: #00e5ff;
                    border: 1px solid rgba(0, 229, 255, 0.45);
                }
                QPushButton:checked {
                    background: rgba(0, 229, 255, 0.18);
                    color: #00e5ff;
                    border: 1px solid #00e5ff;
                }
            """)
            btn.clicked.connect(lambda _, v=val: self.context_size_spin.setValue(v))
            self.ctx_preset_buttons[val] = btn
            preset_box.addWidget(btn)
        self.context_size_spin.valueChanged.connect(self._sync_ctx_presets)
        self._sync_ctx_presets(self.context_size_spin.value())

        ctx_box.addWidget(self.context_size_spin)
        ctx_box.addLayout(preset_box)
        mt_layout.addLayout(ctx_box)

        # Section 3: GPU Offload Layers
        self.sec3_header, self.sec3_icon, self.sec3_title = self._make_section_header(
            "gpu", "GPU 가속 레이어 수 (n_gpu_layers)", top_margin=10)
        mt_layout.addWidget(self.sec3_header)

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
        mt_layout.addLayout(gpu_box)

        mt_layout.addStretch()
        self.tab_widget.addTab(model_tab, self._tab_icon("model"), "로컬 모델 & 엔진")

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

        self.accept()


# Alias for unified naming
SettingsDialog = OrdisPersonaDialog

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = OrdisPersonaDialog()
    dlg.show()
    sys.exit(app.exec())
