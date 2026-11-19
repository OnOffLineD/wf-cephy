import math
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
    compute_numeric_test, build_pipeline_steps,
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
    # Post-U36 Jade Shadows enemy armor DR uses the square-root curve up to the 2,700 cap (90% DR).
    assert sim["damage_reduction"] == pytest.approx(0.9 * math.sqrt(expected / 2700.0))
    half_cap = simulate_combat(1000.0, {"level": 1, "base_level": 1, "armor": 1350.0, "health": 100.0})
    expected_half_dr = 0.9 * math.sqrt(1350.0 / 2700.0)
    assert half_cap["damage_reduction"] == pytest.approx(expected_half_dr)
    assert half_cap["effective_dps"] == pytest.approx(1000.0 * (1.0 - expected_half_dr))
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
    # 42% -> 174% crit chance: orange crits raise the peak tier (2.0 -> 3.0x) and the trough tier (1.0 -> 2.0x).
    assert test["peak"] == pytest.approx(500.0 * 3.0 / 2.0) and test["trough"] == pytest.approx(100.0 * 2.0)
    proc = compute_numeric_test({"crit_chance": 0.2, "procChance": 0.3}, MELEE_MODS, MELEE_METRICS, combo_mult=12)
    assert proc["base_status_chance"] == pytest.approx(0.3)
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


def test_spinbox_arrow_clicks_step_under_global_theme(qapp, monkeypatch):
    try:
        from PyQt6.QtTest import QTest
        from PyQt6.QtWidgets import QStyle, QStyleOptionSpinBox
    except ImportError:
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox
    from scripts.desktop_companion import OrdisCompanionApp
    monkeypatch.setattr(OrdisCompanionApp, "refresh_world_events", lambda self: None)
    panel, old_sheet = OrdisCompanionApp(), qapp.styleSheet()
    try:
        import qdarktheme
        qapp.setStyleSheet(qdarktheme.load_stylesheet())
    except Exception:
        pass  # theme package optional; the companion app's own widgets are still alive
    dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=MELEE_META, mod_objs=MELEE_MODS, metrics=MELEE_METRICS)
    try:
        dlg.tab_widget.setCurrentIndex(2)
        dlg.show()
        qapp.processEvents()
        for spin, covered in ((s, c) for s in (dlg.gladiator_spin, dlg.status_types_spin) for c in (False, True)):
            spin.setValue(2)
            if covered:  # a theme stretching the inner QLineEdit over the arrow buttons
                spin.lineEdit().setGeometry(spin.rect())
            for sub, delta in ((QStyle.SubControl.SC_SpinBoxUp, 1), (QStyle.SubControl.SC_SpinBoxDown, -1)):
                opt = QStyleOptionSpinBox()
                spin.initStyleOption(opt)
                center = spin.style().subControlRect(QStyle.ComplexControl.CC_SpinBox, opt, sub, spin).center()
                target = spin.childAt(center) or spin
                before = spin.value()
                QTest.mouseClick(target, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, target.mapFrom(spin, center))
                assert spin.value() == before + delta, (spin, sub)
    finally:
        dlg.close()
        panel.close()
        qapp.setStyleSheet(old_sheet)


def test_numeric_test_row_fits_default_dialog_width(qapp):
    dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=MELEE_META, mod_objs=MELEE_MODS, metrics=MELEE_METRICS)
    try:
        dlg.tab_widget.setCurrentIndex(2)
        dlg.show()
        qapp.processEvents()
        assert dlg.width() == 860
        for spin in (dlg.gladiator_spin, dlg.status_types_spin):
            assert 80 <= spin.width() <= 115, spin.width()
        viewport = dlg.tab_widget.currentWidget().viewport()
        for widget in (dlg.on_kill_check, dlg.reset_test_btn):
            assert widget.isVisible()
            for host in (dlg, viewport):  # inside the 860px window and the visible (unscrolled) tab area
                left = widget.mapTo(host, widget.rect().topLeft()).x()
                assert left >= 0 and left + widget.width() <= host.width(), (widget, host, left, widget.width())
    finally:
        dlg.close()


