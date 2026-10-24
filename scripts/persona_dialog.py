import sys
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QDialog, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication
    )
    from PyQt6.QtCore import Qt
except ImportError:
    from PySide6.QtWidgets import (
        QDialog, QRadioButton, QButtonGroup, QTextEdit, QPushButton,
        QVBoxLayout, QHBoxLayout, QLabel, QFrame, QApplication
    )
    from PySide6.QtCore import Qt

from scripts.persona_manager import PersonaManager, DEFAULT_PRESETS

class OrdisPersonaDialog(QDialog):
    def __init__(self, persona_manager: Optional[PersonaManager] = None, parent=None):
        super().__init__(parent)
        self.persona_manager = persona_manager or PersonaManager()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("세팔론 오디스 성격 및 페르소나 설정")
        self.setFixedSize(480, 560)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #0c1017;
                border: 1.5px solid #00d2ff;
                border-radius: 16px;
                color: #e2e8f0;
            }
            QLabel {
                color: #e2e8f0;
                font-size: 12px;
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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Header Title
        title_lbl = QLabel("🎭 세팔론 오디스 성격 및 말투 커스터마이징")
        title_lbl.setStyleSheet("color: #00e5ff; font-size: 15px; font-weight: bold;")
        layout.addWidget(title_lbl)

        sub_lbl = QLabel("오디스가 대화나 미션 조언 시 사용할 기본 페르소나와 성격 모드를 선택하십시오.")
        sub_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        sub_lbl.setWordWrap(True)
        layout.addWidget(sub_lbl)

        # Radio button selection frame
        radio_frame = QFrame()
        radio_frame.setStyleSheet("background: rgba(18, 24, 38, 0.7); border: 1px solid #1e293b; border-radius: 10px; padding: 10px;")
        rf_layout = QVBoxLayout(radio_frame)
        rf_layout.setSpacing(8)

        self.btn_group = QButtonGroup(self)
        self.radio_random = QRadioButton("🎲  랜덤 변주 (매번 3가지 성격 중 무작위 변신)")
        self.radio_caretaker = QRadioButton("🛡️  충성스러운 집사 (오퍼레이터 안전 최우선 다정한 말투)")
        self.radio_glitch = QRadioButton("⚡  욱하는 글리치 (살벌한 속마음이 튀어나오는 원작 오디스)")
        self.radio_tactical = QRadioButton("🎯  냉철한 전술장교 (군더더기 없는 신속 정확한 전황 보고)")
        self.radio_custom = QRadioButton("✏️  사용자 직접 설정 (나만의 프롬프트 지침 입력)")

        self.btn_group.addButton(self.radio_random, 0)
        self.btn_group.addButton(self.radio_caretaker, 1)
        self.btn_group.addButton(self.radio_glitch, 2)
        self.btn_group.addButton(self.radio_tactical, 3)
        self.btn_group.addButton(self.radio_custom, 4)

        for btn in [self.radio_random, self.radio_caretaker, self.radio_glitch, self.radio_tactical, self.radio_custom]:
            rf_layout.addWidget(btn)
            btn.toggled.connect(self.on_mode_changed)

        layout.addWidget(radio_frame)

        # Description / Preview Box
        self.lbl_preview = QLabel()
        self.lbl_preview.setStyleSheet("background: #141c2b; border: 1px solid #233147; border-radius: 8px; padding: 10px; color: #38bdf8; font-size: 11px; line-height: 1.4;")
        self.lbl_preview.setWordWrap(True)
        layout.addWidget(self.lbl_preview)

        # Custom Prompt Edit Area
        self.lbl_custom_title = QLabel("✏️ 사용자 지정 프롬프트 (오디스에게 부여할 성격 지침):")
        self.lbl_custom_title.setStyleSheet("color: #e2e8f0; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_custom_title)

        self.edit_custom = QTextEdit()
        self.edit_custom.setPlaceholderText("예: 당신은 츤데레 성격의 오디스입니다. 겉으로는 툴툴대면서도 오퍼레이터를 누구보다 챙겨주며 답변하세요.")
        self.edit_custom.setText(self.persona_manager.get_custom_prompt())
        self.edit_custom.setFixedHeight(95)
        layout.addWidget(self.edit_custom)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        btn_box.setSpacing(10)

        self.btn_save = QPushButton("💾 저장 및 적용")
        self.btn_save.setFixedHeight(36)
        self.btn_save.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088cc, stop:1 #00d2ff);
                color: #0c1017;
                font-weight: bold;
                border-radius: 8px;
                border: none;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #38bdf8;
                color: #ffffff;
            }
        """)
        self.btn_save.clicked.connect(self.save)

        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setFixedHeight(36)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #334155;
                color: #ffffff;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        btn_box.addStretch()
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

        # Initialize current state from persona_manager
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
        self.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dlg = OrdisPersonaDialog()
    dlg.show()
    sys.exit(app.exec())
