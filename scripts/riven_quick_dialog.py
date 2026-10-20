import sys
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox, QGridLayout, QWidget, QStyleFactory
from PyQt6.QtCore import Qt

class RivenQuickInputDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Riven Quick Input Dialog")
        self.setStyleSheet("QDialog {background-color: #121212; color: #FFFFFF;}")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Positive Stats Section
        positive_stats_layout = QGridLayout()
        positive_stats_layout.addWidget(QLabel("Positive Stats"), 0, 0, 1, 2)
        self.positive_stats = []
        for i in range(3):
            combo = QComboBox()
            combo.addItems(["crit_chance", "crit_damage", "base_damage", "multishot", "fire_rate", "toxin", "heat", "electricity", "cold", "status_chance", "slash", "impact", "puncture", "faction_damage", "magazine_capacity", "reload_speed", "initial_combo"])
            line_edit = QLineEdit()
            positive_stats_layout.addWidget(combo, i + 1, 0)
            positive_stats_layout.addWidget(line_edit, i + 1, 1)
            self.positive_stats.append((combo, line_edit))

        layout.addLayout(positive_stats_layout)

        # Curse Section
        curse_layout = QHBoxLayout()
        curse_layout.addWidget(QLabel("Curse"))
        self.curse_combo = QComboBox()
        self.curse_combo.addItems(["zoom", "recoil", "crit_chance", "crit_damage", "base_damage", "multishot", "fire_rate"])
        curse_layout.addWidget(self.curse_combo)
        self.curse_value = QLineEdit()
        curse_layout.addWidget(self.curse_value)
        layout.addLayout(curse_layout)

        # Quick Input Section
        quick_input_layout = QHBoxLayout()
        quick_input_layout.addWidget(QLabel("Quick Input"))
        self.quick_input = QLineEdit()
        quick_input_layout.addWidget(self.quick_input)
        layout.addLayout(quick_input_layout)

        # Buttons
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self.get_stats)
        button_layout.addWidget(self.apply_button)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_stats(self):
        stats = {}
        for combo, line_edit in self.positive_stats:
            key = combo.currentText()
            value = line_edit.text()
            if value:
                stats[key] = float(value) / 100.0

        curse_key = self.curse_combo.currentText()
        curse_value = self.curse_value.text()
        if curse_value:
            stats[curse_key] = -float(curse_value) / 100.0

        quick_input = self.quick_input.text()
        if quick_input:
            for item in quick_input.split():
                if item in stats:
                    stats[item] = 0.0

        self.accept()
        return stats

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    dialog = RivenQuickInputDialog()
    if dialog.exec() == QDialog.Accepted:
        stats = dialog.get_stats()
        print(stats)
    sys.exit(app.exec())