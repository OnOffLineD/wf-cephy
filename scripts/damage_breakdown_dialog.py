import math
import re
import sys
from typing import Optional

try:
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QTabWidget, QTextBrowser,
        QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QWidget,
        QLabel, QFrame, QGridLayout, QComboBox, QCheckBox, QScrollArea, QSizePolicy
    )
    from PyQt6.QtGui import QColor, QPalette, QPainter, QPen, QBrush, QPolygonF
    from PyQt6.QtCore import Qt, QPoint, QPointF
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QTabWidget, QTextBrowser,
        QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QWidget,
        QLabel, QFrame, QGridLayout, QComboBox, QCheckBox, QScrollArea, QSizePolicy
    )
    from PySide6.QtGui import QColor, QPalette, QPainter, QPen, QBrush, QPolygonF
    from PySide6.QtCore import Qt, QPoint, QPointF

from scripts.frameless_dialog import FramelessDialog

BREAKDOWN_BUTTON_STYLE = """
QPushButton {
    background-color: #161e2e;
    color: #e2e8f0;
    border: 1px solid #24324d;
    border-radius: 6px;
    font-weight: bold;
    padding: 8px 14px;
}
QPushButton:hover {
    background-color: #1e2a40;
    color: #00e5ff;
    border: 1px solid #00d2ff;
}
QPushButton:pressed {
    background-color: #0f1724;
}
"""

# The whole sheet is applied at once so the dialog background rule does not
# wipe out tab/browser/table/button styling (paintEvent draws the opaque card).
BREAKDOWN_DIALOG_STYLE = """
QDialog {
    background-color: #0c1017;
    color: #e2e8f0;
}
QTabWidget::pane {
    background-color: #111722;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #161e2e;
    color: #94a3b8;
    border: 1px solid #24324d;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 6px 14px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1e2a40;
    color: #00e5ff;
    border: 1px solid #00d2ff;
    border-bottom: none;
}
QTextBrowser {
    background-color: #0f172a;
    color: #e2e8f0;
    border: none;
}
QTableWidget {
    background-color: #111722;
    color: #e2e8f0;
    gridline-color: #1e293b;
    border: none;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 4px;
    border: none;
}
QScrollArea { background: transparent; border: none; }
QWidget#dashPage { background-color: #111722; }
QLabel { color: #e2e8f0; }
QFrame#kpiCard { background-color: #111a2b; border: 1px solid #00d2ff; border-radius: 8px; }
QFrame#modCard { background-color: #161e2e; border: 1px solid #b08d2e; border-radius: 6px; }
QFrame#modCard[empty="true"] { border: 1px dashed #24324d; }
QLabel#weaknessBadge { background-color: #2a1520; color: #ff8fa3; border: 1px solid #ff3366; border-radius: 9px; padding: 4px 8px; }
QLabel#weaknessBadge[ok="true"] { background-color: #0f2a22; color: #5eead4; border: 1px solid #14b8a6; }
QComboBox, QCheckBox { color: #e2e8f0; background-color: #161e2e; padding: 4px; }
""" + BREAKDOWN_BUTTON_STYLE

# --- Option 2: combat simulator model -------------------------------------
# Effective level already includes the Steel Path +100; SP adds x2.5 health/armor.
SIM_TARGETS = [
    {"name": "강철의 길 그리니어 헤비거너 Lv 150", "base_level": 8, "level": 150, "armor": 500.0, "health": 700.0, "steel_path": True},
    {"name": "강철의 길 그리니어 헤비거너 Lv 225", "base_level": 8, "level": 225, "armor": 500.0, "health": 700.0, "steel_path": True},
    {"name": "강철의 길 그리니어 봄바드 Lv 150", "base_level": 1, "level": 150, "armor": 500.0, "health": 300.0, "steel_path": True},
    {"name": "강철의 길 코퍼스 테크 Lv 150 (무장갑)", "base_level": 15, "level": 150, "armor": 0.0, "health": 700.0, "steel_path": True},
]
HEADSHOT_MULT = 3.0
VIRAL_MULT = 4.25          # 10 viral stacks: +325% vs health
CORROSIVE_STRIP = 0.8      # 10 corrosive stacks strip 80% armor
ARCANE_DAMAGE_BONUS = 3.6  # full-stack primary arcane: +360% base damage (additive with damage mods)
ARMOR_CAP = 2700.0         # 90% damage reduction cap


