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
    simulate_combat, scaled_armor, mod_dps_share, stat_totals, diagnose_weaknesses,
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


def test_set_data_rebuilds_without_duplicates(dialog):
    dialog.set_data("x", W_META, MODS[:1], {"sustained_dps": 500.0}, None)
    assert len(dialog.mod_cards) == 1 and dialog.mod_grid.count() == 8
    assert dialog.kpi_labels["expected_dps"].text() == "500" and dialog.kpi_labels["peak"].text() == "-"
    page = dialog.tab_widget.widget(1).widget()
    assert len(page.findChildren(QLabel, "weaknessBadge")) == len(dialog.weakness_badges) > 0