def test_gladiator_spin_alone_activates_test_and_card_renders_on_top(qapp):
    dlg = DamageBreakdownDialog(breakdown_text="1. 무기 코덱스 기본 스탯\n  - 기본 피해: 18.0\n  - 치명타 확률: 20.0%\n"
                                "  - 연사력: 1.0\n\n2. 모드 합산\n  - 서레이션: 피해 +165.0%\n  ↳ 🎯 [총합 적용치]: 피해 +165.0%\n\n"
                                "3. 단계별 공식\n  ① 근접 타격 판정 = 1,000.0;",
                                w_meta=MELEE_META, mod_objs=MELEE_MODS + [GLADIATOR_VICE], metrics=MELEE_METRICS)
    assert dlg.test_result["is_test_active"] is False and "조건부" not in dlg.text_browser.toPlainText()
    base_tip = dlg.test_summary_label.text()
    dlg.gladiator_spin.setValue(3)
    assert dlg.test_result["is_test_active"] is True and dlg.test_summary_label.text() != base_tip
    plain = dlg.text_browser.toPlainText()
    assert "조건부 수치 테스트" in plain and plain.index("조건부 수치 테스트") < plain.index("1.")
    assert "12x 기준 예상 치확" in plain and "기본 피해" in plain and "1,000.0" in plain
    page = dlg.generate_html_content()
    assert "<table" in page and "#00d2ff" in page and "#4ade80" in page
    dlg.reset_numeric_test()
    assert dlg.test_result["is_test_active"] is False and dlg.gladiator_spin.value() == 1


def test_breakdown_text_shows_conditional_mod_effects():
    from scripts.screen_mod_analyzer import ScreenModAnalyzer
    text = ScreenModAnalyzer.format_calculation_breakdown(None, MELEE_META, MELEE_MODS + [GLADIATOR_VICE], {})
    assert "[유틸리티/효과]" not in text and "상태이상 확률: 16.0%" in text
    for needle in ("블러드 러쉬", "위핑 운즈", "컨디션 오버로드", "글래디에이터 세트", "처치 시 치명타 피해 +30%"):
        assert needle in text


def _pipeline_card_texts(dlg):
    out = {}
    for card in dlg.pipeline_cards:
        key = card.property("stepKey")
        labels = {lbl.objectName(): lbl.text() for lbl in card.findChildren(QLabel)}
        out[key] = labels
    return out


def test_pipeline_flow_block_ranged_vs_melee_and_status_fallback(qapp):
    ranged_meta = {"name": "Braton Prime", "total_damage": 100.0, "crit_chance": 0.2,
                   "crit_mult": 2.0, "fire_rate": 5.0, "base_multishot": 1.0}
    ranged_mods = [
        {"name": "Serration", "kr_name": "서레이션", "damage": 1.65},
        {"name": "Split Chamber", "kr_name": "스플릿 체임버", "multishot": 0.9},
        {"name": "Stormbringer", "kr_name": "스톰브링어", "elemental_damage": 0.9},
        {"name": "Point Strike", "kr_name": "포인트 스트라이크", "crit_chance": 1.5},
    ]
    # Metrics intentionally omit status_dps / direct_burst_dps / status_breakdown to verify safe fallback.
    ranged_dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=ranged_meta, mod_objs=ranged_mods,
                                       metrics={"sustained_dps": 5000.0, "burst_dps": 7553.0})
    assert "원거리" in ranged_dlg.pipeline_title_label.text()
    cards = _pipeline_card_texts(ranged_dlg)
    assert [c["pipelineStage"] for c in cards.values()] == [
        "기본 피해", "피해 모드", "속성/팩션", "치명타 기댓값", "멀티샷·연사", "상태이상 DoT", "기대 / 버스트 DPS"
    ]
    assert cards["damage"]["pipelineBadge"] == "×2.65" and cards["damage"]["pipelineValue"] == "265"
    assert cards["elemental"]["pipelineBadge"] == "×1.90"
    assert cards["status"]["pipelineBadge"] == "+0" and "DoT 없음" in cards["status"]["pipelineSub"]

    melee_dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=MELEE_META,
                                      mod_objs=MELEE_MODS + [GLADIATOR_VICE], metrics=MELEE_METRICS)
    assert "근접" in melee_dlg.pipeline_title_label.text()
    melee_cards = _pipeline_card_texts(melee_dlg)
    melee_titles = [c["pipelineStage"] for c in melee_cards.values()]
    assert melee_titles == [
        "기본 피해", "피해·CO 모드", "속성", "연속기·치명타 기댓값", "공속", "상태이상 DoT", "기대 / 버스트 DPS"
    ]
    assert not any("멀티샷" in t for t in melee_titles)


