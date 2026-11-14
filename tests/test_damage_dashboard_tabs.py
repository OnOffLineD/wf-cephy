import pytest

try:
    from PyQt6.QtWidgets import QApplication, QTextBrowser, QTableWidget, QLabel
    from PyQt6.QtGui import QImage
    from PyQt6.QtCore import Qt
except ImportError:
    from PySide6.QtWidgets import QApplication, QTextBrowser, QTableWidget, QLabel
    from PySide6.QtGui import QImage
    from PySide6.QtCore import Qt

from scripts.damage_breakdown_dialog import (
    DamageBreakdownDialog, SIM_TARGETS, HEADSHOT_MULT, VIRAL_MULT, ARMOR_CAP,
    simulate_combat, scaled_armor, mod_dps_share, stat_totals, diagnose_weaknesses, compute_numeric_test,
)

W_META = {"name": "Test Rifle", "crit_chance": 0.2, "crit_mult": 2.0}
MODS = [{"name": "Serration", "kr_name": "서레이션", "damage": 1.65, "slot_name": "R1_C1"},
        {"name": "Point Strike", "kr_name": "포인트 스트라이크", "crit_chance": 1.5, "slot_name": "R2_C3"},
        {"name": "Riven Mod", "slot_name": "R1_C4"}]
RIVEN = {"crit_damage": 1.2, "fire_rate": 0.5}
METRICS = {"sustained_dps": 12000.0, "burst_dps": 15000.0, "max_crit_hit": 4200.0, "min_hit": 900.0}


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def dialog(qapp):
    return DamageBreakdownDialog(breakdown_text="1. 기본 피해\nTotal: 100", w_meta=W_META,
                                 mod_objs=MODS, metrics=METRICS, riven_stats=RIVEN)


