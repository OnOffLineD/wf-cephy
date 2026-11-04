from typing import Any, Dict

try:
    from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout
except ImportError:
    from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout

from scripts.riven_reroll_reader import format_riven_stats, parse_riven_input

STYLE = (
    "QDialog { background-color: #0d131f; } QLabel { color: #cbd5e1; font-size: 12px; } "
    "QTableWidget { background: #111722; color: #e2e8f0; gridline-color: #1e293b; border: 1px solid #1e293b; } "
    "QHeaderView::section { background: #1e293b; color: #94a3b8; padding: 4px; border: none; } "
    "QLineEdit { background: #161e2e; color: #ffffff; border: 1px solid #24324d; border-radius: 6px; padding: 6px; } "
    "QPushButton { border-radius: 6px; font-weight: bold; padding: 8px; color: #ffffff; background: #1e293b; }"
)


def format_change(before: float, after: float) -> str:
    if before == 0:
        return "-"
    return f"{(after - before) / before * 100:+.1f}%"


class RivenCompareDialog(QDialog):
    def __init__(self, res: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.setWindowTitle("리벤 전후 비교")
        self.setStyleSheet(STYLE)
        self.resize(460, 420)
        layout = QVBoxLayout(self)

        verdict = QLabel(f"{res['verdict']} (지속 DPS 기준)")
        verdict.setStyleSheet("color: #facc15; font-size: 14px; font-weight: bold;")
        layout.addWidget(verdict)

        rows = res["rows"]
        self.table = QTableWidget(len(rows), 4, self)
        self.table.setHorizontalHeaderLabels(["항목", "이전", "새 옵션", "변화"])
        self.table.verticalHeader().setVisible(False)
        for r, (label, before, after) in enumerate(rows):
            for c, text in enumerate((label, f"{before:,.0f}", f"{after:,.0f}", format_change(before, after))):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        layout.addWidget(QLabel(f"이전: {res['old_card'].get('name') or '-'}\n{format_riven_stats(res['old_card']['stats'])}"))
        layout.addWidget(QLabel(f"새 옵션: {res['new_card'].get('name') or '-'}\n{format_riven_stats(res['new_card']['stats'])}"))
        extra = []
        if res.get("unapplied"):
            extra.append("DPS에 반영되지 않는 옵션: " + ", ".join(res["unapplied"]))
        extra.extend(res.get("notes", []))
        if extra:
            note = QLabel("\n".join(extra))
            note.setWordWrap(True)
            layout.addWidget(note)

        close = QPushButton("닫기")
        close.clicked.connect(self.accept)
        layout.addWidget(close)


class RivenRollEditDialog(QDialog):
    """Correct misread options. Values are percents, such as: 피해 251.7 상태이상확률 -53.8"""

    def __init__(self, old_stats: Dict[str, float], new_stats: Dict[str, float], parent=None):
        super().__init__(parent)
        self.setWindowTitle("리벤 옵션 수정")
        self.setStyleSheet(STYLE)
        self.resize(460, 180)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("수치는 % 기준입니다. 예: 치확 150 멀샷 90 화염 85.2 상태이상 -53.8"))
        layout.addWidget(QLabel("이전 옵션"))
        self.old_edit = QLineEdit(format_riven_stats(old_stats), self)
        layout.addWidget(self.old_edit)
        layout.addWidget(QLabel("새 옵션"))
        self.new_edit = QLineEdit(format_riven_stats(new_stats), self)
        layout.addWidget(self.new_edit)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addWidget(self.error_label)
        buttons = QHBoxLayout()
        apply_button = QPushButton("다시 계산")
        apply_button.clicked.connect(self.accept)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def accept(self):
        if not self.old_stats() or not self.new_stats():
            self.error_label.setText("옵션을 읽지 못했습니다. 예시 형식으로 입력해 주세요.")
            return
        super().accept()

    def old_stats(self) -> Dict[str, float]:
        return parse_riven_input(self.old_edit.text())

    def new_stats(self) -> Dict[str, float]:
        return parse_riven_input(self.new_edit.text())