def test_pipeline_flow_displays_status_dps_and_breakdown(qapp):
    w_meta = {"name": "Braton Prime", "total_damage": 46.0, "crit_chance": 0.12, "crit_mult": 2.0,
              "fire_rate": 9.58, "base_multishot": 1.0, "status_chance": 0.26}
    metrics = {
        "sustained_dps": 10200.0, "burst_dps": 14250.0, "direct_burst_dps": 12500.0,
        "status_dps": 1750.0, "status_breakdown": {"slash": 1200.0, "heat": 550.0},
        "max_crit_hit": 2200.0, "min_hit": 300.0,
    }
    dlg = DamageBreakdownDialog(breakdown_text="", w_meta=w_meta, mod_objs=MODS, metrics=metrics, riven_stats=RIVEN)
    cards = _pipeline_card_texts(dlg)
    assert cards["status"]["pipelineBadge"] == "+1,750"
    assert cards["status"]["pipelineValue"] == "14,250"
    assert "베기 1,200" in cards["status"]["pipelineSub"] and "화염 550" in cards["status"]["pipelineSub"]
    assert cards["result"]["pipelineValue"] == "기대 10,200"
    assert cards["result"]["pipelineSubValue"] == "버스트 14,250"
    assert "12,500" in dlg.pipeline_split_label.text() and "1,750" in dlg.pipeline_split_label.text()

    html_doc = dlg.generate_html_content()
    assert "배수 파이프라인 요약" in html_doc and "상태이상 DoT 파이프라인" in html_doc
    assert "베기(출혈)" in html_doc and "화염" in html_doc
    for color in ("#0a1019", "#142336", "#00e5ff", "#ffd700", "#ff4d6d", "#b388ff"):
        assert color in html_doc