def scaled_armor(target, corrosive=False):
    """Ferrite armor: BaseArmor * (1 + (Level - BaseLevel)^1.75 * 0.005)."""
    d = max(0.0, float(target["level"]) - float(target["base_level"]))
    armor = float(target["armor"]) * (1.0 + d ** 1.75 * 0.005)
    if target.get("steel_path"):
        armor *= 2.5
    armor = min(armor, ARMOR_CAP)
    return armor * (1.0 - CORROSIVE_STRIP) if corrosive else armor


def scaled_health(target):
    d = max(0.0, float(target["level"]) - float(target["base_level"]))
    low, high = 1.0 + 0.015 * d ** 2, 1.0 + 24.0 * math.sqrt(5.0) / 5.0 * d ** 0.5
    t = min(1.0, max(0.0, (d - 70.0) / 10.0))  # smoothstep blend between Lv-diff 70 and 80
    s = t * t * (3 - 2 * t)
    hp = float(target["health"]) * (low * (1 - s) + high * s)
    return hp * 2.5 if target.get("steel_path") else hp


def simulate_combat(base_dps, target, headshot=False, viral=False, corrosive=False, arcane=False, damage_bonus=0.0):
    armor = scaled_armor(target, corrosive)
    dr = armor / (armor + 300.0)
    denom = max(0.1, 1.0 + damage_bonus)
    mult = (HEADSHOT_MULT if headshot else 1.0) * (VIRAL_MULT if viral else 1.0)
    mult *= (denom + ARCANE_DAMAGE_BONUS) / denom if arcane else 1.0
    eff = max(0.0, float(base_dps or 0.0)) * mult * (1.0 - dr)
    hp = scaled_health(target)
    return {"armor": armor, "damage_reduction": dr, "health": hp, "multiplier": mult,
            "effective_dps": eff, "ttk": hp / eff if eff > 0 else math.inf}


# --- Option 3: build 2x4 grid, radar and weakness diagnosis ------------------
STAT_KEYS = ("damage", "multishot", "elemental_damage", "crit_chance", "crit_damage", "fire_rate")
# (key, axis label, bucket value treated as the radar's outer ring)
RADAR_AXES = [("damage", "피해", 3.0), ("multishot", "멀티샷", 2.0), ("elemental_damage", "속성", 3.6),
              ("crit_chance", "치확", 3.0), ("crit_damage", "치피", 2.5), ("fire_rate", "연사", 1.0)]
STAT_LABELS = {k: label for k, label, _ in RADAR_AXES}


def mod_stat(mod, key):
    if key == "damage":
        return float(mod.get("damage") or mod.get("base_damage") or 0.0)
    return float(mod.get(key) or 0.0)


def effective_mods(mod_objs, riven_stats):
    """Grid mods with the riven slot marker replaced by the riven's own values."""
    out, riven_slot = [], None
    for m in mod_objs or []:
        if m.get("name") == "Riven Mod" and riven_stats:
            riven_slot = riven_slot or m.get("slot_name")
            continue
        out.append(m)
    if riven_stats:
        riven = dict(riven_stats, name="Riven Mod", kr_name="리벤")
        if riven_slot:
            riven["slot_name"] = riven_slot
        out.append(riven)
    return out


def stat_totals(mods):
    return {k: sum(mod_stat(m, k) for m in mods) for k in STAT_KEYS}


def dps_factor(totals, base_cc, base_cd):
    cc = max(0.0, base_cc * (1.0 + totals["crit_chance"]))
    cd = max(1.0, base_cd * (1.0 + totals["crit_damage"]))
    product = 1.0 + cc * (cd - 1.0)
    for k in ("damage", "multishot", "elemental_damage", "fire_rate"):
        product *= max(0.1, 1.0 + totals[k])
    return product


