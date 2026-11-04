from typing import Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QComboBox, QCompleter, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout
except ImportError:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QComboBox, QCompleter, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from scripts.build_store import GRID_SLOTS, RIVEN_MOD

EMPTY = "(비어 있음)"
RIVEN_LABEL = "리벤 모드"
STYLE = (
    "QDialog { background-color: #0d131f; } QLabel { color: #94a3b8; font-size: 12px; } "
    "QComboBox { background: #161e2e; color: #ffffff; border: 1px solid #24324d; border-radius: 6px; padding: 4px; } "
    "QPushButton { border-radius: 6px; font-weight: bold; padding: 8px; color: #ffffff; background: #1e293b; }"
)
INVALID_STYLE = "QComboBox { border: 1px solid #ef4444; }"


class BuildEditDialog(QDialog):
    """Fix misrecognized mods slot by slot. Position matters: it decides elemental combination."""

    def __init__(self, slots: Dict[str, str], mod_choices: List[Tuple[str, str]], arcane: Optional[str] = None, arcane_choices: Optional[List[Tuple[str, str]]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("장착 모드 수정")
        self.setStyleSheet(STYLE)
        self._names = {display: name for display, name in mod_choices}
        self._names[RIVEN_LABEL] = RIVEN_MOD
        self._displays = {name: display for display, name in self._names.items()}
        self._arcane_names = {display: name for display, name in (arcane_choices or [])}
        self._arcane_displays = {name: display for display, name in self._arcane_names.items()}
        self.combos: Dict[str, QComboBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("슬롯 위치도 속성 합성에 영향을 줍니다. 이름을 입력하면 검색됩니다."))

        top = QGridLayout()
        top.addWidget(QLabel("스탠스/오라"), 0, 0)
        top.addWidget(self._add_combo("stance", slots), 0, 1)
        top.addWidget(QLabel("엑실러스"), 1, 0)
        top.addWidget(self._add_combo("exilus", slots), 1, 1)
        self.arcane_combo = self._make_combo(list(self._arcane_names), self._arcane_displays.get(arcane, arcane or ""))
        top.addWidget(QLabel("아케인"), 2, 0)
        top.addWidget(self.arcane_combo, 2, 1)
        layout.addLayout(top)

        grid = QGridLayout()
        for index, slot in enumerate(GRID_SLOTS):
            grid.addWidget(self._add_combo(slot, slots), index // 4, index % 4)
        layout.addLayout(grid)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #ef4444;")
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        save = QPushButton("적용")
        save.clicked.connect(self.accept)
        cancel = QPushButton("취소")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

    def _make_combo(self, items: List[str], current: str) -> QComboBox:
        combo = QComboBox(self)
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        combo.setMinimumWidth(170)
        combo.addItems([EMPTY] + items)
        completer = QCompleter(combo.model(), combo)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        combo.setCompleter(completer)
        combo.setCurrentText(current or EMPTY)
        return combo

    def _add_combo(self, slot: str, slots: Dict[str, str]) -> QComboBox:
        name = slots.get(slot, "")
        combo = self._make_combo(sorted(self._names), self._displays.get(name, name))
        self.combos[slot] = combo
        return combo

    def invalid_slots(self) -> List[str]:
        invalid = []
        for slot, combo in self.combos.items():
            combo.setStyleSheet("")
            text = combo.currentText().strip()
            if text and text != EMPTY and text not in self._names:
                combo.setStyleSheet(INVALID_STYLE)
                invalid.append(slot)
        return invalid

    def accept(self):
        if self.invalid_slots():
            self.error_label.setText("목록에 없는 모드 이름입니다. 빨간 칸을 확인해 주세요.")
            return
        super().accept()

    def get_edits(self) -> Dict[str, str]:
        edits = {}
        for slot, combo in self.combos.items():
            text = combo.currentText().strip()
            edits[slot] = "" if not text or text == EMPTY else self._names[text]
        arcane = self.arcane_combo.currentText().strip()
        edits["arcane"] = "" if not arcane or arcane == EMPTY else self._arcane_names.get(arcane, arcane)
        return edits