def test_pipeline_flow_updates_live_on_numeric_test_controls(qapp):
    melee_with_status = {
        "sustained_dps": 1400.0, "burst_dps": 1620.0, "direct_burst_dps": 1200.0,
        "status_dps": 420.0, "status_breakdown": {"slash": 300.0, "heat": 120.0},
        "max_crit_hit": 500.0, "min_hit": 100.0,
    }
    dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=MELEE_META,
                                mod_objs=MELEE_MODS + [GLADIATOR_VICE], metrics=melee_with_status)
    try:
        dlg.tab_widget.setCurrentIndex(2)
        dlg.show()
        qapp.processEvents()
        base_cards = _pipeline_card_texts(dlg)
        assert base_cards["damage"]["pipelineBadge"] == "×1.00"
        assert base_cards["status"]["pipelineBadge"] == "+420"

        dlg.status_types_spin.setValue(4)
        co_cards = _pipeline_card_texts(dlg)
        assert co_cards["damage"]["pipelineBadge"] == "×4.20"
        assert float(co_cards["status"]["pipelineBadge"].lstrip("+").replace(",", "")) > 420.0

        dlg.combo_mult_combo.setCurrentIndex(11)  # 12x -> Blood Rush + Weeping Wounds + Gladiator
        combo_cards = _pipeline_card_texts(dlg)
        assert combo_cards["crit"]["pipelineBadge"] != base_cards["crit"]["pipelineBadge"]
        assert float(combo_cards["status"]["pipelineBadge"].lstrip("+").replace(",", "")) > float(
            co_cards["status"]["pipelineBadge"].lstrip("+").replace(",", ""))
        assert combo_cards["result"]["pipelineSubValue"] == f"버스트 {dlg.kpi_labels['burst_dps'].text()}"

        dlg.on_kill_check.setChecked(True)
        kill_cards = _pipeline_card_texts(dlg)
        assert kill_cards["crit"]["pipelineBadge"] != combo_cards["crit"]["pipelineBadge"]

        # Verify pipeline cards stay inside the 860px viewport without triggering scrollbars.
        scroll = dlg.tab_widget.currentWidget()
        assert not scroll.verticalScrollBar().isVisible()
        assert not scroll.horizontalScrollBar().isVisible()
        for card in dlg.pipeline_cards:
            left = card.mapTo(scroll.viewport(), card.rect().topLeft()).x()
            assert left >= 0 and left + card.width() <= scroll.viewport().width()

        dlg.reset_numeric_test()
        reset_cards = _pipeline_card_texts(dlg)
        assert reset_cards["damage"]["pipelineBadge"] == "×1.00"
        assert reset_cards["status"]["pipelineBadge"] == "+420"
    finally:
        dlg.close()

    # Sniper multiplier should update ranged Step 5 badge & sublabel.
    ranged_dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=W_META, mod_objs=MODS, metrics=METRICS, riven_stats=RIVEN)
    before_step5 = _pipeline_card_texts(ranged_dlg)["speed_ms"]["pipelineBadge"]
    ranged_dlg.sniper_mult_combo.setCurrentIndex(2)  # 2.0x
    after_step5 = _pipeline_card_texts(ranged_dlg)["speed_ms"]
    assert after_step5["pipelineBadge"] != before_step5 and "저격×2.0" in after_step5["pipelineSub"]
    assert build_pipeline_steps(None, None, None)["status_dps"] == 0.0


def test_pipeline_preserves_valence_and_innate_traits_when_test_active():
    from scripts.warframe_damage_engine import WarframeDamageEngine
    from scripts.wf_data_indexer import WFDataIndexer

    idx = WFDataIndexer()
    eng = WarframeDamageEngine()

    kh = idx.fuzzy_match_weapon("Kuva Hek")
    kh_mods = [dict(idx.mods_index[n]) for n in ("incendiary coat", "galvanized hell", "point blank")]
    kh_metrics = eng.compute_metrics(kh, left_stats={"valence_heat": 0.6}, mod_objs=kh_mods)
    kh_off = {s["key"]: s for s in build_pipeline_steps(kh, kh_mods, kh_metrics)["steps"]}
    kh_test = compute_numeric_test(kh, kh_mods, kh_metrics, status_types=3, on_kill_active=True)
    kh_on = {s["key"]: s for s in build_pipeline_steps(kh, kh_mods, kh_metrics, test_result=kh_test)["steps"]}
    assert kh_off["elemental"]["badge"] == "×3.04" and kh_on["elemental"]["badge"] == "×3.04"
    assert "14.70발" in kh_off["speed_ms"]["sub_text"]
    assert kh_on["speed_ms"]["value"] == pytest.approx(kh_test["metrics"]["direct_burst_dps"], rel=1e-4)
    assert kh_on["status"]["value"] == pytest.approx(kh_test["metrics"]["burst_dps"], rel=1e-4)

    cm = idx.fuzzy_match_weapon("Coda Motovore")
    cm_mods = [dict(idx.mods_index[n]) for n in ("buzz kill", "pressure point")]
    cm_metrics = eng.compute_metrics(cm, mod_objs=cm_mods)
    cm_off = {s["key"]: s for s in build_pipeline_steps(cm, cm_mods, cm_metrics)["steps"]}
    cm_test = compute_numeric_test(cm, cm_mods, cm_metrics, combo_mult=12, status_types=3)
    cm_on = {s["key"]: s for s in build_pipeline_steps(cm, cm_mods, cm_metrics, test_result=cm_test)["steps"]}
    assert cm_off["elemental"]["badge"] == "×3.40" and cm_on["elemental"]["badge"] == "×3.40"
    assert cm_on["speed_ms"]["value"] == pytest.approx(cm_test["metrics"]["direct_burst_dps"], rel=1e-4)

    # Extra elemental bonus during active test stacks on top of the implied baseline (e.g. Melee Exposure).
    cm_exp_test = dict(cm_test, extra=dict(cm_test["extra"], elemental_damage=2.4))
    cm_exp = {s["key"]: s for s in build_pipeline_steps(cm, cm_mods, cm_metrics, test_result=cm_exp_test)["steps"]}
    assert cm_exp["elemental"]["badge"] == "×5.80"


