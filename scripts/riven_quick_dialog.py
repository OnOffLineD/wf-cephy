from typing import Dict

try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout
    from PyQt6.QtCore import Qt
except ImportError:
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout
    from PySide6.QtCore import Qt

from scripts.riven_reroll_reader import parse_riven_input
from scripts.frameless_dialog import apply_frameless_shell

STAT_CHOICES = ['치확', '치피', '멀샷', '피해', '공속', '탄창', '재장전', '화염', '냉기', '전기', '독성', '충격', '관통', '베기', '상태이상']


class RivenQuickInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('리벤 모드 옵션 간편 입력')
        self.setFixedSize(400, 470)
        self.setStyleSheet('QDialog { background-color: #0c1017; color: #FFFFFF; border: 1.5px solid #00d2ff; border-radius: 14px; } QLabel { color: #94a3b8; font-size: 12px; } QLineEdit { background: #161e2e; color: #ffffff; border: 1px solid #24324d; border-radius: 6px; padding: 6px; } QComboBox { background: #161e2e; color: #ffffff; border: 1px solid #24324d; border-radius: 6px; padding: 4px; } QPushButton { border-radius: 6px; font-weight: bold; padding: 8px; }')

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        header = apply_frameless_shell(self, title='리벤 모드 옵션 간편 입력', on_close=self.reject)
        layout.addWidget(header)

        # Quick input at top
        self.quick_input = QLineEdit(self)
        self.quick_input.setPlaceholderText('예: 치확 150 치피 120 멀샷 90 (단축어 또는 숫자만 입력 가능)')
        layout.addWidget(self.quick_input)

        # Section for 3 positive stats combos + line_edits
        self.positive_stats_layout = QGridLayout()
        self.positive_stats = []
        for i in range(3):
            label = QLabel(f'Positive Stat {i+1}', self)
            combo = QComboBox(self)
            combo.addItems(STAT_CHOICES)
            line_edit = QLineEdit(self)
            self.positive_stats.append((combo, line_edit))
            self.positive_stats_layout.addWidget(label, i, 0)
            self.positive_stats_layout.addWidget(combo, i, 1)
            self.positive_stats_layout.addWidget(line_edit, i, 2)
        layout.addLayout(self.positive_stats_layout)

        # Section for 1 curse combo + line_edit
        self.curse_label = QLabel('Curse', self)
        self.curse_combo = QComboBox(self)
        self.curse_combo.addItems(STAT_CHOICES)
        self.curse_line_edit = QLineEdit(self)
        self.curse_layout = QHBoxLayout()
        self.curse_layout.addWidget(self.curse_label)
        self.curse_layout.addWidget(self.curse_combo)
        self.curse_layout.addWidget(self.curse_line_edit)
        layout.addLayout(self.curse_layout)

        # Bottom buttons
        self.apply_button = QPushButton('Apply', self)
        self.apply_button.setStyleSheet('QPushButton { background-color: #00bfff; }')
        self.apply_button.clicked.connect(self.on_apply)
        self.cancel_button = QPushButton('Cancel', self)
        self.cancel_button.clicked.connect(self.reject)
        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.apply_button)
        self.button_layout.addWidget(self.cancel_button)
        layout.addLayout(self.button_layout)

    def on_apply(self):
        self.accept()

    def get_stats(self) -> Dict[str, float]:
        # All values are percents, and the curse is always a penalty whichever sign was typed.
        parts = [self.quick_input.text().strip()]
        for combo, line_edit in self.positive_stats:
            if line_edit.text().strip():
                parts.append(f"{combo.currentText()} {line_edit.text().strip()}")
        curse_value = self.curse_line_edit.text().strip().lstrip('+-')
        if curse_value:
            parts.append(f"{self.curse_combo.currentText()} -{curse_value}")
        return parse_riven_input(" ".join(parts))