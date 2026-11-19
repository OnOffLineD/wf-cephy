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


def test_dialog_paints_opaque_dark_card_with_cyan_border(qapp):
    try:
        from PyQt6.QtGui import QImage, QColor, QPaintEvent
        from PyQt6.QtCore import Qt
    except ImportError:
        from PySide6.QtGui import QImage, QColor, QPaintEvent
        from PySide6.QtCore import Qt
    dialog = DamageBreakdownDialog(breakdown_text="x", w_meta={"name": "W"}, mod_objs=MODS)
    assert dialog.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    dialog.resize(400, 300)
    dialog.paintEvent(QPaintEvent(dialog.rect()))  # direct call must not raise outside a paint cycle
    image = QImage(dialog.size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    dialog.render(image)
    # Bottom margin strip below the buttons (inside the border) is only covered by paintEvent.
    bottom = image.pixelColor(200, 300 - 5)
    assert bottom.alpha() == 255
    assert bottom.name() == "#0c1017"
    border = image.pixelColor(200, 299)
    assert border.alpha() > 0
    assert border.blue() > border.red()
    # Rounded corner stays transparent (outside the 14px radius).
    assert image.pixelColor(0, 0).alpha() == 0
    assert "QTabBar::tab" in dialog.styleSheet() and "QPushButton" in dialog.styleSheet()
    assert "QPushButton" in dialog.copy_button.styleSheet()
    assert dialog.layout().contentsMargins().left() == 14


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


def test_arcane_choices_and_incarnon_description_exact_matching():
    analyzer = ScreenModAnalyzer()

    # Non-prefixed arcanes appear for their proper weapon categories & sub-types.
    sec_arcanes = {en for _, en in analyzer.arcane_choices(analyzer.indexer.fuzzy_match_weapon("Kuva Nukor"))}
    assert "Cascadia Flare" in sec_arcanes
    assert "Secondary Merciless" in sec_arcanes
    assert "Longbow Sharpshot" not in sec_arcanes

    bow_arcanes = {en for _, en in analyzer.arcane_choices(analyzer.indexer.fuzzy_match_weapon("Nataruk"))}
    assert "Longbow Sharpshot" in bow_arcanes
    assert "Primary Merciless" in bow_arcanes
    assert "Shotgun Vendetta" not in bow_arcanes

    shotgun_arcanes = {en for _, en in analyzer.arcane_choices(analyzer.indexer.fuzzy_match_weapon("Corinth Prime"))}
    assert "Shotgun Vendetta" in shotgun_arcanes
    assert "Longbow Sharpshot" not in shotgun_arcanes

    # Incarnon description uses exact family matching (no lex -> Aklex or furis -> Afuris false positives).
    lex_desc = analyzer.get_incarnon_trait_description("Lex Prime")
    aklex_desc = analyzer.get_incarnon_trait_description("Aklex Prime")
    assert lex_desc != aklex_desc
    assert "인카논 고유 변신 화력" in aklex_desc


def test_format_calculation_breakdown_lhs_equals_rhs_and_elements_faction_parity():
    from scripts.warframe_damage_engine import WarframeDamageEngine
    analyzer = ScreenModAnalyzer()
    eng = WarframeDamageEngine()

    # 1. CC > 100%: prints Tier-2 crit multiplier (not raw final_cd), no "비크리 1타(최저점)" on guaranteed crit, no "+-".
    reaper = analyzer.indexer.fuzzy_match_weapon("Reaper Prime")
    reaper_mods = [dict(analyzer.indexer.mods_index["sacrificial steel"]), dict(analyzer.indexer.mods_index["organ shatter"])]
    r_metrics = eng.compute_metrics(reaper, mod_objs=reaper_mods)
    r_text = analyzer.format_calculation_breakdown(reaper, reaper_mods, r_metrics)
    assert r_metrics["final_cc"] > 1.0
    expected_tier2 = 1.0 + 2 * (r_metrics["final_cd"] - 1.0)
    assert f"× {expected_tier2:.2f}배 = {r_metrics['max_crit_hit']:,.1f}" in r_text
    assert "비크리 1타(최저점)" not in r_text
    assert "확정 치명타 최저점" in r_text

    # 2. Negative fire rate has no "+-" double sign; bleed tick prints modded_base (not elemental per_pellet) and LHS == RHS.
    braton = analyzer.indexer.fuzzy_match_weapon("Braton Prime")
    b_mods = [
        dict(analyzer.indexer.mods_index["serration"]),
        dict(analyzer.indexer.mods_index["critical delay"]),
        dict(analyzer.indexer.mods_index["vital sense"]),
        dict(analyzer.indexer.mods_index["stormbringer"]),
        dict(analyzer.indexer.mods_index["hunter munitions"]),
    ]
    b_metrics = eng.compute_metrics(braton, mod_objs=b_mods)
    b_text = analyzer.format_calculation_breakdown(braton, b_mods, b_metrics)
    assert "+-" not in b_text
    assert "연사력 -20.0%" in b_text
    modded_base = braton["total_damage"] * (1.0 + 1.65)
    assert f"모딩 기본피해({modded_base:,.1f})" in b_text
    assert f"틱당 약 {b_metrics['hunter_munitions']['bleed_tick']:,.1f}" in b_text

    # 3. _format_elements computes unfactored_direct * fm + faction_status_dps[f] without losing Bane^2 on DoT.
    bane_mods = b_mods + [dict(analyzer.indexer.mods_index["primed bane of grineer"])]
    bane_metrics = eng.compute_metrics(braton, mod_objs=bane_mods, target_faction="grineer")
    el_lines = "\n".join(analyzer._format_elements(bane_metrics))
    fm_g = bane_metrics["elements"]["faction_multipliers"]["grineer"]
    unfactored_direct = bane_metrics["direct_burst_dps"] / (1.0 + bane_metrics["active_faction_bonus"])
    expected_grineer = unfactored_direct * fm_g + bane_metrics["faction_status_dps"]["grineer"]
    assert f"`{expected_grineer:,.0f}`" in el_lines