def test_numeric_test_controls_visibility_branches_by_weapon_type(qapp):
    sniper_meta = {"name": "Rubico Prime", "category": "Primary", "type": "Sniper", "crit_chance": 0.38, "crit_mult": 3.0}
    shotgun_meta = {"name": "Kuva Hek", "category": "Primary", "type": "Shotgun", "crit_chance": 0.23, "crit_mult": 2.1}

    dlg = DamageBreakdownDialog(breakdown_text="1. 기본", w_meta=MELEE_META, mod_objs=MELEE_MODS + [GLADIATOR_VICE], metrics=MELEE_METRICS)
    try:
        dlg.tab_widget.setCurrentIndex(2)
        dlg.show()
        qapp.processEvents()

        # 1. Melee: combo & gladiator visible, sniper hidden
        for w in (dlg.combo_label, dlg.combo_mult_combo, dlg.gladiator_label, dlg.gladiator_spin,
                  dlg.status_types_label, dlg.status_types_spin, dlg.on_kill_check, dlg.reset_test_btn):
            assert not w.isHidden() and w.isVisible()
        for w in (dlg.sniper_label, dlg.sniper_mult_combo):
            assert w.isHidden() and not w.isVisible()

        dlg.combo_mult_combo.setCurrentIndex(11)
        assert "연속기" in dlg.test_summary_label.text() and "저격" not in dlg.test_summary_label.text()
        assert "저격" not in dlg.text_browser.toPlainText()

        # 2. Switch via set_data() -> Sniper: sniper visible, combo & gladiator hidden & reset
        dlg.set_data("1. 기본", w_meta=sniper_meta, mod_objs=MODS, metrics=METRICS, riven_stats=RIVEN)
        qapp.processEvents()
        assert dlg.combo_mult_combo.currentIndex() == 0 and dlg.gladiator_spin.value() == 0
        for w in (dlg.sniper_label, dlg.sniper_mult_combo, dlg.status_types_label,
                  dlg.status_types_spin, dlg.on_kill_check, dlg.reset_test_btn):
            assert not w.isHidden() and w.isVisible()
        for w in (dlg.combo_label, dlg.combo_mult_combo, dlg.gladiator_label, dlg.gladiator_spin):
            assert w.isHidden() and not w.isVisible()

        dlg.sniper_mult_combo.setCurrentIndex(2)  # 2.0x
        summary = dlg.test_summary_label.text()
        plain = dlg.text_browser.toPlainText()
        assert "저격 2.0x" in summary and "연속기" not in summary and "글래디에이터" not in summary
        assert "저격총 연속 적중 배수 x2.0" in plain and "블러드 러쉬" not in plain and "글래디에이터" not in plain

        # 3. Switch via set_data() -> Non-sniper ranged (Shotgun): combo, gladiator, sniper all hidden & reset
        dlg.set_data("1. 기본", w_meta=shotgun_meta, mod_objs=MODS, metrics=METRICS)
        qapp.processEvents()
        assert dlg.sniper_mult_combo.currentIndex() == 0 and dlg.combo_mult_combo.currentIndex() == 0
        for w in (dlg.combo_label, dlg.combo_mult_combo, dlg.gladiator_label, dlg.gladiator_spin,
                  dlg.sniper_label, dlg.sniper_mult_combo):
            assert w.isHidden() and not w.isVisible()
        for w in (dlg.status_types_label, dlg.status_types_spin, dlg.on_kill_check, dlg.reset_test_btn):
            assert not w.isHidden() and w.isVisible()

        dlg.on_kill_check.setChecked(True)
        summary = dlg.test_summary_label.text()
        plain = dlg.text_browser.toPlainText()
        assert "연속기" not in summary and "저격" not in summary
        assert "연속기" not in plain and "저격" not in plain and "글래디에이터" not in plain and "블러드 러쉬" not in plain
    finally:
        dlg.close()