def mod_dps_share(mod, totals, base_cc, base_cd):
    """Share of the build's DPS lost if this single mod were removed."""
    full = dps_factor(totals, base_cc, base_cd)
    without = {k: totals[k] - mod_stat(mod, k) for k in STAT_KEYS}
    return 1.0 - dps_factor(without, base_cc, base_cd) / full if full > 0 else 0.0


def diagnose_weaknesses(totals, base_cc, is_melee=False):
    badges = []
    if totals["damage"] <= 0:
        badges.append("기본 피해 모드 누락 — 서레이션/혼넷 스트라이크 계열 부재")
    if not is_melee and totals["multishot"] <= 0:
        badges.append("멀티샷 누락 — 분열 사격 계열 부재")
    if totals["elemental_damage"] <= 0:
        badges.append("속성 모드 누락 — 90%/60% 속성 모드 부재")
    if totals["crit_damage"] > 0 and base_cc * (1.0 + totals["crit_chance"]) < 0.25:
        badges.append("시너지 누락 — 치확 25% 미만에서 치피 투자")
    for key, label, cap in RADAR_AXES:
        if totals[key] > cap:
            badges.append(f"합연산 누수 — {label} 버킷 과적재 ({totals[key] * 100:+.0f}%), 다른 배수로 분산 권장")
    return badges


