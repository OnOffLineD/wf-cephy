import os
import sys

import pytest

try:
    from PyQt6.QtWidgets import QApplication, QLabel
except ImportError:
    from PySide6.QtWidgets import QApplication, QLabel

from scripts.build_store import RIVEN_MOD, BuildStore, slot_order
from scripts.damage_breakdown_dialog import DamageBreakdownDialog
from scripts.desktop_companion import OrdisCompanionApp, handle_uncaught_exception
from scripts.screen_mod_analyzer import ScreenModAnalyzer

MODS = [
    {"name": "Serration", "kr_name": "서레이션", "damage": 1.65},
    {"name": "Critical Delay", "kr_name": "크리티컬 딜레이", "crit_chance": 2.0, "fire_rate": -0.2},
]


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def rows(dialog):
    table = dialog.table_widget
    return [[table.item(r, c).text() for c in range(table.columnCount())] for r in range(table.rowCount())]


@pytest.mark.parametrize("riven", [
    {"elemental_damage": 0.9, "toxin": 0.9},
    {"base_damage": 1.65, "multishot": 0.9},
    {"crit_chance": 1.0, "crit_damage": 0.8, "fire_rate": 0.5},
    {"crit_chance": -0.3},
    {"status_chance": 0.5},
])
def test_riven_options_never_break_the_table(qapp, riven):
    dialog = DamageBreakdownDialog(breakdown_text="1. 항목", w_meta={"name": "W"}, mod_objs=MODS, metrics={}, riven_stats=riven)
    assert any(row[0] == "Riven" for row in rows(dialog))


def test_riven_row_shows_percents(qapp):
    dialog = DamageBreakdownDialog(breakdown_text="x", w_meta={"name": "W"}, mod_objs=MODS, riven_stats={"base_damage": 1.65, "multishot": 0.9, "elemental_damage": 0.9, "crit_chance": -0.3})
    riven = next(row for row in rows(dialog) if row[0] == "Riven")
    assert riven[1] == "+165.0%"
    assert riven[2] == "+90.0%"
    assert riven[3] == "+90.0%"
    assert riven[4] == "-30.0%"


def test_totals_include_riven_and_negatives_read_correctly(qapp):
    dialog = DamageBreakdownDialog(breakdown_text="x", w_meta={"name": "W"}, mod_objs=MODS, riven_stats={"base_damage": 1.0})
    table = rows(dialog)
    assert next(r for r in table if r[0] == "크리티컬 딜레이")[6] == "-20.0%"
    assert table[-1][1] == "+265.0%"
    assert table[-1][6] == "-20.0%"


def test_riven_placeholder_is_not_listed_twice(qapp):
    mods = MODS + [{"name": RIVEN_MOD, "kr_name": "리벤 모드"}]
    dialog = DamageBreakdownDialog(breakdown_text="x", w_meta={"name": "W"}, mod_objs=mods, riven_stats={"multishot": 0.9})
    assert [r[0] for r in rows(dialog)].count("리벤 모드") == 0
    assert [r[0] for r in rows(dialog)].count("Riven") == 1


def test_copy_button_copies_selection(qapp):
    dialog = DamageBreakdownDialog(breakdown_text="x", w_meta={"name": "W"}, mod_objs=MODS)
    dialog.table_widget.selectAll()
    dialog.copy_to_clipboard()
    assert "서레이션" in QApplication.clipboard().text()


def test_copy_without_selection_copies_breakdown_text(qapp):
    dialog = DamageBreakdownDialog(breakdown_text="계산 내역", w_meta={"name": "W"}, mod_objs=MODS)
    dialog.copy_to_clipboard()
    assert "계산 내역" in QApplication.clipboard().text()


def test_real_riven_flow_with_element_opens_dialog(qapp, tmp_path):
    analyzer = ScreenModAnalyzer()
    analyzer.build_store = BuildStore(str(tmp_path / "b.json"))
    w_meta = analyzer.indexer.fuzzy_match_weapon("Corinth Prime")
    mods = [dict(analyzer.indexer.mods_index["hunter munitions"], slot_name="R1_C1", slot_index=slot_order("R1_C1")), {"name": RIVEN_MOD, "slot_name": "R1_C4", "slot_index": slot_order("R1_C4")}]
    analyzer._await_riven_values(w_meta, {"total_damage": 3667.4, "multishot": 12.6}, mods, "리벤 모드")
    res = analyzer.resume_pending_riven("치확 100 독 90")
    assert res["riven_stats"]["toxin"] == pytest.approx(0.9)
    dialog = DamageBreakdownDialog(breakdown_text=res["calculation_breakdown"], w_meta=res["w_meta"], mod_objs=res["mod_objs"], metrics=res["metrics"], riven_stats=res["riven_stats"])
    assert any(row[0] == "Riven" for row in rows(dialog))


def test_uncaught_error_is_logged_and_reported_instead_of_closing(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    panel = OrdisCompanionApp()
    log_path = tmp_path / "errors.log"
    before = panel.chat_list_layout.count()
    try:
        raise TypeError("테스트 오류")
    except TypeError:
        handle_uncaught_exception(*sys.exc_info(), panel=panel, log_path=str(log_path))
    qapp.processEvents()
    assert "테스트 오류" in log_path.read_text(encoding="utf-8")
    assert panel.chat_list_layout.count() > before
    bubble = panel.chat_list_layout.itemAt(panel.chat_list_layout.count() - 1).widget()
    assert any("오류" in label.text() for label in bubble.findChildren(QLabel))
    panel.close()