# --- Phase B Slice 3: UI Parity Regression Tests ---

def test_simulate_combat_slash_true_damage_heat_strip_faction_and_melee_arcane():
    # Post-U36: Steel Path does not multiply armor by 2.5x; Heat -50% stacks multiplicatively with Corrosive -80%.
    low_armor_sp = {"level": 1, "base_level": 1, "armor": 500.0, "health": 1000.0, "steel_path": True, "faction": "grineer"}
    assert scaled_armor(low_armor_sp) == pytest.approx(500.0)
    assert scaled_armor(low_armor_sp, corrosive=True, heat=True) == pytest.approx(500.0 * 0.2 * 0.5)

    # Slash Bleed True Damage ignores 90% armor DR while direct & non-slash DoT are mitigated by (1 - DR).
    target_cap = SIM_TARGETS[0]  # SP Lv150 Grineer Heavy Gunner -> 2700 armor (90% DR)
    metrics = {
        "direct_sustained_dps": 10000.0,
        "slash_status_sustained_dps": 4000.0,
        "non_slash_status_sustained_dps": 2000.0,
        "status_breakdown": {"slash": 4000.0, "heat": 2000.0},
        "elements": {"types": {"corrosive": 100.0}},  # +50% vs Grineer
        "faction_by_name": {"grineer": 0.55},
        "generic_faction": 0.0,
        "active_faction_bonus": 0.0,
        "headshot_ratio": 5.5,
    }
    sim = simulate_combat(16000.0, target_cap, metrics=metrics)
    assert sim["damage_reduction"] == pytest.approx(0.9)
    # Direct: 10000 * 1.5 (Corrosive vs Grineer) * 1.55 (Bane) * 0.1 (DR) = 2325
    # Non-slash Heat DoT: 2000 * 1.0 * 1.55^2 * 0.1 (DR) = 480.5
    # Slash Bleed True Damage: 4000 * 1.55^2 (NO armor DR, NO faction weakness table) = 9610
    assert sim["slash_effective_dps"] == pytest.approx(4000.0 * (1.55 ** 2))
    assert sim["direct_effective_dps"] == pytest.approx(10000.0 * 1.5 * 1.55 * 0.1)
    assert sim["non_slash_effective_dps"] == pytest.approx(2000.0 * (1.55 ** 2) * 0.1)
    assert sim["effective_dps"] == pytest.approx(
        sim["direct_effective_dps"] + sim["non_slash_effective_dps"] + sim["slash_effective_dps"]
    )

    # Headshot uses engine headshot_ratio (5.5x) on direct hits ONLY — Slash/Heat DoT ticks stay uninflated.
    sim_hs = simulate_combat(16000.0, target_cap, headshot=True, metrics=metrics)
    assert sim_hs["headshot_mult"] == pytest.approx(5.5)
    assert sim_hs["direct_effective_dps"] == pytest.approx(sim["direct_effective_dps"] * 5.5)
    assert sim_hs["non_slash_effective_dps"] == pytest.approx(sim["non_slash_effective_dps"])
    assert sim_hs["slash_effective_dps"] == pytest.approx(sim["slash_effective_dps"])
    assert sim_hs["effective_dps"] == pytest.approx(
        sim["direct_effective_dps"] * 5.5 + sim["non_slash_effective_dps"] + sim["slash_effective_dps"]
    )
    assert sim_hs["multiplier"] == pytest.approx(
        sim_hs["effective_dps"] / (10000.0 * 0.1 + 2000.0 * 0.1 + 4000.0)
    )

    # Melee does not hardcode Primary Merciless +360%.
    sim_melee = simulate_combat(1000.0, low_armor_sp, arcane=True, is_melee=True)
    sim_melee_no_arc = simulate_combat(1000.0, low_armor_sp, arcane=False, is_melee=True)
    assert sim_melee["effective_dps"] == pytest.approx(sim_melee_no_arc["effective_dps"])