class RadarChart(QWidget):
    """6-axis tendency radar drawn with QPainter.drawPolygon()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = [label for _, label, _ in RADAR_AXES]
        self.values = [0.0] * len(self.labels)
        self.setMinimumSize(200, 200)

    def set_values(self, values):
        self.values = [min(1.0, max(0.0, float(v))) for v in values]
        self.update()

    def polygon(self, center, radius, values):
        angles = [-math.pi / 2 + 2 * math.pi * i / len(values) for i in range(len(values))]
        return QPolygonF([QPointF(center.x() + radius * v * math.cos(a), center.y() + radius * v * math.sin(a))
                          for v, a in zip(values, angles)])

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            center = QPointF(self.width() / 2, self.height() / 2)
            radius = max(10.0, min(self.width(), self.height()) / 2 - 26)
            painter.setPen(QPen(QColor("#24324d"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for ring in (0.25, 0.5, 0.75, 1.0):
                painter.drawPolygon(self.polygon(center, radius, [ring] * len(self.values)))
            outer = self.polygon(center, radius, [1.0] * len(self.values))
            for i in range(outer.count()):
                painter.drawLine(center, outer.at(i))
            painter.setPen(QPen(QColor("#00e5ff"), 2))
            painter.setBrush(QBrush(QColor(0, 229, 255, 70)))
            painter.drawPolygon(self.polygon(center, radius, self.values))
            painter.setPen(QColor("#94a3b8"))
            label_ring = self.polygon(center, radius + 14, [1.0] * len(self.values))
            for i in range(label_ring.count()):
                pt = label_ring.at(i)
                painter.drawText(QPointF(pt.x() - 14, pt.y() + 4), self.labels[i])
        finally:
            painter.end()


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class DamageBreakdownDialog(FramelessDialog):
    def __init__(self, parent=None, breakdown_text='', w_meta=None, mod_objs=None, metrics=None, riven_stats=None):
        super().__init__(parent)
        self.setWindowTitle("Warframe Damage Breakdown")
        self.setModal(True)
        self.breakdown_text = breakdown_text
        self.w_meta = w_meta
        self.mod_objs = mod_objs or []
        self.metrics = metrics or {}
        self.riven_stats = riven_stats or {}
        self.setup_ui()
        self.apply_dark_theme()
        self.resize(860, 680)
        if breakdown_text or w_meta or mod_objs:
            self.set_data(breakdown_text, w_meta, mod_objs, metrics, riven_stats)

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)
        header = self.create_title_bar(title=self.windowTitle(), on_close=self.close)
        layout.addWidget(header)

        # Top: 4 neon KPI summary cards
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(8)
        self.kpi_labels = {}
        for key, title, color in (("expected_dps", "기대 DPS", "#00e5ff"), ("burst_dps", "버스트 DPS", "#ff3366"),
                                  ("peak", "Peak 크리", "#facc15"), ("trough", "Trough 크리", "#a78bfa")):
            card = QFrame()
            card.setObjectName("kpiCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(8, 4, 8, 4)
            card_layout.setSpacing(0)
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; border: none;")
            value_lbl = QLabel("-")
            value_lbl.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold; border: none;")
            for lbl in (title_lbl, value_lbl):
                lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
                card_layout.addWidget(lbl)
            self.kpi_labels[key] = value_lbl
            kpi_row.addWidget(card)
        layout.addLayout(kpi_row)

        # Tab Widget
        tab_widget = self.tab_widget = QTabWidget()
        layout.addWidget(tab_widget, 1)

        tab_widget.addTab(self._scroll_page(self._build_simulator_page()), "전투 시뮬레이터")
        tab_widget.addTab(self._scroll_page(self._build_visual_page()), "비주얼 2x4 · 성향 레이더")

        # Tab 3: calculation steps (HTML) + mod contribution table
        steps_page = QWidget()
        steps_layout = QVBoxLayout(steps_page)
        steps_layout.setContentsMargins(4, 4, 4, 4)
        self.text_browser = QTextBrowser()
        self.text_browser.setHtml(self.generate_html_content())
        steps_layout.addWidget(self.text_browser, 3)
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(8)
        self.table_widget.setHorizontalHeaderLabels(["모드명", "피해", "멀티샷", "속성", "치확", "치피", "연사/공속", "비고"])
        self.populate_table()
        steps_layout.addWidget(self.table_widget, 2)
        tab_widget.addTab(self._scroll_page(steps_page), "상세 수식 (Calculation Steps)")

        # Buttons
        button_layout = QHBoxLayout()
        copy_button = QPushButton("Copy to Clipboard")
        copy_button.setObjectName("breakdownCopyBtn")
        copy_button.setStyleSheet(BREAKDOWN_BUTTON_STYLE)
        copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(copy_button)

        close_button = QPushButton("Close")
        close_button.setObjectName("breakdownCloseBtn")
        close_button.setStyleSheet(BREAKDOWN_BUTTON_STYLE)
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)
        self.copy_button = copy_button
        self.close_button = close_button

        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.refresh_dashboard()

    def _scroll_page(self, page):
        page.setObjectName("dashPage")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(page)
        return scroll

    def _build_simulator_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(10, 10, 10, 10)
        self.target_combo = QComboBox()
        for target in SIM_TARGETS:
            self.target_combo.addItem(target["name"])
        v.addWidget(QLabel("🎯 적 타겟"))
        v.addWidget(self.target_combo)
        toggles = QGridLayout()
        self.headshot_check = QCheckBox(f"헤드샷 x{HEADSHOT_MULT:g}")
        self.viral_check = QCheckBox(f"바이럴 10스택 x{VIRAL_MULT:g}")
        self.corrosive_check = QCheckBox(f"부식 방깎 -{CORROSIVE_STRIP * 100:.0f}%")
        self.arcane_check = QCheckBox(f"아케인 풀스택 +{ARCANE_DAMAGE_BONUS * 100:.0f}%")
        for i, check in enumerate((self.headshot_check, self.viral_check, self.corrosive_check, self.arcane_check)):
            toggles.addWidget(check, i // 2, i % 2)
            check.toggled.connect(self.update_simulation)
        self.target_combo.currentIndexChanged.connect(self.update_simulation)
        v.addLayout(toggles)
        self.sim_dps_label = QLabel()
        self.sim_dps_label.setStyleSheet("color: #00e5ff; font-size: 18px; font-weight: bold;")
        self.sim_ttk_label = QLabel()
        self.sim_ttk_label.setStyleSheet("color: #facc15; font-size: 18px; font-weight: bold;")
        self.sim_detail_label = QLabel()
        self.sim_detail_label.setStyleSheet("color: #94a3b8;")
        self.sim_detail_label.setWordWrap(True)
        for lbl in (self.sim_dps_label, self.sim_ttk_label, self.sim_detail_label):
            v.addWidget(lbl)
        v.addStretch()
        return page

    def _build_visual_page(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(10, 10, 10, 10)
        body = QHBoxLayout()
        self.mod_grid = QGridLayout()
        self.mod_grid.setSpacing(6)
        body.addLayout(self.mod_grid, 3)
        self.radar_chart = RadarChart()
        body.addWidget(self.radar_chart, 2)
        v.addLayout(body)
        v.addWidget(QLabel("🩺 오디스 시너지 진단"))
        self.badge_layout = QVBoxLayout()
        v.addLayout(self.badge_layout)
        v.addStretch()
        return page

    def _crit_base(self):
        w_meta = self.w_meta or {}
        base_cc = float(w_meta.get("crit_chance", 0.1) or 0.0)
        if base_cc > 1.0:
            base_cc /= 100.0
        return base_cc, float(w_meta.get("crit_mult", 1.5) or 1.5)

    def refresh_dashboard(self):
        metrics = self.metrics or {}
        values = {"expected_dps": metrics.get("sustained_dps"), "burst_dps": metrics.get("burst_dps"),
                  "peak": metrics.get("max_crit_hit"), "trough": metrics.get("min_hit")}
        for key, lbl in self.kpi_labels.items():
            val = values[key]
            lbl.setText(f"{float(val):,.0f}" if isinstance(val, (int, float)) else "-")
        self.populate_visuals()
        self.update_simulation()

    def update_simulation(self, *_):
        metrics = self.metrics or {}
        base_dps = metrics.get("sustained_dps") or metrics.get("burst_dps") or 0.0
        mods = effective_mods(self.mod_objs, self.riven_stats)
        target = SIM_TARGETS[max(0, self.target_combo.currentIndex())]
        sim = simulate_combat(base_dps, target, headshot=self.headshot_check.isChecked(),
                              viral=self.viral_check.isChecked(), corrosive=self.corrosive_check.isChecked(),
                              arcane=self.arcane_check.isChecked(), damage_bonus=stat_totals(mods)["damage"])
        self.last_simulation = sim
        self.sim_dps_label.setText(f"실효 DPS: {sim['effective_dps']:,.0f}")
        ttk = sim["ttk"]
        self.sim_ttk_label.setText("처치 소요 시간(TTK): ∞ (피해 불가)" if math.isinf(ttk) else f"처치 소요 시간(TTK): {ttk:,.2f}초")
        self.sim_detail_label.setText(
            f"방어력 {sim['armor']:,.0f} → 피해 감쇄 {sim['damage_reduction'] * 100:.1f}% · "
            f"체력 {sim['health']:,.0f} · 상황 배수 x{sim['multiplier']:.2f} · 기준 DPS {float(base_dps):,.0f}")

    def populate_visuals(self):
        _clear_layout(self.mod_grid)
        _clear_layout(self.badge_layout)
        mods = effective_mods(self.mod_objs, self.riven_stats)
        totals = stat_totals(mods)
        base_cc, base_cd = self._crit_base()
        metrics = self.metrics or {}
        base_dps = float(metrics.get("sustained_dps") or metrics.get("burst_dps") or 0.0)

        cells = [None] * 8
        loose = []
        for m in mods:
            match = re.fullmatch(r"R([12])_C([1-4])", str(m.get("slot_name") or ""))
            idx = (int(match.group(1)) - 1) * 4 + int(match.group(2)) - 1 if match else None
            if idx is not None and cells[idx] is None:
                cells[idx] = m
            elif not m.get("slot_name") and "stance" not in str(m.get("type", "")).lower():
                loose.append(m)  # unslotted grid mods fill the next free cell; stance/exilus stay out
        for m in loose:
            if None in cells:
                cells[cells.index(None)] = m

        self.mod_cards = []
        for idx, m in enumerate(cells):
            card = QFrame()
            card.setObjectName("modCard")
            card.setMinimumSize(80, 56)
            box = QVBoxLayout(card)
            box.setContentsMargins(6, 4, 6, 4)
            if m is None:
                card.setProperty("empty", True)
                box.addWidget(QLabel("빈 슬롯"))
            else:
                share = mod_dps_share(m, totals, base_cc, base_cd)
                name = QLabel(m.get("kr_name") or m.get("name") or "?")
                name.setWordWrap(True)
                name.setStyleSheet("color: #facc15; font-weight: bold; border: none;")
                pct = QLabel(f"{share * 100:+.1f}%")
                pct.setStyleSheet("color: #00e5ff; border: none;")
                box.addWidget(name)
                box.addWidget(pct)
                opts = [f"{STAT_LABELS[k]} {mod_stat(m, k) * 100:+.0f}%" for k in STAT_KEYS if mod_stat(m, k)]
                card.setToolTip("\n".join([m.get("kr_name") or m.get("name") or "?"] + (opts or ["유틸리티 (DPS 옵션 없음)"])
                                          + [f"단독 DPS 기여도: {share * 100:+.1f}% (≈ {base_dps * share:,.0f} DPS)"]))
                self.mod_cards.append(card)
            self.mod_grid.addWidget(card, idx // 4, idx % 4)

        self.radar_values = [min(1.0, max(0.0, totals[k] / cap)) for k, _, cap in RADAR_AXES]
        self.radar_chart.set_values(self.radar_values)

        self.weakness_badges = []
        issues = diagnose_weaknesses(totals, base_cc, is_melee=(self.w_meta or {}).get("category") == "Melee") if mods else []
        for text in issues or ["오디스 진단: 배수 버킷 밸런스 양호" if mods else "오디스 진단: 장착 모드 데이터 없음"]:
            badge = QLabel(("⚠ " if issues else "✔ ") + text)
            badge.setObjectName("weaknessBadge")
            badge.setProperty("ok", not issues)
            badge.setWordWrap(True)
            self.badge_layout.addWidget(badge)
            self.weakness_badges.append(badge)

    def generate_html_content(self):
        text = getattr(self, 'breakdown_text', '') or ''
        if not text:
            return """
            <html>
            <head>
                <style>
                    body { background-color: #0f172a; color: #D4AF37; }
                </style>
            </head>
            <body>
                <h1>No Damage Breakdown Available</h1>
            </body>
            </html>
            """

        lines = text.split('\n')
        html_content = """
        <html>
        <head>
            <style>
                body { background-color: #0f172a; color: #D4AF37; }
                h1 { color: #D4AF37; }
                .section-header { color: #D4AF37; font-weight: bold; }
                .step { background-color: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; padding: 5px; border-radius: 5px; }
                .bullet-item { background-color: #1e293b; color: #D4AF37; padding: 5px; border-radius: 5px; }
                .total-highlight { background-color: #D4AF37; color: #0f172a; padding: 5px; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>Damage Calculation Breakdown</h1>
        """

        for line in lines:
            line = line.strip()
            if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.')):
                html_content += f'<p class="section-header">{line}</p>'
            elif line.startswith(('①', '②', '③', '④', '⑤', '⑥', '⑦')):
                html_content += f'<p class="step">{line}</p>'
            elif line.startswith('•'):
                html_content += f'<p class="bullet-item">{line}</p>'
            elif line.startswith('Total:'):
                html_content += f'<p class="total-highlight">{line}</p>'
            else:
                html_content += f'<p>{line}</p>'

        html_content += """
        </body>
        </html>
        """
        return html_content

    def populate_table(self):
        self.table_widget.setRowCount(0)  # Clear existing rows
        self.table_widget.setColumnCount(8)
        self.table_widget.setHorizontalHeaderLabels(["모드명", "피해", "멀티샷", "속성", "치확", "치피", "연사/공속", "비고"])

        if not self.mod_objs and not self.riven_stats:
            return

        def percent(value):
            return f"{value*100:+.1f}%" if value != 0 else "-"

        data = []
        total_damage = 0
        total_multishot = 0
        total_elemental_damage = 0
        total_crit_chance = 0
        total_crit_damage = 0
        total_fire_rate = 0

        for m in self.mod_objs or []:
            # The riven's values get their own row below; this is only its slot marker.
            if self.riven_stats and m.get('name') == 'Riven Mod':
                continue
            mod_name = m.get('kr_name') or m.get('name')
            damage = float(m.get('damage') or 0.0)
            multishot = float(m.get('multishot') or 0.0)
            elemental_damage = float(m.get('elemental_damage') or 0.0)
            crit_chance = float(m.get('crit_chance') or 0.0)
            crit_damage = float(m.get('crit_damage') or 0.0)
            fire_rate = float(m.get('fire_rate') or 0.0)

            total_damage += damage
            total_multishot += multishot
            total_elemental_damage += elemental_damage
            total_crit_chance += crit_chance
            total_crit_damage += crit_damage
            total_fire_rate += fire_rate

            is_zero = not any([damage, multishot, elemental_damage, crit_chance, crit_damage, fire_rate])
            note = "[스탠스]" if "stance" in str(m.get("type", "")).lower() else ("[유틸리티]" if is_zero else "-")

            row_data = [
                mod_name,
                percent(damage),
                percent(multishot),
                percent(elemental_damage),
                percent(crit_chance),
                percent(crit_damage),
                percent(fire_rate),
                note
            ]
            data.append(row_data)

        if self.riven_stats:
            riven = self.riven_stats
            riven_damage = riven.get('damage', 0.0) or riven.get('base_damage', 0.0)
            total_damage += riven_damage
            total_multishot += riven.get('multishot', 0.0)
            total_elemental_damage += riven.get('elemental_damage', 0.0)
            total_crit_chance += riven.get('crit_chance', 0.0)
            total_crit_damage += riven.get('crit_damage', 0.0)
            total_fire_rate += riven.get('fire_rate', 0.0)
            data.append([
                "Riven",
                percent(riven_damage),
                percent(riven.get('multishot', 0.0)),
                percent(riven.get('elemental_damage', 0.0)),
                percent(riven.get('crit_chance', 0.0)),
                percent(riven.get('crit_damage', 0.0)),
                percent(riven.get('fire_rate', 0.0)),
                "고유 롤 옵션 합산"
            ])

        summary_row = [
            "🎯 총합 적용치",
            f"{total_damage*100:+.1f}%",
            f"{total_multishot*100:+.1f}%",
            f"{total_elemental_damage*100:+.1f}%",
            f"{total_crit_chance*100:+.1f}%",
            f"{total_crit_damage*100:+.1f}%",
            f"{total_fire_rate*100:+.1f}%",
            "연산 대입값 (Total Sum)"
        ]
        data.append(summary_row)

        self.table_widget.setRowCount(len(data))
        for row, row_data in enumerate(data):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if value != "0" and value != "-":
                    item.setBackground(QColor("#1e293b"))
                self.table_widget.setItem(row, col, item)

    def copy_to_clipboard(self):
        lines = []
        for selection in self.table_widget.selectedRanges():
            for row in range(selection.topRow(), selection.bottomRow() + 1):
                items = (self.table_widget.item(row, col) for col in range(selection.leftColumn(), selection.rightColumn() + 1))
                lines.append("\t".join(item.text() for item in items if item))
        # With nothing selected, the calculation steps are what the button can usefully copy.
        QApplication.clipboard().setText("\n".join(lines) if lines else (self.breakdown_text or ""))

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f172a"))
        self.setPalette(palette)
        self.setStyleSheet(BREAKDOWN_DIALOG_STYLE)

    def set_data(self, breakdown_text='', w_meta=None, mod_objs=None, metrics=None, riven_stats=None):
        self.breakdown_text = breakdown_text
        self.w_meta = w_meta
        self.mod_objs = mod_objs or []
        self.metrics = metrics or {}
        self.riven_stats = riven_stats or {}

        if w_meta:
            self.setWindowTitle(f"Warframe Damage Breakdown - {w_meta.get('name', 'Unknown Weapon')}")

        self.text_browser.setHtml(self.generate_html_content())
        self.populate_table()
        self.refresh_dashboard()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = DamageBreakdownDialog()
    dialog.show()
    sys.exit(app.exec())