def test_three_tabs_render_and_kpis(dialog):
    tabs = dialog.tab_widget
    titles = [tabs.tabText(i) for i in range(tabs.count())]
    assert len(titles) == 3 and "전투 시뮬레이터" in titles[0]
    assert "2x4" in titles[1] and "레이더" in titles[1] and "상세 수식" in titles[2]
    steps = tabs.widget(2).widget()  # each tab page sits in a QScrollArea
    assert steps.findChild(QTextBrowser) is dialog.text_browser and steps.findChild(QTableWidget) is dialog.table_widget
    assert "기본 피해" in dialog.text_browser.toPlainText()
    for i in range(3):
        tabs.setCurrentIndex(i)
        image = QImage(dialog.size(), QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        dialog.render(image)  # every tab (incl. radar paintEvent) renders without raising
    texts = {k: lbl.text() for k, lbl in dialog.kpi_labels.items()}
    assert texts == {"expected_dps": "12,000", "burst_dps": "15,000", "peak": "4,200", "trough": "900"}


def test_headshot_viral_and_corrosive_toggles_update_live(dialog):
    base, base_text = dict(dialog.last_simulation), dialog.sim_dps_label.text()
    dialog.headshot_check.setChecked(True)
    assert dialog.last_simulation["effective_dps"] == pytest.approx(base["effective_dps"] * HEADSHOT_MULT)
    assert dialog.last_simulation["ttk"] == pytest.approx(base["ttk"] / HEADSHOT_MULT)
    assert dialog.sim_dps_label.text() != base_text
    dialog.viral_check.setChecked(True)
    both = dialog.last_simulation
    assert both["effective_dps"] == pytest.approx(base["effective_dps"] * HEADSHOT_MULT * VIRAL_MULT)
    assert f"{both['ttk']:,.2f}초" in dialog.sim_ttk_label.text()
    assert base["armor"] == pytest.approx(ARMOR_CAP)  # SP Lv150 heavy gunner hits the 90% cap
    dialog.corrosive_check.setChecked(True)
    assert dialog.last_simulation["armor"] == pytest.approx(ARMOR_CAP * 0.2)
    dialog.target_combo.setCurrentIndex(1)
    assert dialog.last_simulation["health"] > both["health"]


def test_armor_formula_arcane_and_zero_dps(dialog):
    target = {"level": 20, "base_level": 10, "armor": 100.0, "health": 100.0}
    expected = 100.0 * (1 + 10 ** 1.75 * 0.005)
    assert scaled_armor(target) == pytest.approx(expected)
    sim = simulate_combat(1000.0, target)
    assert sim["damage_reduction"] == pytest.approx(expected / (expected + 300.0))
    assert sim["effective_dps"] == pytest.approx(1000.0 * (1 - sim["damage_reduction"]))
    arcane = simulate_combat(1000.0, target, arcane=True, damage_bonus=1.65)
    assert arcane["effective_dps"] == pytest.approx(sim["effective_dps"] * (2.65 + 3.6) / 2.65)
    assert simulate_combat(1000.0, next(t for t in SIM_TARGETS if t["armor"] == 0))["damage_reduction"] == 0
    empty = DamageBreakdownDialog()
    assert empty.last_simulation["ttk"] == float("inf") and "∞" in empty.sim_ttk_label.text()


def test_mod_grid_cards_radar_and_weakness_badges(dialog):
    assert dialog.mod_grid.count() == 8 and len(dialog.mod_cards) == 3
    assert dialog.mod_grid.itemAtPosition(0, 0).widget() in dialog.mod_cards
    riven_card = dialog.mod_grid.itemAtPosition(0, 3).widget()  # riven values land in the marker's slot
    assert riven_card.toolTip().startswith("리벤") and "치피 +120%" in riven_card.toolTip()
    assert all("단독 DPS 기여도" in c.toolTip() for c in dialog.mod_cards)
    texts = [b.text() for b in dialog.weakness_badges]
    assert any("멀티샷 누락" in t for t in texts) and any("속성 모드 누락" in t for t in texts)
    vals = dialog.radar_values
    assert len(vals) == 6 and all(0.0 <= v <= 1.0 for v in vals)
    assert vals[0] == pytest.approx(1.65 / 3.0) and vals[1] == 0.0
    assert dialog.radar_chart.values == vals


def test_mod_share_and_diagnosis_rules(qapp):
    mods = [{"damage": 1.65}, {"crit_chance": 2.0}]
    assert mod_dps_share(mods[0], stat_totals(mods), 0.2, 2.0) == pytest.approx(1 - 1 / 2.65)
    full = {"damage": 4.0, "multishot": 1.0, "elemental_damage": 1.0, "crit_chance": 1.0, "crit_damage": 1.0, "fire_rate": 0.0}
    assert diagnose_weaknesses(full, 0.3) == ["합연산 누수 — 피해 버킷 과적재 (+400%), 다른 배수로 분산 권장"]
    assert any("시너지 누락" in b for b in diagnose_weaknesses(dict(full, damage=1.0, crit_chance=0.0), 0.05))


MELEE_MODS = [
    {"name": "Condition Overload", "kr_name": "컨디션 오버로드", "damage": 0.0, "status_type_damage": 0.8, "slot_name": "R1_C1"},
    {"name": "Blood Rush", "kr_name": "블러드 러쉬", "crit_chance": 0.0, "combo_crit": 0.4, "slot_name": "R1_C2"},
    {"name": "Galvanized Steel", "kr_name": "갈바나이즈드 스틸", "crit_chance": 1.1,
     "on_kill": [{"stat": "crit_damage", "value": 0.3, "stacks": 4}], "slot_name": "R1_C3"},
    {"name": "Galvanized Elementalist", "kr_name": "갈바나이즈드 엘리멘탈리스트", "status_damage": 0.8,
     "on_kill": [{"stat": "status", "value": 0.3, "stacks": 4}], "slot_name": "R1_C4"},
    {"name": "Weeping Wounds", "kr_name": "위핑 운즈", "combo_status": 0.4, "slot_name": "R2_C1"},
]


def test_melee_radar_drops_multishot_and_counts_conditional_mods(qapp):
    melee = DamageBreakdownDialog(w_meta={"name": "Prisma Skana", "category": "Melee", "crit_chance": 0.2, "crit_mult": 2.0},
                                  mod_objs=MELEE_MODS, metrics={"sustained_dps": 1000.0})
    labels = melee.radar_chart.labels
    assert "멀티샷" not in labels and "상태이상" in labels and "공속" in labels
    totals = stat_totals(MELEE_MODS)
    for mod in MELEE_MODS:
        assert mod_dps_share(mod, totals, 0.2, 2.0, is_melee=True) > 0, mod["name"]
    assert all("+0.0%" not in c.findChildren(QLabel)[1].text() for c in melee.mod_cards)
    texts = [b.text() for b in melee.weakness_badges]
    assert not any("기본 피해 모드 누락" in t or "멀티샷" in t for t in texts)
    assert any("프레셔 포인트/컨디션 오버로드" in b for b in diagnose_weaknesses(stat_totals(MELEE_MODS[1:]), 0.2, is_melee=True))
    lower = DamageBreakdownDialog(w_meta={"name": "Skana", "category": "melee"}, mod_objs=MELEE_MODS[:1])
    assert "멀티샷" not in lower.radar_chart.labels


def test_set_data_rebuilds_without_duplicates(dialog):
    dialog.set_data("x", W_META, MODS[:1], {"sustained_dps": 500.0}, None)
    assert len(dialog.mod_cards) == 1 and dialog.mod_grid.count() == 8
    assert dialog.kpi_labels["expected_dps"].text() == "500" and dialog.kpi_labels["peak"].text() == "-"
    page = dialog.tab_widget.widget(1).widget()
    assert len(page.findChildren(QLabel, "weaknessBadge")) == len(dialog.weakness_badges) > 0


MELEE_META = {"name": "Prisma Skana", "category": "Melee", "crit_chance": 0.2, "crit_mult": 2.0, "status_chance": 0.16}
GLADIATOR_VICE = {"name": "Gladiator Vice", "kr_name": "글래디에이터 바이스", "fire_rate": 0.3,
                  "modSet": "/Lotus/Upgrades/Mods/Sets/Gladiator/GladiatorSetMod", "combo_crit": 0.10, "_set_applied": True}
MELEE_METRICS = {"sustained_dps": 1000.0, "burst_dps": 1200.0, "max_crit_hit": 500.0, "min_hit": 100.0}


def test_compute_numeric_test_combo_gladiator_and_defaults():
    default = compute_numeric_test(MELEE_META, MELEE_MODS, MELEE_METRICS)
    assert default["is_test_active"] is False and default["metrics"] == MELEE_METRICS and default["breakdown_text"] == ""
    test = compute_numeric_test(MELEE_META, MELEE_MODS + [GLADIATOR_VICE], MELEE_METRICS, combo_mult=12, gladiator_stacks=2)
    assert test["ww_sc_bonus"] == pytest.approx(0.4 * 11)
    assert test["final_status_chance"] == pytest.approx(0.16 * (1 + 4.4))
    # Gladiator Vice's set-applied combo_crit is not counted again as Blood Rush.
    assert test["br_cc_bonus"] == pytest.approx(0.4 * 11) and test["glad_cc_bonus"] == pytest.approx(0.10 * 2 * 11)
    assert test["final_crit_chance"] == pytest.approx(0.2 * (1 + 1.1 + 4.4 + 2.2))
    assert test["expected_dps"] > 1000.0
    auto = compute_numeric_test(MELEE_META, MELEE_MODS + [GLADIATOR_VICE], MELEE_METRICS, combo_mult=12)
    assert auto["gladiator_stacks"] == 1 and auto["glad_cc_bonus"] == pytest.approx(1.1)
    sniper = compute_numeric_test(W_META, MODS, METRICS, RIVEN, sniper_mult=2.0)
    for key, src in (("expected_dps", "sustained_dps"), ("burst_dps", "burst_dps"), ("peak", "max_crit_hit"), ("trough", "min_hit")):
        assert sniper[key] == pytest.approx(METRICS[src] * 2.0)
    co = compute_numeric_test(MELEE_META, MELEE_MODS, MELEE_METRICS, status_types=4)
    assert co["co_damage_bonus"] == pytest.approx(3.2) and co["expected_dps"] == pytest.approx(1000.0 * 4.2)
    galv = compute_numeric_test(MELEE_META, MELEE_MODS, MELEE_METRICS, on_kill_active=True)
    assert galv["on_kill_sc"] == pytest.approx(1.2) and galv["final_crit_mult"] == pytest.approx(2.0 * 2.2)


def table_rows(dlg):
    t = dlg.table_widget
    return {t.item(r, 0).text(): [t.item(r, c).text() for c in range(t.columnCount())] for r in range(t.rowCount())}


def test_numeric_test_controls_update_kpis_table_and_simulator(qapp):
    dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=MELEE_META, mod_objs=MELEE_MODS + [GLADIATOR_VICE], metrics=MELEE_METRICS)
    assert dlg.gladiator_spin.value() == 1 and dlg.kpi_labels["expected_dps"].text() == "1,000"
    rows = table_rows(dlg)
    assert "블러드 러쉬" in rows["블러드 러쉬"][7] and "위핑 운즈" in rows["위핑 운즈"][7]
    assert "컨디션 오버로드" in rows["컨디션 오버로드"][7] and "미적용" in rows["갈바나이즈드 스틸"][7]
    base_sim, base_tip = dict(dlg.last_simulation), dlg.test_summary_label.text()
    dlg.combo_mult_combo.setCurrentIndex(11)  # 12x
    rows = table_rows(dlg)
    assert rows["블러드 러쉬"][4] == "+440.0%" and rows["글래디에이터 세트"][4] == "+110.0%"
    assert dlg.test_result["final_status_chance"] == pytest.approx(0.16 * (1 + 4.4))
    assert "위핑 운즈 +440%" in dlg.text_browser.toPlainText() and dlg.test_summary_label.text() != base_tip
    assert dlg.last_simulation["effective_dps"] > base_sim["effective_dps"]
    dlg.reset_numeric_test()
    dlg.status_types_spin.setValue(4)
    rows = table_rows(dlg)
    assert rows["컨디션 오버로드"][1] == "+320.0%" and rows["🎯 총합 적용치"][1] == "+320.0%"
    assert dlg.last_simulation["damage_bonus"] == pytest.approx(3.2)
    assert dlg.last_simulation["effective_dps"] == pytest.approx(base_sim["effective_dps"] * 4.2)
    dlg.on_kill_check.setChecked(True)
    assert "풀스택 적용" in table_rows(dlg)["갈바나이즈드 스틸"][7]
    assert table_rows(dlg)["갈바나이즈드 스틸"][5] == "+120.0%"
    dlg.reset_numeric_test()
    assert dlg.test_result["is_test_active"] is False and dlg.kpi_labels["expected_dps"].text() == "1,000"
    assert dlg.last_simulation["effective_dps"] == pytest.approx(base_sim["effective_dps"])