def test_primary_acuity_headshot_multishot_lock_share_and_weakness_suppression(qapp):
    from scripts.warframe_damage_engine import WarframeDamageEngine
    from scripts.wf_data_indexer import WFDataIndexer

    idx = WFDataIndexer()
    eng = WarframeDamageEngine()
    w = idx.fuzzy_match_weapon("Braton Prime")
    mods = [dict(idx.mods_index["serration"]), dict(idx.mods_index["galvanized chamber"]), dict(idx.mods_index["primary acuity"])]
    metrics = eng.compute_metrics(w, mod_objs=mods)

    # 1. compute_numeric_test with on_kill=True must NOT let Galvanized Chamber inflate DPS when Primary Acuity locks multishot.
    test_on = compute_numeric_test(w, mods, metrics, on_kill_active=True)
    assert test_on["lock_multishot"] is True
    assert test_on["ms_ratio"] == pytest.approx(1.0)
    assert test_on["expected_dps"] == pytest.approx(metrics["sustained_dps"])

    # 2. simulate_combat headshot toggle reflects Primary Acuity's massive headshot_ratio (>> 3.0x) on direct hits only.
    assert metrics["headshot_ratio"] > 8.0
    sim_body = simulate_combat(metrics["sustained_dps"], SIM_TARGETS[3], headshot=False, metrics=metrics)
    sim_head = simulate_combat(metrics["sustained_dps"], SIM_TARGETS[3], headshot=True, metrics=metrics)
    assert sim_head["direct_effective_dps"] == pytest.approx(sim_body["direct_effective_dps"] * metrics["headshot_ratio"])
    assert sim_head["slash_effective_dps"] == pytest.approx(sim_body["slash_effective_dps"])
    assert sim_head["non_slash_effective_dps"] == pytest.approx(sim_body["non_slash_effective_dps"])
    assert sim_head["effective_dps"] == pytest.approx(
        sim_body["direct_effective_dps"] * metrics["headshot_ratio"]
        + sim_body["non_slash_effective_dps"]
        + sim_body["slash_effective_dps"]
    )

    # 3. Tab 2: Primary Acuity gets positive mod_dps_share and suppresses "멀티샷 누락".
    totals = stat_totals(mods)
    assert mod_dps_share(mods[2], totals, w["crit_chance"], w["crit_mult"]) > 0.3
    dlg = DamageBreakdownDialog(w_meta=w, mod_objs=mods, metrics=metrics)
    try:
        badge_texts = [b.text() for b in dlg.weakness_badges]
        assert not any("멀티샷 누락" in t for t in badge_texts)
    finally:
        dlg.close()


