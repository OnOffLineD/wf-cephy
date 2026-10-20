import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QCheckBox, QHBoxLayout, QLineEdit, QGridLayout, QScrollArea, QFrame
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QIcon, QFont
from scripts.world_state_tracker import WorldStateTracker

class WorldStatusPanel(QWidget):
    refresh_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("World Status Panel")
        self.setFixedSize(400, 600)
        self.setStyleSheet("background-color: #1c1c1c; color: #ffffff;")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.create_cards()

    def create_cards(self):
        self.cetus_card = self.create_card("Cetus Plains", "Day/Night and Countdown")
        self.void_trader_card = self.create_card("Void Trader", "Baro KiTeer Location and ETA")
        self.duviri_card = self.create_card("Duviri", "Spiral")
        self.sortie_card = self.create_card("Sortie", "Sortie and Archon Hunt")
        self.incarnon_card = self.create_card("Incarnon", "Rotation")

        self.layout.addWidget(self.cetus_card)
        self.layout.addWidget(self.void_trader_card)
        self.layout.addWidget(self.duviri_card)
        self.layout.addWidget(self.sortie_card)
        self.layout.addWidget(self.incarnon_card)

    def create_card(self, title, content):
        card = QFrame()
        card.setStyleSheet("background-color: #2c2c2c; border-radius: 10px; padding: 10px;")
        card_layout = QVBoxLayout()
        card.setLayout(card_layout)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        content_label = QLabel(content)
        content_label.setStyleSheet("font-size: 14px;")

        card_layout.addWidget(title_label)
        card_layout.addWidget(content_label)

        return card

    def update_events(self, ev_dict):
        # Update the content of each card based on the event dictionary
        pass

class TodoPanel(QWidget):
    task_added = pyqtSignal(str)
    task_toggled = pyqtSignal(str, bool)
    task_deleted = pyqtSignal(str)
    auto_detect_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Todo Panel")
        self.setFixedSize(400, 600)
        self.setStyleSheet("background-color: #1c1c1c; color: #ffffff;")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.create_ui()

    def create_ui(self):
        self.task_list = QScrollArea()
        self.task_list.setStyleSheet("background-color: #2c2c2c; border: none;")
        self.task_list.setWidgetResizable(True)
        self.task_list.setWidget(QWidget())

        self.task_layout = QVBoxLayout()
        self.task_list.widget().setLayout(self.task_layout)

        self.input_box = QLineEdit()
        self.input_box.setStyleSheet("background-color: #3c3c3c; color: #ffffff; border: none; padding: 10px;")
        self.input_box.setPlaceholderText("Add new task...")

        self.add_button = QPushButton("Add")
        self.add_button.setStyleSheet("background-color: #3c3c3c; color: #ffffff; border: none; padding: 10px;")
        self.add_button.clicked.connect(self.add_task)

        self.auto_toggle = QCheckBox("Auto Todo Toggle")
        self.auto_toggle.setStyleSheet("background-color: #2c2c2c; color: #ffffff; border: none;")
        self.auto_toggle.stateChanged.connect(self.auto_detect_changed.emit)

        self.layout.addWidget(self.task_list)
        self.layout.addWidget(self.input_box)
        self.layout.addWidget(self.add_button)
        self.layout.addWidget(self.auto_toggle)

    def add_task(self):
        task_text = self.input_box.text().strip()
        if task_text:
            self.task_added.emit(task_text)
            self.input_box.clear()

    def refresh_tasks(self, items):
        self.task_layout = QVBoxLayout()
        self.task_list.widget().setLayout(self.task_layout)

        for item in items:
            task_widget = QWidget()
            task_layout = QHBoxLayout()
            task_widget.setLayout(task_layout)

            task_checkbox = QCheckBox(item["text"])
            task_checkbox.setStyleSheet("background-color: #2c2c2c; color: #ffffff; border: none;")
            task_checkbox.setChecked(item["done"])
            task_checkbox.stateChanged.connect(lambda state, id=item["id"]: self.task_toggled.emit(id, state == Qt.CheckState.Checked))

            delete_button = QPushButton("Delete")
            delete_button.setStyleSheet("background-color: #3c3c3c; color: #ffffff; border: none; padding: 10px;")
            delete_button.clicked.connect(lambda _, id=item["id"]: self.task_deleted.emit(id))

            task_layout.addWidget(task_checkbox)
            task_layout.addWidget(delete_button)

            self.task_layout.addWidget(task_widget)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    world_status_panel = WorldStatusPanel()
    todo_panel = TodoPanel()

    world_status_panel.show()
    todo_panel.show()

    sys.exit(app.exec())