def test_sniper_multiplier_doubles_kpis_and_simulator(dialog):
    base = dict(dialog.last_simulation)
    dialog.sniper_mult_combo.setCurrentIndex(2)  # 2.0x
    texts = {k: lbl.text() for k, lbl in dialog.kpi_labels.items()}
    assert texts == {"expected_dps": "24,000", "burst_dps": "30,000", "peak": "8,400", "trough": "1,800"}
    assert dialog.last_simulation["effective_dps"] == pytest.approx(base["effective_dps"] * 2.0)
    assert "저격총 연속 적중 배수 x2.0" in dialog.text_browser.toPlainText()
    dialog.reset_test_btn.click()
    assert dialog.kpi_labels["expected_dps"].text() == "12,000"


def test_breakdown_text_shows_conditional_mod_effects():
    from scripts.screen_mod_analyzer import ScreenModAnalyzer
    text = ScreenModAnalyzer.format_calculation_breakdown(None, MELEE_META, MELEE_MODS + [GLADIATOR_VICE], {})
    assert "[유틸리티/효과]" not in text and "상태이상 확률: 16.0%" in text
    for needle in ("블러드 러쉬", "위핑 운즈", "컨디션 오버로드", "글래디에이터 세트", "처치 시 치명타 피해 +30%"):
        assert needle in text