def test_galvanized_elementalist_does_not_inflate_hunter_munitions_slash():
    from scripts.warframe_damage_engine import WarframeDamageEngine
    from scripts.wf_data_indexer import WFDataIndexer

    idx = WFDataIndexer()
    eng = WarframeDamageEngine()
    # Zero natural slash weapon so 100% of slash DoT comes from Hunter Munitions.
    w = {"name": "Heat Gun", "category": "Primary", "total_damage": 100.0, "crit_chance": 0.5, "crit_mult": 3.0,
         "fire_rate": 5.0, "status_chance": 0.2, "base_multishot": 1.0, "attacks": [{"name": "Shot", "damage": {"heat": 100.0}}]}
    mods = [
        {"name": "Hunter Munitions", "kr_name": "헌터 뮤니션즈", "hunter_munitions": True},
        {"name": "Galvanized Elementalist", "kr_name": "갈바나이즈드 엘리멘탈리스트", "status_damage": 0.8,
         "on_kill": [{"stat": "status", "value": 0.3, "stacks": 4}]},
    ]
    metrics = eng.compute_metrics(w, mod_objs=mods)
    assert metrics["hm_slash_dps"] > 0
    assert metrics["status_breakdown"]["slash"] == pytest.approx(metrics["hm_slash_dps"])

    test_on = compute_numeric_test(w, mods, metrics, on_kill_active=True)
    # Heat DoT scales with sc_ratio (2.2x), while HM Slash stays 1.0x!
    assert test_on["metrics"]["status_breakdown"]["slash"] == pytest.approx(metrics["status_breakdown"]["slash"])
    assert test_on["metrics"]["status_breakdown"]["heat"] == pytest.approx(metrics["status_breakdown"]["heat"] * test_on["sc_ratio"])


def test_sacrificial_pipeline_does_not_hallucinate_elemental_and_melee_share_not_linear_status(qapp):
    from scripts.damage_breakdown_dialog import dps_factor
    from scripts.warframe_damage_engine import WarframeDamageEngine
    from scripts.wf_data_indexer import WFDataIndexer

    idx = WFDataIndexer()
    eng = WarframeDamageEngine()
    w = idx.fuzzy_match_weapon("Stropha")
    mods = [dict(idx.mods_index["sacrificial pressure"]), dict(idx.mods_index["sacrificial steel"])]
    metrics = eng.compute_metrics(w, mod_objs=mods)

    steps = {s["key"]: s for s in build_pipeline_steps(w, mods, metrics)["steps"]}
    assert steps["damage"]["badge"] == "×2.38"  # 1 + 1.375 set-boosted Sacrificial Pressure
    assert steps["elemental"]["badge"] == "×1.00"  # No hallucinated +13% elemental card!

    dlg = DamageBreakdownDialog(w_meta=w, mod_objs=mods, metrics=metrics)
    try:
        rows_map = table_rows(dlg)
        assert rows_map["🎯 총합 적용치"][1] == "+137.5%"
    finally:
        dlg.close()

    # Melee dps_factor must NOT multiply direct DPS linearly by (1 + status = 5.4x).
    f_no_status = dps_factor({"damage": 0.0, "status": 0.0, "elemental_damage": 0.0, "crit_chance": 0.0, "crit_damage": 0.0, "fire_rate": 0.0}, 0.2, 2.0, is_melee=True)
    f_weeping = dps_factor({"damage": 0.0, "status": 4.4, "elemental_damage": 0.0, "crit_chance": 0.0, "crit_damage": 0.0, "fire_rate": 0.0}, 0.2, 2.0, is_melee=True)
    assert f_weeping > f_no_status
    assert f_weeping < f_no_status * 2.0  # bounded DoT share, not 5.4x direct!

    # Bane, Hunter Munitions, and IPS mods all get positive share instead of +0.0%.
    special_mods = [
        {"name": "Primed Bane of Grineer", "faction": {"grineer": 0.55}},
        {"name": "Hunter Munitions", "hunter_munitions": True},
        {"name": "Buzz Kill", "slash": 1.2},
    ]
    sp_totals = stat_totals(special_mods)
    for m in special_mods:
        assert mod_dps_share(m, sp_totals, 0.3, 2.5) > 0, m["name"]
