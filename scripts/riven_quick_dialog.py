import re
from typing import Dict

try:
    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout
    from PyQt6.QtCore import Qt
except ImportError:
    from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout
    from PySide6.QtCore import Qt

class RivenQuickInputDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('리벤 모드 옵션 간편 입력')
        self.setFixedSize(380, 420)
        self.setStyleSheet('QDialog { background-color: #0d131f; color: #FFFFFF; border: 1px solid #1e293b; border-radius: 12px; } QLabel { color: #94a3b8; font-size: 12px; } QLineEdit { background: #161e2e; color: #ffffff; border: 1px solid #24324d; border-radius: 6px; padding: 6px; } QComboBox { background: #161e2e; color: #ffffff; border: 1px solid #24324d; border-radius: 6px; padding: 4px; } QPushButton { border-radius: 6px; font-weight: bold; padding: 8px; }')
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

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
            combo.addItems(['치확', '치피', '멀샷', '피해', '공속'])
            line_edit = QLineEdit(self)
            self.positive_stats.append((combo, line_edit))
            self.positive_stats_layout.addWidget(label, i, 0)
            self.positive_stats_layout.addWidget(combo, i, 1)
            self.positive_stats_layout.addWidget(line_edit, i, 2)
        layout.addLayout(self.positive_stats_layout)

        # Section for 1 curse combo + line_edit
        self.curse_label = QLabel('Curse', self)
        self.curse_combo = QComboBox(self)
        self.curse_combo.addItems(['치명', '분산', '재사용'])
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
        stats = {}

        # Check quick input
        quick_input_text = self.quick_input.text().strip()
        if quick_input_text:
            pattern = re.compile(r'(\w+)\s+(\d+\.?\d*)')
            matches = pattern.findall(quick_input_text)
            for label, value in matches:
                if label in ['치확', 'crit_chance', 'cc']:
                    stats['crit_chance'] = float(value) / 100
                elif label in ['치피', 'crit_damage', 'cd']:
                    stats['crit_damage'] = float(value) / 100
                elif label in ['멀샷', 'multishot', 'ms']:
                    stats['multishot'] = float(value) / 100
                elif label in ['피해', 'base_damage', 'dmg']:
                    stats['base_damage'] = float(value)
                elif label in ['공속', 'fire_rate', 'fr']:
                    stats['fire_rate'] = float(value)

        # Check positive combos and curse combo
        for combo, line_edit in self.positive_stats:
            label = combo.currentText()
            value_text = line_edit.text().strip()
            if value_text:
                try:
                    value = float(value_text)
                    if abs(value) > 3.0:
                        value /= 100
                    if label in ['치확', 'crit_chance', 'cc']:
                        stats['crit_chance'] = value
                    elif label in ['치피', 'crit_damage', 'cd']:
                        stats['crit_damage'] = value
                    elif label in ['멀샷', 'multishot', 'ms']:
                        stats['multishot'] = value
                except ValueError:
                    pass

        curse_label = self.curse_combo.currentText()
        curse_value_text = self.curse_line_edit.text().strip()
        if curse_value_text:
            try:
                curse_value = float(curse_value_text)
                if abs(curse_value) > 3.0:
                    curse_value /= 100
                if curse_label in ['치명', 'critical_chance', 'cc']:
                    stats['critical_chance'] = -curse_value
                elif curse_label in ['분산', 'dispersion', 'd']:
                    stats['dispersion'] = -curse_value
                elif curse_label in ['재사용', 'reload', 'r']:
                    stats['reload'] = -curse_value
            except ValueError:
                pass

        return stats