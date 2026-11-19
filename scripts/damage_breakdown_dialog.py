import html
import math
import re
import sys

try:
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QTabWidget, QTextBrowser,
        QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QWidget,
        QLabel, QFrame, QGridLayout, QComboBox, QCheckBox, QScrollArea, QSizePolicy, QSpinBox,
        QStyle, QStyleOptionSpinBox
    )
    from PyQt6.QtGui import QColor, QPalette, QPainter, QPen, QBrush, QPolygonF
    from PyQt6.QtCore import Qt, QPointF, QEvent
except ImportError:
    from PySide6.QtWidgets import (
        QApplication, QDialog, QVBoxLayout, QTabWidget, QTextBrowser,
        QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QWidget,
        QLabel, QFrame, QGridLayout, QComboBox, QCheckBox, QScrollArea, QSizePolicy, QSpinBox,
        QStyle, QStyleOptionSpinBox
    )
    from PySide6.QtGui import QColor, QPalette, QPainter, QPen, QBrush, QPolygonF
    from PySide6.QtCore import Qt, QPointF, QEvent

from scripts.damage_formulas import (
    FACTION_MODIFIERS,
    average_crit_mult,
    enemy_armor_dr,
    hm_crit_avg,
    shooting_proportion,
)
from scripts.frameless_dialog import FramelessDialog
from scripts.warframe_damage_engine import WarframeDamageEngine

_ENGINE_HELPER = WarframeDamageEngine()

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
    background-color: #0a1019;
    color: #e2e8f0;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QTableWidget {
    background-color: #0a1019;
    color: #e2e8f0;
    gridline-color: #1e293b;
    border: 1px solid #1e293b;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #142336;
    color: #00e5ff;
    font-weight: bold;
    padding: 5px 4px;
    border: none;
    border-bottom: 1px solid #00e5ff;
}
QScrollArea { background: transparent; border: none; }
QWidget#dashPage { background-color: #111722; }
QLabel { color: #e2e8f0; }
QFrame#kpiCard { background-color: #111a2b; border: 1px solid #00d2ff; border-radius: 8px; }
QFrame#pipelineFrame { background-color: #0a1019; border: 1px solid #1e3a5f; border-radius: 8px; }
QFrame#pipelineCard { background-color: #142336; border: 1px solid #243b55; border-radius: 6px; }
QFrame#modCard { background-color: #161e2e; border: 1px solid #b08d2e; border-radius: 6px; }
QFrame#modCard[empty="true"] { border: 1px dashed #24324d; }
QLabel#weaknessBadge { background-color: #2a1520; color: #ff8fa3; border: 1px solid #ff3366; border-radius: 9px; padding: 4px 8px; }
QLabel#weaknessBadge[ok="true"] { background-color: #0f2a22; color: #5eead4; border: 1px solid #14b8a6; }
QComboBox, QCheckBox { color: #e2e8f0; background-color: #161e2e; padding: 4px; }
QSpinBox { color: #e2e8f0; background-color: #161e2e; border: 1px solid #24324d; border-radius: 4px; padding: 4px 48px 4px 6px; min-width: 36px; max-width: 48px; selection-background-color: #1e2a40; }
""" + BREAKDOWN_BUTTON_STYLE

# --- Option 2: combat simulator model -------------------------------------
# Post-Update 36 (Jade Shadows): enemy armor caps at 2,700 (90% DR, sqrt curve)
# and Steel Path no longer applies a 2.5x armor multiplier (HP still gets 2.5x).
SIM_TARGETS = [
    {"name": "강철의 길 그리니어 헤비거너 Lv 150", "faction": "grineer", "base_level": 8, "level": 150, "armor": 500.0, "health": 700.0, "steel_path": True},
    {"name": "강철의 길 그리니어 헤비거너 Lv 225", "faction": "grineer", "base_level": 8, "level": 225, "armor": 500.0, "health": 700.0, "steel_path": True},
    {"name": "강철의 길 그리니어 봄바드 Lv 150", "faction": "grineer", "base_level": 1, "level": 150, "armor": 500.0, "health": 300.0, "steel_path": True},
    {"name": "강철의 길 코퍼스 테크 Lv 150 (무장갑)", "faction": "corpus", "base_level": 15, "level": 150, "armor": 0.0, "health": 700.0, "steel_path": True},
]
HEADSHOT_MULT = 3.0
VIRAL_MULT = 4.25          # 10 viral stacks: +325% vs health
CORROSIVE_STRIP = 0.8      # 10 corrosive stacks strip 80% armor
HEAT_STRIP = 0.5           # heat proc strips 50% armor (multiplicative with corrosive)
ARCANE_DAMAGE_BONUS = 3.6  # full-stack primary/secondary arcane: +360% base damage (additive with damage mods)
ARMOR_CAP = 2700.0         # U36 enemy armor cap (90% DR)


def scaled_armor(target, corrosive=False, heat=False):
    """Post-U36 enemy armor: BaseArmor * (1 + (Level - BaseLevel)^1.75 * 0.005), capped at 2,700.

    Corrosive (-80%) and Heat (-50%) armor strips stack multiplicatively: (1 - corr) * (1 - heat).
    """
    d = max(0.0, float(target["level"]) - float(target["base_level"]))
    armor = float(target["armor"]) * (1.0 + d ** 1.75 * 0.005)
    armor = min(armor, ARMOR_CAP)
    if corrosive:
        armor *= (1.0 - CORROSIVE_STRIP)
    if heat:
        armor *= (1.0 - HEAT_STRIP)
    return armor


def scaled_health(target):
    d = max(0.0, float(target["level"]) - float(target["base_level"]))
    low, high = 1.0 + 0.015 * d ** 2, 1.0 + 24.0 * math.sqrt(5.0) / 5.0 * d ** 0.5
    t = min(1.0, max(0.0, (d - 70.0) / 10.0))  # smoothstep blend between Lv-diff 70 and 80
    s = t * t * (3 - 2 * t)
    hp = float(target["health"]) * (low * (1 - s) + high * s)
    return hp * 2.5 if target.get("steel_path") else hp


def _resolve_headshot_mult(metrics, is_melee=False):
    if isinstance(metrics, dict):
        ratio = metrics.get("headshot_ratio")
        if isinstance(ratio, (int, float)) and ratio > 0:
            return float(ratio)
        hs_exp = metrics.get("headshot_expected_hit")
        exp = metrics.get("expected_hit")
        if isinstance(hs_exp, (int, float)) and isinstance(exp, (int, float)) and exp > 0 and hs_exp > 0:
            return float(hs_exp) / float(exp)
    return 1.0 if is_melee else HEADSHOT_MULT


def simulate_combat(
    base_dps,
    target,
    headshot=False,
    viral=False,
    corrosive=False,
    arcane=False,
    damage_bonus=0.0,
    *,
    heat=False,
    metrics=None,
    is_melee=False,
    arcane_bonus=None,
):
    armor = scaled_armor(target, corrosive=corrosive, heat=heat)
    dr = enemy_armor_dr(armor)
    denom = max(0.1, 1.0 + float(damage_bonus or 0.0))
    eff_arcane_bonus = (0.0 if is_melee else ARCANE_DAMAGE_BONUS) if arcane_bonus is None else float(arcane_bonus)
    hs_mult = _resolve_headshot_mult(metrics, is_melee=is_melee) if headshot else 1.0
    viral_mult = VIRAL_MULT if viral else 1.0
    arcane_mult = ((denom + eff_arcane_bonus) / denom) if (arcane and eff_arcane_bonus > 0) else 1.0
    dot_mult = viral_mult * arcane_mult
    direct_mult = hs_mult * dot_mult

    # Target faction element modifiers + equipped Bane (1x direct, ^2 on DoT; Slash ignores faction weakness table).
    target_faction = str(target.get("faction") or "").strip().lower()
    direct_faction_mult = 1.0
    non_slash_faction_mult = 1.0
    slash_faction_mult = 1.0
    if isinstance(metrics, dict) and target_faction in FACTION_MODIFIERS and (
        metrics.get("elements") or metrics.get("faction_by_name") or metrics.get("generic_faction")
    ):
        table = FACTION_MODIFIERS[target_faction]
        types = (metrics.get("elements") or {}).get("types") or {}
        type_total = sum(float(v) for v in types.values() if isinstance(v, (int, float)) and v > 0)
        el_direct_mult = (
            sum(float(v) * table.get(k, 1.0) for k, v in types.items() if isinstance(v, (int, float)) and v > 0) / type_total
            if type_total > 0 else 1.0
        )
        generic_f = float(metrics.get("generic_faction") or 0.0)
        fac_map = metrics.get("faction_by_name") or {}
        active_f = float(metrics.get("active_faction_bonus") or 0.0)
        target_f = generic_f + float(fac_map.get(target_faction, 0.0))
        bane_direct = max(0.0, 1.0 + target_f) / max(0.01, 1.0 + active_f)
        bane_dot = bane_direct ** 2
        direct_faction_mult = el_direct_mult * bane_direct
        slash_faction_mult = bane_dot
        sb = metrics.get("status_breakdown") or {}
        ns_total = sum(float(v) for k, v in sb.items() if k != "slash" and isinstance(v, (int, float)) and v > 0)
        ns_el = (
            sum(float(v) * table.get(k, 1.0) for k, v in sb.items() if k != "slash" and isinstance(v, (int, float)) and v > 0) / ns_total
            if ns_total > 0 else 1.0
        )
        non_slash_faction_mult = ns_el * bane_dot

    # Split armor-ignoring Slash Bleed True Damage from armor-mitigated direct + elemental DoT.
    base_total = max(0.0, float(base_dps or 0.0))
    direct_dps = base_total
    slash_dps = 0.0
    non_slash_dot_dps = 0.0
    if isinstance(metrics, dict) and any(
        k in metrics for k in ("slash_status_sustained_dps", "non_slash_status_sustained_dps", "direct_sustained_dps")
    ):
        raw_direct = max(0.0, float(metrics.get("direct_sustained_dps") or 0.0))
        raw_slash = max(0.0, float(metrics.get("slash_status_sustained_dps") or 0.0))
        raw_non_slash = max(0.0, float(metrics.get("non_slash_status_sustained_dps") or 0.0))
        raw_sum = raw_direct + raw_slash + raw_non_slash
        if raw_sum > 0 and base_total > 0:
            scale = (base_total / raw_sum) if abs(base_total - raw_sum) > max(1.0, 0.02 * base_total) else 1.0
            direct_dps = raw_direct * scale
            slash_dps = raw_slash * scale
            non_slash_dot_dps = raw_non_slash * scale

    # Headshot/weakpoint multiplier applies to direct hits only; status DoT ticks do not inherit weakpoint mults.
    eff_direct = direct_dps * direct_mult * direct_faction_mult * (1.0 - dr)
    eff_non_slash = non_slash_dot_dps * dot_mult * non_slash_faction_mult * (1.0 - dr)
    eff_slash = slash_dps * dot_mult * slash_faction_mult  # Slash Bleed is True Damage: ignores armor DR.
    eff = eff_direct + eff_non_slash + eff_slash
    base_no_toggles = direct_dps * (1.0 - dr) + non_slash_dot_dps * (1.0 - dr) + slash_dps
    overall_mult = (eff / base_no_toggles) if base_no_toggles > 0 else (direct_mult * direct_faction_mult)
    hp = scaled_health(target)
    return {
        "armor": armor,
        "damage_reduction": dr,
        "health": hp,
        "multiplier": overall_mult,
        "headshot_mult": hs_mult,
        "faction_mult": direct_faction_mult,
        "direct_effective_dps": eff_direct,
        "non_slash_effective_dps": eff_non_slash,
        "slash_effective_dps": eff_slash,
        "effective_dps": eff,
        "ttk": hp / eff if eff > 0 else math.inf,
    }


# --- Option 3: build 2x4 grid, radar and weakness diagnosis ------------------
STAT_KEYS = ("damage", "multishot", "elemental_damage", "crit_chance", "crit_damage", "fire_rate", "status")
EXTRA_SHARE_KEYS = ("weak_point", "weak_point_crit", "faction", "forced_bleed", "ips")
ALL_SHARE_KEYS = STAT_KEYS + EXTRA_SHARE_KEYS
# (key, axis label, bucket value treated as the radar's outer ring)
RADAR_AXES = [("damage", "피해", 3.0), ("multishot", "멀티샷", 2.0), ("elemental_damage", "속성", 3.6),
              ("crit_chance", "치확", 3.0), ("crit_damage", "치피", 2.5), ("fire_rate", "연사", 1.0)]
# Melee weapons have no multishot; status and attack speed matter instead.
MELEE_RADAR_AXES = [("damage", "피해", 3.0), ("status", "상태이상", 2.0), ("elemental_damage", "속성", 3.6),
                    ("crit_chance", "치확", 3.0), ("crit_damage", "치피", 2.5), ("fire_rate", "공속", 1.0)]
STAT_LABELS = dict(
    {k: label for k, label, _ in RADAR_AXES},
    status="상태이상",
    status_chance="상태이상 확률",
    status_type_direct="상태이상 종류당 피해",
    attack_speed="공격 속도",
    weak_point="약점 피해",
    weak_point_crit="약점 치확",
    faction="진영 피해",
    forced_bleed="강제 출혈",
    ips="물리 피해",
)
MELEE_STAT_LABELS = dict(STAT_LABELS, **{k: label for k, label, _ in MELEE_RADAR_AXES})
# Same assumptions as WarframeDamageEngine.compute_full_stack for conditional melee mods.
COMBO_MULT = 12.0
STATUS_TYPES = 3
# Realistic DoT weight when estimating status mod share without multiplying direct DPS by (1 + status).
MELEE_STATUS_DOT_WEIGHT = 0.15


def is_melee_weapon(w_meta):
    w_meta = w_meta or {}
    cat = str(w_meta.get("category") or "").lower()
    w_type = str(w_meta.get("type") or "").lower()
    return "melee" in cat or w_type == "melee"


def is_sniper_weapon(w_meta):
    if is_melee_weapon(w_meta):
        return False
    w_meta = w_meta or {}
    w_type = str(w_meta.get("type") or "").lower()
    w_cat = str(w_meta.get("category") or "").lower()
    w_name = f"{w_meta.get('name') or ''} {w_meta.get('kr_name') or ''}".lower()
    return ("sniper" in w_type or "sniper" in w_cat or "저격" in w_type or "저격" in w_cat
            or "sniper" in w_name or "저격" in w_name)


def _mod_locks_multishot(mod):
    return bool(mod.get("lock_multishot") or "acuity" in str(mod.get("name", "")).lower())


def _mod_faction_bonus(mod):
    fac_val = float(mod.get("faction_damage") or 0.0)
    fac_dict = mod.get("faction")
    if isinstance(fac_dict, dict) and fac_dict:
        fac_val += max((float(v or 0.0) for v in fac_dict.values()), default=0.0)
    return fac_val


def _mod_forced_bleed(mod):
    name = str(mod.get("name") or "").lower()
    if mod.get("hunter_munitions") or "hunter munitions" in name:
        return 0.30
    if mod.get("internal_bleeding") or "internal bleeding" in name or "hemorrhage" in name:
        return 0.35
    return 0.0


def mod_stat(mod, key):
    """Bucket value of one mod, counting conditional/stacking bonuses at their usual uptime."""
    if key == "weak_point":
        return float(mod.get("weak_point_damage") or 0.0)
    if key == "weak_point_crit":
        return float(mod.get("weak_point_crit_chance") or 0.0)
    if key == "faction":
        return _mod_faction_bonus(mod)
    if key == "forced_bleed":
        return _mod_forced_bleed(mod)
    if key == "ips":
        return sum(float(mod.get(k) or 0.0) for k in ("slash", "impact", "puncture"))
    raw = mod.get(key)
    value = float(raw) if isinstance(raw, (int, float)) else 0.0
    if key == "damage":
        value = float(mod.get("damage") or mod.get("base_damage") or 0.0)
        value += float(mod.get("status_type_damage") or 0.0) * STATUS_TYPES
    elif key == "crit_chance":
        value += float(mod.get("combo_crit") or 0.0) * (COMBO_MULT - 1.0)
    elif key == "status":
        value += float(mod.get("status_chance") or 0.0) + float(mod.get("status_damage") or 0.0)
        value += float(mod.get("combo_status") or 0.0) * (COMBO_MULT - 1.0)
    for e in mod.get("on_kill") or []:
        stat, total = e.get("stat"), float(e.get("value") or 0.0) * float(e.get("stacks") or 1)
        if stat == key:
            value += total
        elif stat == "attack_speed" and key == "fire_rate":
            value += total
        elif stat == "status_type_direct" and key == "damage":
            value += total * STATUS_TYPES
    for e in mod.get("on_weakpoint") or []:
        stat, total = e.get("stat"), float(e.get("value") or 0.0) * float(e.get("stacks") or 1)
        if stat == key:
            value += total
    return value


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


def prepared_effective_mods(w_meta, mod_objs, riven_stats=None):
    """Apply WarframeDamageEngine._prepare_mods() (set bonuses & innate traits) + riven replacement."""
    raw = list(mod_objs or [])
    prepared = _ENGINE_HELPER._prepare_mods(w_meta, raw) if w_meta else raw
    return effective_mods(prepared, riven_stats)


def stat_totals(mods):
    totals = {k: sum(mod_stat(m, k) for m in mods) for k in ALL_SHARE_KEYS}
    if any(_mod_locks_multishot(m) for m in mods):
        totals["multishot"] = 0.0
    return totals


def dps_factor(totals, base_cc, base_cd, is_melee=False):
    cc = max(0.0, base_cc * (1.0 + totals.get("crit_chance", 0.0) + totals.get("weak_point_crit", 0.0)))
    cd = max(1.0, base_cd * (1.0 + totals.get("crit_damage", 0.0)))
    product = 1.0 + cc * (cd - 1.0)
    product *= max(0.1, 1.0 + totals.get("damage", 0.0))
    product *= max(0.1, 1.0 + totals.get("elemental_damage", 0.0) + 0.35 * totals.get("ips", 0.0))
    product *= max(0.1, 1.0 + totals.get("fire_rate", 0.0))
    if not is_melee:
        product *= max(0.1, 1.0 + totals.get("multishot", 0.0))
    product *= max(0.1, 1.0 + totals.get("faction", 0.0))
    product *= max(0.1, 1.0 + 0.5 * totals.get("weak_point", 0.0))
    # Status DoTs add a bounded DoT component instead of multiplying melee direct DPS by (1 + status).
    dot_addon = totals.get("forced_bleed", 0.0) * min(1.0, cc) * 2.1
    if is_melee and totals.get("status", 0.0) > 0:
        dot_addon += MELEE_STATUS_DOT_WEIGHT * totals.get("status", 0.0)
    return product * (1.0 + dot_addon)


def mod_dps_share(mod, totals, base_cc, base_cd, is_melee=False):
    """Share of the build's DPS lost if this single mod were removed."""
    full = dps_factor(totals, base_cc, base_cd, is_melee)
    without = {k: totals.get(k, 0.0) - mod_stat(mod, k) for k in ALL_SHARE_KEYS}
    return 1.0 - dps_factor(without, base_cc, base_cd, is_melee) / full if full > 0 else 0.0


TABLE_KEYS = ("damage", "multishot", "elemental_damage", "crit_chance", "crit_damage", "fire_rate")
GLADIATOR_COMBO_CRIT = 0.10
SNIPER_MULTS = (1.0, 1.5, 2.0, 2.5, 3.0)


def is_gladiator_mod(m):
    name = f"{m.get('name') or ''} {m.get('kr_name') or ''}".lower()
    return ("Gladiator" in str(m.get("modSet") or "") or m.get("set") == "Gladiator"
            or "gladiator" in name or "글래디에이터" in name)


def blood_rush_crit(m):
    """combo_crit without the Gladiator set +10% that _apply_mod_sets() already folded in."""
    cc = float(m.get("combo_crit") or 0.0)
    if m.get("_set_applied") and is_gladiator_mod(m):
        cc = max(0.0, cc - GLADIATOR_COMBO_CRIT)
    return cc


def conditional_effects(m, test=None):
    """(active extra stats per table column, readable notes) for combo/status-type/on-kill mods."""
    test = test or {}
    cx = max(0.0, float(test.get("combo_mult", 1.0)) - 1.0)
    st, on_kill = int(test.get("status_types", 0)), bool(test.get("on_kill_active"))
    extra, notes = dict.fromkeys(TABLE_KEYS, 0.0), []
    br, ww, co = blood_rush_crit(m), float(m.get("combo_status") or 0.0), float(m.get("status_type_damage") or 0.0)
    if br:
        extra["crit_chance"] += br * cx
        notes.append(f"블러드 러쉬: 연속기당 치확 +{br * 100:g}% → +{br * cx * 100:.0f}%")
    if is_gladiator_mod(m):
        notes.append(f"글래디에이터 세트: 연속기당 치확 +{GLADIATOR_COMBO_CRIT * 100:g}%/세트")
    if ww:
        notes.append(f"위핑 운즈: 연속기당 상확 +{ww * 100:g}% → +{ww * cx * 100:.0f}%")
    if co:
        extra["damage"] += co * st
        notes.append(f"컨디션 오버로드: 상태이상 종류당 피해 +{co * 100:g}% → +{co * st * 100:.0f}% ({st}종)")
    sc, sd = float(m.get("status") or 0.0) + float(m.get("status_chance") or 0.0), float(m.get("status_damage") or 0.0)
    if sc:
        notes.append(f"상태이상 확률 +{sc * 100:.0f}%")
    if sd:
        notes.append(f"상태이상 피해 +{sd * 100:.0f}%")
    for e in m.get("on_kill") or []:
        stat, total = e.get("stat"), float(e.get("value") or 0.0) * float(e.get("stacks") or 1)
        if on_kill and stat == "status_type_direct":
            extra["damage"] += total * st
        elif on_kill and stat == "attack_speed":
            extra["fire_rate"] += total
        elif on_kill and stat in extra:
            extra[stat] += total
        notes.append(f"온킬 {STAT_LABELS.get(stat, stat)} +{total * 100:.0f}% ({'풀스택 적용' if on_kill else '미적용'})")
    for e in m.get("on_weakpoint") or []:
        stat, total = e.get("stat"), float(e.get("value") or 0.0) * float(e.get("stacks") or 1)
        if on_kill and stat in extra:
            extra[stat] += total
        notes.append(f"약점 {STAT_LABELS.get(stat, stat)} +{total * 100:.0f}% ({'풀스택 적용' if on_kill else '미적용'})")
    if float(m.get("weak_point_damage") or 0.0):
        notes.append(f"약점 피해 +{float(m['weak_point_damage']) * 100:.0f}%")
    if float(m.get("weak_point_crit_chance") or 0.0):
        notes.append(f"약점 치확 +{float(m['weak_point_crit_chance']) * 100:.0f}%")
    if _mod_locks_multishot(m):
        notes.append("멀티샷 고정")
    fac_b = _mod_faction_bonus(m)
    if fac_b:
        notes.append(f"진영 피해 +{fac_b * 100:.0f}%")
    if _mod_forced_bleed(m):
        notes.append(f"강제 출혈 ({_mod_forced_bleed(m) * 100:.0f}%)")
    for ips_k, ips_lbl in (("slash", "베기"), ("impact", "충격"), ("puncture", "관통")):
        if float(m.get(ips_k) or 0.0):
            notes.append(f"{ips_lbl} +{float(m[ips_k]) * 100:.0f}%")
    return extra, notes


def compute_numeric_test(w_meta, mod_objs, metrics, riven_stats=None, *, combo_mult=1, sniper_mult=1.0,
                         gladiator_stacks=None, status_types=0, on_kill_active=False):
    """Re-scales the build's metrics for the conditional test knobs (combo, sniper combo, CO, galvanized)."""
    w_meta, metrics = w_meta or {}, metrics or {}
    mods = prepared_effective_mods(w_meta, mod_objs, riven_stats)
    combo_mult, sniper_mult = max(1.0, float(combo_mult)), max(1.0, float(sniper_mult))
    status_types = max(0, int(status_types))
    is_melee = is_melee_weapon(w_meta)
    equipped_gladiator = sum(1 for m in mods if is_gladiator_mod(m)) if is_melee else 0
    if gladiator_stacks is None:
        gladiator_stacks = equipped_gladiator
    test = dict(combo_mult=combo_mult, sniper_mult=sniper_mult, gladiator_stacks=int(gladiator_stacks),
                status_types=status_types, on_kill_active=bool(on_kill_active))
    glad_changed = int(gladiator_stacks) != equipped_gladiator
    test["is_test_active"] = (combo_mult != 1 or sniper_mult != 1.0 or status_types != 0 or bool(on_kill_active)
                              or glad_changed)
    cx = combo_mult - 1.0

    lock_ms = bool(metrics.get("lock_multishot")) or any(_mod_locks_multishot(m) for m in mods)
    lock_fr = bool(metrics.get("lock_fire_rate")) or any(m.get("lock_fire_rate") for m in mods)

    base_cc = float(w_meta.get("crit_chance", 0.1) or 0.0)
    base_cc = base_cc / 100.0 if base_cc > 1.0 else base_cc
    base_cd = float(w_meta.get("crit_mult", 1.5) or 1.5)
    base_sc = float(w_meta.get("status_chance") or w_meta.get("status") or w_meta.get("procChance") or 0.0)
    base_sc = base_sc / 100.0 if base_sc > 1.0 else base_sc
    flat = {k: sum(float(m.get(k) or (m.get("base_damage") if k == "damage" else 0.0) or 0.0) for m in mods) for k in TABLE_KEYS}
    if lock_ms:
        flat["multishot"] = 0.0
    if lock_fr:
        flat["fire_rate"] = 0.0
    extra = dict.fromkeys(TABLE_KEYS, 0.0)
    for m in mods:
        for k, v in conditional_effects(m, test)[0].items():
            extra[k] += v
    if lock_ms:
        extra["multishot"] = 0.0
    if lock_fr:
        extra["fire_rate"] = 0.0
    br_cc = sum(blood_rush_crit(m) for m in mods) * cx
    glad_cc = GLADIATOR_COMBO_CRIT * test["gladiator_stacks"] * cx
    on_kill = [e for m in mods for e in (m.get("on_kill") or [])] if on_kill_active else []
    ok_sc = sum(float(e.get("value") or 0.0) * float(e.get("stacks") or 1) for e in on_kill if e.get("stat") in ("status", "status_chance"))
    flat_sc = sum(float(m.get("status") or 0.0) + float(m.get("status_chance") or 0.0) for m in mods)
    ww_sc = sum(float(m.get("combo_status") or 0.0) for m in mods) * cx

    flat_cc_add = sum(float(m.get("flat_crit_chance") or 0.0) for m in mods)
    flat_cd_add = sum(float(m.get("flat_crit_damage") or 0.0) for m in mods)
    flat_sc_add = sum(float(m.get("flat_status") or 0.0) for m in mods)

    cc0 = max(0.0, base_cc * (1.0 + flat["crit_chance"]) + flat_cc_add)
    cd0 = max(1.0, base_cd * (1.0 + flat["crit_damage"]) + flat_cd_add)
    cc1 = max(0.0, base_cc * (1.0 + flat["crit_chance"] + extra["crit_chance"] + glad_cc) + flat_cc_add)
    cd1 = max(1.0, base_cd * (1.0 + flat["crit_damage"] + extra["crit_damage"]) + flat_cd_add)
    dmg_ratio = max(0.1, 1.0 + flat["damage"] + extra["damage"]) / max(0.1, 1.0 + flat["damage"])
    ms_ratio = 1.0 if lock_ms else max(0.1, 1.0 + flat["multishot"] + extra["multishot"]) / max(0.1, 1.0 + flat["multishot"])
    fr_ratio = 1.0 if lock_fr else max(0.1, 1.0 + flat["fire_rate"] + extra["fire_rate"]) / max(0.1, 1.0 + flat["fire_rate"])
    sc_val0 = max(0.0, base_sc * (1.0 + flat_sc) + flat_sc_add)
    sc_val1 = max(0.0, base_sc * (1.0 + flat_sc + ww_sc + ok_sc) + flat_sc_add)
    if sc_val0 > 0:
        sc_ratio = sc_val1 / sc_val0
    else:
        sc_ratio = max(0.1, 1.0 + flat_sc + ww_sc + ok_sc) / max(0.1, 1.0 + flat_sc)

    vig = float(metrics.get("vigilante_chance") or 0.0)
    crit_avg0 = average_crit_mult(cc0, cd0, vigilante_chance=vig)
    crit_avg1 = average_crit_mult(cc1, cd1, vigilante_chance=vig)
    hit_ratio = dmg_ratio * ms_ratio * sniper_mult
    dps_ratio = hit_ratio * fr_ratio * crit_avg1 / crit_avg0
    status_ratio = dps_ratio * sc_ratio
    # Hunter Munitions forced slash scales with crit probability * conditional crit mult, NOT status chance.
    hm_p0 = min(1.0, cc0) * hm_crit_avg(cc0, cd0, vigilante_chance=vig)
    hm_p1 = min(1.0, cc1) * hm_crit_avg(cc1, cd1, vigilante_chance=vig)
    hm_ratio = (hit_ratio * fr_ratio * (hm_p1 / hm_p0)) if hm_p0 > 0 else dps_ratio

    # Recompute shooting_proportion when fire rate changes on ranged weapons with magazine/reload data.
    prop_ratio = 1.0
    new_prop = metrics.get("shooting_proportion")
    if (not is_melee and abs(fr_ratio - 1.0) > 1e-6
            and isinstance(metrics.get("shooting_proportion"), (int, float))
            and metrics["shooting_proportion"] > 0
            and (w_meta.get("magazineSize") is not None or w_meta.get("reloadTime") is not None)):
        base_efr = float(metrics.get("effective_fire_rate") or metrics.get("final_fr") or w_meta.get("fire_rate") or 0.0)
        if base_efr > 0:
            mag, reload_t = _ENGINE_HELPER._magazine_and_reload(w_meta, mods, {})
            new_prop = shooting_proportion(mag, base_efr * fr_ratio, reload_t)
            prop_ratio = new_prop / float(metrics["shooting_proportion"])
    sustained_ratio = dps_ratio * prop_ratio

    test.update(base_crit_chance=base_cc, final_crit_chance=cc1, br_cc_bonus=br_cc, glad_cc_bonus=glad_cc,
                base_status_chance=base_sc, final_status_chance=sc_val1,
                ww_sc_bonus=ww_sc, on_kill_sc=ok_sc, final_crit_mult=cd1, co_damage_bonus=extra["damage"],
                damage_bonus_total=flat["damage"] + extra["damage"], dps_ratio=dps_ratio,
                dmg_ratio=dmg_ratio, ms_ratio=ms_ratio, fr_ratio=fr_ratio, sc_ratio=sc_ratio,
                status_ratio=status_ratio, hm_ratio=hm_ratio, prop_ratio=prop_ratio,
                lock_multishot=lock_ms, lock_fire_rate=lock_fr, extra=extra)

    scaled = dict(metrics)

    def tier(level, cd):  # crit tier multiplier, as min_crit/max_crit in WarframeDamageEngine
        return 1.0 + int(level) * (cd - 1.0)

    def tier_max(cc):
        return max(1, math.ceil(cc - 1e-6)) if cc > 0 else 0

    def tier_min(cc):
        return int(cc + 1e-6) if cc > 0 else 0

    if test["is_test_active"]:
        if isinstance(new_prop, (int, float)):
            scaled["shooting_proportion"] = float(new_prop)
        for key, ratio in (("sustained_dps", sustained_ratio), ("burst_dps", dps_ratio),
                           ("direct_burst_dps", dps_ratio), ("direct_sustained_dps", sustained_ratio),
                           ("max_crit_hit", hit_ratio * tier(tier_max(cc1), cd1) / tier(tier_max(cc0), cd0)),
                           ("min_hit", hit_ratio * tier(tier_min(cc1), cd1) / tier(tier_min(cc0), cd0))):
            if isinstance(metrics.get(key), (int, float)):
                scaled[key] = metrics[key] * ratio
        raw_sb = metrics.get("status_breakdown")
        hm_orig = max(0.0, float(metrics.get("hm_slash_dps") or 0.0))
        if isinstance(raw_sb, dict):
            scaled_sb = {}
            for sk, sv in raw_sb.items():
                if isinstance(sv, (int, float)):
                    sk_low = str(sk).strip().lower()
                    if sk_low == "slash" and hm_orig > 0:
                        hm_part = min(float(sv), hm_orig)
                        nat_part = max(0.0, float(sv) - hm_part)
                        scaled_sb[sk] = nat_part * status_ratio + hm_part * hm_ratio
                    elif "hunter" in sk_low:
                        scaled_sb[sk] = float(sv) * hm_ratio
                    else:
                        scaled_sb[sk] = float(sv) * status_ratio
                else:
                    scaled_sb[sk] = sv
            scaled["status_breakdown"] = scaled_sb
        if hm_orig > 0:
            scaled["hm_slash_dps"] = hm_orig * hm_ratio
        if isinstance(metrics.get("status_dps"), (int, float)):
            if isinstance(scaled.get("status_breakdown"), dict) and metrics["status_dps"] > 0:
                orig_sum = sum(v for v in raw_sb.values() if isinstance(v, (int, float)))
                if orig_sum > 0 and abs(orig_sum - metrics["status_dps"]) <= max(1.0, 0.02 * metrics["status_dps"]):
                    scaled["status_dps"] = sum(v for v in scaled["status_breakdown"].values() if isinstance(v, (int, float)))
                else:
                    scaled["status_dps"] = metrics["status_dps"] * status_ratio
            else:
                scaled["status_dps"] = metrics["status_dps"] * status_ratio
        # Keep slash vs non-slash sustained/burst splits consistent for simulate_combat.
        status_scale = (scaled["status_dps"] / metrics["status_dps"]) if (
            isinstance(metrics.get("status_dps"), (int, float)) and metrics["status_dps"] > 0
            and isinstance(scaled.get("status_dps"), (int, float))
        ) else status_ratio
        if isinstance(scaled.get("status_breakdown"), dict):
            new_slash_burst = float(scaled["status_breakdown"].get("slash", 0.0) or 0.0)
            new_non_slash_burst = max(0.0, float(scaled.get("status_dps") or 0.0) - new_slash_burst)
            if "slash_status_dps" in metrics:
                scaled["slash_status_dps"] = new_slash_burst
            if "non_slash_status_dps" in metrics:
                scaled["non_slash_status_dps"] = new_non_slash_burst
            uptime_prop = float(scaled.get("shooting_proportion") or metrics.get("shooting_proportion") or 1.0)
            if "slash_status_sustained_dps" in metrics:
                scaled["slash_status_sustained_dps"] = new_slash_burst * uptime_prop
            if "non_slash_status_sustained_dps" in metrics:
                scaled["non_slash_status_sustained_dps"] = new_non_slash_burst * uptime_prop
            if isinstance(metrics.get("status_sustained_dps"), (int, float)):
                scaled["status_sustained_dps"] = float(scaled.get("status_dps") or 0.0) * uptime_prop
        else:
            if isinstance(metrics.get("status_sustained_dps"), (int, float)):
                scaled["status_sustained_dps"] = metrics["status_sustained_dps"] * status_scale * prop_ratio
            if isinstance(metrics.get("slash_status_sustained_dps"), (int, float)):
                scaled["slash_status_sustained_dps"] = metrics["slash_status_sustained_dps"] * status_scale * prop_ratio
            if isinstance(metrics.get("non_slash_status_sustained_dps"), (int, float)):
                scaled["non_slash_status_sustained_dps"] = metrics["non_slash_status_sustained_dps"] * status_scale * prop_ratio

        if (isinstance(metrics.get("direct_burst_dps"), (int, float))
                and isinstance(metrics.get("status_dps"), (int, float))
                and metrics["status_dps"] > 0
                and isinstance(metrics.get("burst_dps"), (int, float))):
            orig_total = metrics["direct_burst_dps"] + metrics["status_dps"]
            if abs(metrics["burst_dps"] - orig_total) <= max(1.0, 0.02 * abs(metrics["burst_dps"])):
                scaled["burst_dps"] = scaled["direct_burst_dps"] + scaled["status_dps"]
                if isinstance(metrics.get("sustained_dps"), (int, float)) and metrics["burst_dps"] > 0:
                    if isinstance(scaled.get("direct_sustained_dps"), (int, float)) and isinstance(scaled.get("status_sustained_dps"), (int, float)):
                        scaled["sustained_dps"] = scaled["direct_sustained_dps"] + scaled["status_sustained_dps"]
                    else:
                        uptime = (metrics["sustained_dps"] / metrics["burst_dps"]) * prop_ratio
                        scaled["sustained_dps"] = scaled["burst_dps"] * uptime
    test["metrics"] = scaled
    test.update(expected_dps=scaled.get("sustained_dps"), burst_dps=scaled.get("burst_dps"),
                peak=scaled.get("max_crit_hit"), trough=scaled.get("min_hit"),
                direct_burst_dps=scaled.get("direct_burst_dps"), status_dps=scaled.get("status_dps", 0.0))
    show_melee = is_melee_weapon(w_meta) or combo_mult > 1 or int(gladiator_stacks) > 0 or br_cc > 0 or ww_sc > 0
    show_sniper = is_sniper_weapon(w_meta) or sniper_mult > 1.0
    summary_parts = []
    if show_melee:
        summary_parts.append(f"연속기 {combo_mult:g}x")
    if show_sniper:
        summary_parts.append(f"저격 {sniper_mult:.1f}x")
    summary_parts.extend([
        f"치확 {cc0 * 100:.1f}%→{cc1 * 100:.1f}%",
        f"상확 {base_sc * (1 + flat_sc) * 100:.1f}%→{test['final_status_chance'] * 100:.1f}%",
        f"CO +{extra['damage'] * 100:.0f}%",
        f"DPS x{dps_ratio:.2f}",
    ])
    test["summary"] = ("🧪 테스트 OFF — 원본 수치 표시 중" if not test["is_test_active"] else
                       "🧪 " + " · ".join(summary_parts))
    crit_line = (
        f"• 치명타 확률 = {base_cc * 100:.1f}% × (1 + 모드 {flat['crit_chance'] * 100:+.0f}% + 블러드 러쉬 {br_cc * 100:+.0f}%"
        f" + 글래디에이터 {test['gladiator_stacks']}세트 {glad_cc * 100:+.0f}%"
        f" + 온킬 {(extra['crit_chance'] - br_cc) * 100:+.0f}%) = {cc1 * 100:.1f}%"
        if show_melee else
        f"• 치명타 확률 = {base_cc * 100:.1f}% × (1 + 모드 {flat['crit_chance'] * 100:+.0f}%"
        f" + 온킬 {extra['crit_chance'] * 100:+.0f}%) = {cc1 * 100:.1f}%"
    )
    status_line = (
        f"• 상태이상 확률 = {base_sc * 100:.1f}% × (1 + 모드 {flat_sc * 100:+.0f}% + 위핑 운즈 {ww_sc * 100:+.0f}%"
        f" + 온킬 {ok_sc * 100:+.0f}%) = {test['final_status_chance'] * 100:.1f}%"
        if show_melee else
        f"• 상태이상 확률 = {base_sc * 100:.1f}% × (1 + 모드 {flat_sc * 100:+.0f}%"
        f" + 온킬 {ok_sc * 100:+.0f}%) = {test['final_status_chance'] * 100:.1f}%"
    )
    if show_sniper and show_melee:
        mult_line = f"• 저격총 연속 적중 배수 x{sniper_mult:.1f} · 연속기 x{combo_mult:g} → DPS 배율 x{dps_ratio:.2f}"
    elif show_sniper:
        mult_line = f"• 저격총 연속 적중 배수 x{sniper_mult:.1f} → DPS 배율 x{dps_ratio:.2f}"
    elif show_melee:
        mult_line = f"• 연속기 x{combo_mult:g} → DPS 배율 x{dps_ratio:.2f}"
    else:
        mult_line = f"• 최종 DPS 배율 x{dps_ratio:.2f}"
    test["breakdown_text"] = "\n".join([
        "🧪 조건부 수치 테스트 (실시간 반영)",
        crit_line,
        status_line,
        f"• 피해 보너스 = 모드 {flat['damage'] * 100:+.0f}% + 조건부(CO {status_types}종/온킬) {extra['damage'] * 100:+.0f}%",
        mult_line,
    ] + ([f"• 상태이상 DoT DPS = {scaled['status_dps']:,.0f} (상확 배율 ×{sc_ratio:.2f})"]
         if isinstance(scaled.get("status_dps"), (int, float)) and scaled["status_dps"] > 0 else [])
      + ([f"• 글래디에이터 {test['gladiator_stacks']}세트 (장착 {equipped_gladiator}) — 연속기 1x에서는 보너스 없음, 12x 기준 예상 치확 "
          f"{base_cc * (1.0 + flat['crit_chance'] + GLADIATOR_COMBO_CRIT * test['gladiator_stacks'] * (COMBO_MULT - 1.0)) * 100:.1f}%"]
         if show_melee and glad_changed and combo_mult == 1 else [])) if test["is_test_active"] else ""
    return test


STATUS_DOT_LABELS = {
    "slash": "베기(출혈)",
    "bleed": "베기(출혈)",
    "hunter_munitions": "헌터 뮤니션",
    "heat": "화염",
    "toxin": "독성",
    "electric": "전기",
    "electricity": "전기",
    "gas": "가스",
    "blast": "폭발",
}


STATUS_DOT_SHORT_LABELS = {
    "slash": "베기",
    "bleed": "출혈",
    "hunter_munitions": "헌터",
    "heat": "화염",
    "toxin": "독성",
    "electric": "전기",
    "electricity": "전기",
    "gas": "가스",
    "blast": "폭발",
}


def _fmt_pipe_num(value):
    if value is None:
        return "-"
    val = float(value)
    if 0 < abs(val) < 100 and not val.is_integer():
        return f"{val:,.1f}"
    return f"{val:,.0f}"


def _format_status_breakdown_raw(status_breakdown):
    if not isinstance(status_breakdown, dict):
        return []
    items = [(str(k).strip().lower(), float(v)) for k, v in status_breakdown.items()
             if isinstance(v, (int, float)) and v > 0]
    items.sort(key=lambda item: item[1], reverse=True)
    return items


def _format_status_breakdown(status_breakdown):
    """Return sorted [(label, dps), ...] entries for positive DoT contributors."""
    return [(STATUS_DOT_LABELS.get(k, k), val) for k, val in _format_status_breakdown_raw(status_breakdown)]


def build_pipeline_steps(w_meta, mod_objs, metrics, riven_stats=None, test_result=None):
    """Build structured stage cards for the Tab 3 Multiplier Pipeline Flow Block."""
    w_meta = w_meta or {}
    base_metrics = metrics or {}
    test = test_result or {}
    test_active = bool(test.get("is_test_active"))
    active_metrics = (test.get("metrics") if test_active and isinstance(test.get("metrics"), dict) else base_metrics) or {}
    mods = prepared_effective_mods(w_meta, mod_objs, riven_stats)
    is_melee = is_melee_weapon(w_meta)

    base_dmg = float(w_meta.get("total_damage") or 0.0)
    attacks = w_meta.get("attacks") or []
    dist = attacks[0].get("damage") if attacks and isinstance(attacks[0], dict) and isinstance(attacks[0].get("damage"), dict) else {}
    if base_dmg <= 0.0 and dist:
        base_dmg = sum(float(v or 0.0) for v in dist.values())

    base_ms = 1.0 if is_melee else float(w_meta.get("base_multishot") or w_meta.get("multishot") or 1.0)
    base_fr = float(w_meta.get("fire_rate") or 0.0)
    base_cc = float(w_meta.get("crit_chance", 0.0) or 0.0)
    if base_cc > 1.0:
        base_cc /= 100.0
    base_cd = float(w_meta.get("crit_mult", 1.5) or 1.5)

    if isinstance(base_metrics.get("effective_mod_dmg"), (int, float)):
        flat_dmg = float(base_metrics["effective_mod_dmg"])
    else:
        flat_dmg = sum(float(m.get("damage") or m.get("base_damage") or 0.0) for m in mods)
    flat_elem = sum(float(m.get("elemental_damage") or 0.0) for m in mods)
    flat_cc = sum(float(m.get("crit_chance") or 0.0) for m in mods)
    flat_cd = sum(float(m.get("crit_damage") or 0.0) for m in mods)
    lock_ms = bool(base_metrics.get("lock_multishot")) or any(_mod_locks_multishot(m) for m in mods)
    lock_fr = bool(base_metrics.get("lock_fire_rate")) or any(m.get("lock_fire_rate") for m in mods)
    flat_ms = 0.0 if lock_ms else sum(float(m.get("multishot") or 0.0) for m in mods)
    flat_fr = 0.0 if lock_fr else sum(float(m.get("fire_rate") or 0.0) for m in mods)
    if isinstance(base_metrics.get("active_faction_bonus"), (int, float)):
        flat_faction = float(base_metrics["active_faction_bonus"])
    else:
        flat_faction = sum(float(m.get("faction_damage") or 0.0) for m in mods)
    dist_total = sum(float(v or 0.0) for v in dist.values()) if dist else 0.0
    phys_elem = (sum((float(dist.get(k, 0.0) or 0.0) / dist_total) * sum(float(m.get(k) or 0.0) for m in mods)
                     for k in ("slash", "impact", "puncture")) if dist_total > 0 else 0.0)

    extra = (test.get("extra") or {}) if test_active else {}
    extra_dmg = float(extra.get("damage") or 0.0)
    extra_elem = float(extra.get("elemental_damage") or 0.0)
    extra_ms = 0.0 if lock_ms else float(extra.get("multishot") or 0.0)
    extra_fr = 0.0 if lock_fr else float(extra.get("fire_rate") or 0.0)
    sniper_mult = max(1.0, float(test.get("sniper_mult") or 1.0)) if test_active else 1.0

    # On ranged weapons, total_damage is per-pellet so final_dmg scales directly by final_ms (not final_ms / base_ms).
    if is_melee:
        base_ms_factor = 1.0
        ms_factor = 1.0
    elif isinstance(base_metrics.get("final_ms"), (int, float)) and float(base_metrics["final_ms"]) > 0:
        base_ms_factor = float(base_metrics["final_ms"])
        if test_active and not lock_ms:
            ms_factor = base_ms_factor * (max(0.1, 1.0 + flat_ms + extra_ms) / max(0.1, 1.0 + flat_ms))
        else:
            ms_factor = base_ms_factor
    else:
        base_ms_factor = max(0.1, base_ms * max(0.1, 1.0 + flat_ms))
        ms_factor = max(0.1, base_ms * max(0.1, 1.0 + flat_ms + extra_ms))

    dmg_mult = max(0.1, 1.0 + flat_dmg + extra_dmg)
    if isinstance(base_metrics.get("effective_mod_elem"), (int, float)):
        base_elem_mult = max(0.1, 1.0 + float(base_metrics["effective_mod_elem"]))
    else:
        base_elem_mult = max(0.1, 1.0 + flat_elem + phys_elem)
    if isinstance(base_metrics.get("final_dmg"), (int, float)) and base_dmg > 0:
        # Accounts for multiplicative Valence (1 + valence) * (1 + elem) and innate physical multipliers.
        implied_elem = float(base_metrics["final_dmg"]) / (base_dmg * max(0.1, 1.0 + flat_dmg) * base_ms_factor)
        if implied_elem >= 0.1 and abs(implied_elem - base_elem_mult) > 0.005:
            base_elem_mult = implied_elem
    elem_mult = max(0.1, base_elem_mult + extra_elem)
    faction_mult = max(0.1, 1.0 + flat_faction)
    elem_faction_mult = elem_mult * faction_mult

    if test_active and "final_crit_chance" in test and "final_crit_mult" in test:
        eff_cc = max(0.0, float(test["final_crit_chance"]))
        eff_cd = max(1.0, float(test["final_crit_mult"]))
    elif isinstance(base_metrics.get("final_cc"), (int, float)) and isinstance(base_metrics.get("final_cd"), (int, float)):
        eff_cc = max(0.0, float(base_metrics["final_cc"]))
        eff_cd = max(1.0, float(base_metrics["final_cd"]))
    else:
        flat_cc_add = sum(float(m.get("flat_crit_chance") or 0.0) for m in mods)
        flat_cd_add = sum(float(m.get("flat_crit_damage") or 0.0) for m in mods)
        eff_cc = max(0.0, base_cc * (1.0 + flat_cc) + flat_cc_add)
        eff_cd = max(1.0, base_cd * (1.0 + flat_cd) + flat_cd_add)
    vig_chance = float(base_metrics.get("vigilante_chance") or 0.0)
    crit_exp_mult = average_crit_mult(eff_cc, eff_cd, vigilante_chance=vig_chance)

    fr_ratio = (1.0 if lock_fr else (max(0.1, 1.0 + flat_fr + extra_fr) / max(0.1, 1.0 + flat_fr))) if test_active else 1.0
    if isinstance(base_metrics.get("effective_fire_rate"), (int, float)) or isinstance(base_metrics.get("final_fr"), (int, float)):
        base_efr = float(base_metrics.get("effective_fire_rate") or base_metrics.get("final_fr") or 1.0)
        eff_fr = base_efr * fr_ratio
    else:
        fr_mult = max(0.1, 1.0 + flat_fr + extra_fr)
        eff_fr = (base_fr * fr_mult) if base_fr > 0 else fr_mult
    speed_ms_mult = eff_fr if is_melee else (ms_factor * eff_fr * sniper_mult)

    raw_status = active_metrics.get("status_dps")
    status_dps = float(raw_status) if isinstance(raw_status, (int, float)) else 0.0
    status_entries = _format_status_breakdown(active_metrics.get("status_breakdown"))

    cum1 = base_dmg if base_dmg > 0 else None
    cum2 = cum1 * dmg_mult if cum1 is not None else None
    cum3 = cum2 * elem_faction_mult if cum2 is not None else None
    cum4 = cum3 * crit_exp_mult if cum3 is not None else None
    cum5 = cum4 * speed_ms_mult if cum4 is not None else None

    raw_direct_burst = active_metrics.get("direct_burst_dps")
    raw_burst = active_metrics.get("burst_dps")
    raw_sustained = active_metrics.get("sustained_dps")
    if isinstance(raw_direct_burst, (int, float)):
        direct_burst_dps = float(raw_direct_burst)
    elif isinstance(raw_burst, (int, float)):
        direct_burst_dps = max(0.0, float(raw_burst) - status_dps)
    else:
        direct_burst_dps = cum5 if cum5 is not None else 0.0

    burst_dps = float(raw_burst) if isinstance(raw_burst, (int, float)) else (direct_burst_dps + status_dps)
    expected_dps = float(raw_sustained) if isinstance(raw_sustained, (int, float)) else burst_dps
    step5_val = cum5 if cum5 is not None else (direct_burst_dps if direct_burst_dps > 0 else None)
    step6_val = burst_dps if (isinstance(raw_burst, (int, float)) or direct_burst_dps > 0 or status_dps > 0) else step5_val

    if status_entries:
        short_items = []
        for k, val in _format_status_breakdown_raw(active_metrics.get("status_breakdown"))[:2]:
            short_items.append(f"{STATUS_DOT_SHORT_LABELS.get(k, k)} {val:,.0f}")
        top_status = " · ".join(short_items)
        if len(status_entries) > 2:
            top_status += f" +{len(status_entries) - 2}"
        status_detail = "\n".join(f"• {lbl}: {val:,.1f} DPS" for lbl, val in status_entries)
    elif status_dps > 0:
        top_status = "DoT 합산 반영"
        status_detail = f"• 상태이상 DoT 합산: +{status_dps:,.1f} DPS"
    else:
        top_status = "DoT 없음"
        status_detail = "• 활성 상태이상 DoT 없음 (0 DPS 폴백)"

    if is_melee:
        dmg_title, elem_title, crit_title, speed_title = "피해·CO 모드", "속성", "연속기·치명타 기댓값", "공속"
        speed_sub = f"공속 {eff_fr:.2f}/s"
        elem_sub = f"속성 {(elem_mult - 1.0) * 100:+.0f}%"
    else:
        dmg_title, elem_title, crit_title, speed_title = "피해 모드", "속성/팩션", "치명타 기댓값", "멀티샷·연사"
        speed_sub = f"{ms_factor:.2f}발 · {eff_fr:.2f}/s" + (f" · 저격×{sniper_mult:.1f}" if sniper_mult > 1.0 else "")
        elem_sub = f"속성 {(elem_mult - 1.0) * 100:+.0f}%" + (f" · 팩션×{faction_mult:.2f}" if faction_mult != 1.0 else "")

    steps = [
        {
            "key": "base", "title": "기본 피해", "operator": "", "badge": "기본",
            "value": cum1, "value_text": _fmt_pipe_num(cum1),
            "sub_text": "근접 원본" if is_melee else "무기 원본", "accent": "#00e5ff",
            "tooltip": f"기본 피해: {_fmt_pipe_num(cum1)}\n기본 치확 {base_cc * 100:.1f}% · 기본 치피 {base_cd:.1f}x · 기본 연사/공속 {base_fr:.2f}",
        },
        {
            "key": "damage", "title": dmg_title, "operator": "×", "badge": f"×{dmg_mult:.2f}",
            "value": cum2, "value_text": _fmt_pipe_num(cum2),
            "sub_text": f"피해 {(flat_dmg + extra_dmg) * 100:+.0f}%", "accent": "#00e5ff",
            "tooltip": f"{dmg_title}: ×{dmg_mult:.2f}\n기본 피해 모드 {flat_dmg * 100:+.1f}% + 테스트/CO {extra_dmg * 100:+.1f}%",
        },
        {
            "key": "elemental", "title": elem_title, "operator": "×", "badge": f"×{elem_faction_mult:.2f}",
            "value": cum3, "value_text": _fmt_pipe_num(cum3),
            "sub_text": elem_sub, "accent": "#b388ff",
            "tooltip": f"{elem_title}: ×{elem_faction_mult:.2f}\n속성/물리 배수 ×{elem_mult:.2f} · 팩션 배수 ×{faction_mult:.2f}",
        },
        {
            "key": "crit", "title": crit_title, "operator": "×", "badge": f"×{crit_exp_mult:.2f}",
            "value": cum4, "value_text": _fmt_pipe_num(cum4),
            "sub_text": f"치확 {eff_cc * 100:.0f}% · {eff_cd:.1f}x", "accent": "#ffd700",
            "tooltip": f"{crit_title}: ×{crit_exp_mult:.2f}\n최종 치확 {eff_cc * 100:.1f}% · 최종 치피 {eff_cd:.2f}x\n공식: 1 + {eff_cc:.2f} × ({eff_cd:.2f} - 1)",
        },
        {
            "key": "speed_ms", "title": speed_title, "operator": "×", "badge": f"×{speed_ms_mult:.2f}",
            "value": step5_val, "value_text": _fmt_pipe_num(step5_val),
            "sub_text": speed_sub, "accent": "#00e5ff",
            "tooltip": f"{speed_title}: ×{speed_ms_mult:.2f}\n{speed_sub}\n직접 타격 버스트 DPS: {direct_burst_dps:,.0f}",
        },
        {
            "key": "status", "title": "상태이상 DoT", "operator": "+", "badge": f"+{status_dps:,.0f}",
            "value": step6_val, "value_text": _fmt_pipe_num(step6_val),
            "sub_text": top_status, "accent": "#ff4d6d",
            "tooltip": f"상태이상 DoT: +{status_dps:,.0f} DPS\n{status_detail}\n직접+DoT 합산: {_fmt_pipe_num(step6_val)} DPS",
        },
        {
            "key": "result", "title": "기대 / 버스트 DPS", "operator": "", "badge": "최종 DPS",
            "value": burst_dps, "value_text": f"{expected_dps:,.0f} / {burst_dps:,.0f}",
            "expected_dps": expected_dps, "burst_dps": burst_dps,
            "sub_text": "기대 / 버스트", "accent": "#ffd700",
            "tooltip": f"기대(지속) DPS: {expected_dps:,.0f}\n버스트 DPS: {burst_dps:,.0f}\n(직접 {direct_burst_dps:,.0f} + DoT {status_dps:,.0f})",
        },
    ]
    return {
        "is_melee": is_melee,
        "direct_burst_dps": direct_burst_dps,
        "status_dps": status_dps,
        "burst_dps": burst_dps,
        "expected_dps": expected_dps,
        "status_entries": status_entries,
        "steps": steps,
    }


def diagnose_weaknesses(totals, base_cc, is_melee=False, lock_multishot=False):
    badges = []
    if totals["damage"] <= 0:
        badges.append("기본 피해 모드 누락 — " + ("프레셔 포인트/컨디션 오버로드 계열 부재" if is_melee else "서레이션/혼넷 스트라이크 계열 부재"))
    if not is_melee and not lock_multishot and totals.get("multishot", 0.0) <= 0:
        badges.append("멀티샷 누락 — 분열 사격 계열 부재")
    if totals["elemental_damage"] <= 0:
        badges.append("속성 모드 누락 — 90%/60% 속성 모드 부재")
    if totals["crit_damage"] > 0 and base_cc * (1.0 + totals["crit_chance"]) < 0.25:
        badges.append("시너지 누락 — 치확 25% 미만에서 치피 투자")
    for key, label, cap in (MELEE_RADAR_AXES if is_melee else RADAR_AXES):
        if totals.get(key, 0.0) > cap:
            badges.append(f"합연산 누수 — {label} 버킷 과적재 ({totals[key] * 100:+.0f}%), 다른 배수로 분산 권장")
    return badges


class RadarChart(QWidget):
    """6-axis tendency radar drawn with QPainter.drawPolygon()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = [label for _, label, _ in RADAR_AXES]
        self.values = [0.0] * len(self.labels)
        self.setMinimumSize(200, 200)

    def set_values(self, values, labels=None):
        if labels is not None:
            self.labels = list(labels)
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


class ClickableSpinBox(QSpinBox):
    """QSpinBox whose arrow areas step even when the inner QLineEdit (or a theme) covers the buttons."""
    ARROW_WIDTH = 52

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineEdit().installEventFilter(self)

    def _arrow_step(self, pos):
        opt = QStyleOptionSpinBox()
        self.initStyleOption(opt)
        cc, sc = QStyle.ComplexControl.CC_SpinBox, QStyle.SubControl
        up = self.style().subControlRect(cc, opt, sc.SC_SpinBoxUp, self)
        down = self.style().subControlRect(cc, opt, sc.SC_SpinBoxDown, self)
        if up.isEmpty() or down.isEmpty():  # fallback: right-hand strip, upper half up / lower half down
            if pos.x() < self.width() - self.ARROW_WIDTH:
                return 0
            return 1 if pos.y() < self.height() / 2 else -1
        if up.top() == down.top():  # buttons side by side: accept the full height of each
            up = up.adjusted(0, -up.top(), 0, self.height() - up.bottom())
            down = down.adjusted(0, -down.top(), 0, self.height() - down.bottom())
        return 1 if up.contains(pos) else (-1 if down.contains(pos) else 0)

    def _handle_arrow_press(self, local_pos):
        step = self._arrow_step(local_pos) if self.isEnabled() else 0
        if step:
            self.stepUp() if step > 0 else self.stepDown()
        return bool(step)

    def eventFilter(self, obj, event):
        if (obj is self.lineEdit() and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick)
                and event.button() == Qt.MouseButton.LeftButton
                and self._handle_arrow_press(obj.mapTo(self, event.position().toPoint()))):
            return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._handle_arrow_press(event.position().toPoint()):
            event.accept()
            return
        super().mousePressEvent(event)


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class _CompactTextBrowser(QTextBrowser):
    """QTextBrowser whose initial sizeHint leaves room for the pipeline strip inside 860x680."""

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(140)
        return hint


class _CompactTableWidget(QTableWidget):
    """QTableWidget whose initial sizeHint avoids triggering an outer scroll bar at 860x680."""

    def sizeHint(self):
        hint = super().sizeHint()
        hint.setHeight(115)
        return hint


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
        steps_layout.setSpacing(5)
        test_row = QHBoxLayout()
        test_row.setSpacing(4)
        self.combo_mult_combo = QComboBox()
        self.combo_mult_combo.addItems([f"{i}x" for i in range(1, 13)])
        self.sniper_mult_combo = QComboBox()
        self.sniper_mult_combo.addItems([f"{v:.1f}x" for v in SNIPER_MULTS])
        self.gladiator_spin, self.status_types_spin = ClickableSpinBox(), ClickableSpinBox()
        self.gladiator_spin.setRange(0, 6)
        self.status_types_spin.setRange(0, 10)
        self.on_kill_check = QCheckBox("갈바나이즈드 풀스택")
        self.reset_test_btn = QPushButton("초기화")
        self.reset_test_btn.setStyleSheet(BREAKDOWN_BUTTON_STYLE)
        self.combo_label = QLabel("연속기")
        self.sniper_label = QLabel("저격총")
        self.gladiator_label = QLabel("글래디에이터")
        self.status_types_label = QLabel("상태이상 종류")
        for label, widget in ((self.combo_label, self.combo_mult_combo), (self.sniper_label, self.sniper_mult_combo),
                              (self.gladiator_label, self.gladiator_spin), (self.status_types_label, self.status_types_spin)):
            test_row.addWidget(label)
            test_row.addWidget(widget)
        test_row.addWidget(self.on_kill_check)
        test_row.addWidget(self.reset_test_btn)
        test_row.addStretch(1)
        steps_layout.addLayout(test_row)
        self.test_summary_label = QLabel()
        self.test_summary_label.setWordWrap(True)
        self.test_summary_label.setStyleSheet("color: #facc15;")
        steps_layout.addWidget(self.test_summary_label)
        self.combo_mult_combo.currentIndexChanged.connect(self._on_numeric_test_changed)
        self.sniper_mult_combo.currentIndexChanged.connect(self._on_numeric_test_changed)
        self.gladiator_spin.valueChanged.connect(self._on_numeric_test_changed)
        self.status_types_spin.valueChanged.connect(self._on_numeric_test_changed)
        self.on_kill_check.toggled.connect(self._on_numeric_test_changed)
        self.reset_test_btn.clicked.connect(self.reset_numeric_test)
        self._sync_test_controls_visibility()
        self._sync_gladiator_spin()
        self._compute_test()
        self.pipeline_frame = self._build_pipeline_frame()
        steps_layout.addWidget(self.pipeline_frame)
        self.text_browser = _CompactTextBrowser()
        self.text_browser.setMinimumHeight(120)
        self.text_browser.setHtml(self.generate_html_content())
        steps_layout.addWidget(self.text_browser, 3)
        self.table_widget = _CompactTableWidget()
        self.table_widget.setMinimumHeight(105)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.horizontalHeader().setStretchLastSection(True)
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
        self.test_summary_label.setText(self.test_result["summary"])
        self.refresh_dashboard()

    def _sync_test_controls_visibility(self):
        """Show melee combo/Gladiator only on Melee, and sniper multiplier only on Snipers."""
        melee = is_melee_weapon(self.w_meta)
        sniper = is_sniper_weapon(self.w_meta)
        for widget in (self.combo_label, self.combo_mult_combo, self.gladiator_label, self.gladiator_spin):
            widget.setVisible(melee)
        for widget in (self.sniper_label, self.sniper_mult_combo):
            widget.setVisible(sniper)
        if not melee and self.combo_mult_combo.currentIndex() != 0:
            self.combo_mult_combo.blockSignals(True)
            self.combo_mult_combo.setCurrentIndex(0)
            self.combo_mult_combo.blockSignals(False)
        if not sniper and self.sniper_mult_combo.currentIndex() != 0:
            self.sniper_mult_combo.blockSignals(True)
            self.sniper_mult_combo.setCurrentIndex(0)
            self.sniper_mult_combo.blockSignals(False)

    def _sync_gladiator_spin(self):
        """Default the Gladiator spin to the number of equipped Gladiator set mods (Melee only)."""
        count = sum(1 for m in effective_mods(self.mod_objs, self.riven_stats) if is_gladiator_mod(m)) if is_melee_weapon(self.w_meta) else 0
        self.gladiator_spin.blockSignals(True)
        self.gladiator_spin.setValue(min(6, count))
        self.gladiator_spin.blockSignals(False)

    def _compute_test(self):
        self.test_result = compute_numeric_test(
            self.w_meta, self.mod_objs, self.metrics, self.riven_stats,
            combo_mult=self.combo_mult_combo.currentIndex() + 1,
            sniper_mult=SNIPER_MULTS[max(0, self.sniper_mult_combo.currentIndex())],
            gladiator_stacks=self.gladiator_spin.value(), status_types=self.status_types_spin.value(),
            on_kill_active=self.on_kill_check.isChecked())
        self.pipeline_data = build_pipeline_steps(
            self.w_meta, self.mod_objs, self.metrics, self.riven_stats, self.test_result)
        return self.test_result

    def _build_pipeline_frame(self):
        frame = QFrame()
        frame.setObjectName("pipelineFrame")
        frame.setMinimumWidth(0)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(6, 5, 6, 5)
        outer.setSpacing(4)
        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        self.pipeline_title_label = QLabel("⚡ 배수 파이프라인")
        self.pipeline_title_label.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: bold; border: none;")
        self.pipeline_split_label = QLabel()
        self.pipeline_split_label.setStyleSheet("color: #94a3b8; font-size: 10px; border: none;")
        head.addWidget(self.pipeline_title_label)
        head.addStretch()
        head.addWidget(self.pipeline_split_label)
        outer.addLayout(head)
        self.pipeline_cards_layout = QHBoxLayout()
        self.pipeline_cards_layout.setContentsMargins(0, 0, 0, 0)
        self.pipeline_cards_layout.setSpacing(2)
        outer.addLayout(self.pipeline_cards_layout)
        self.pipeline_cards = []
        return frame

    def update_pipeline(self):
        data = getattr(self, "pipeline_data", None)
        if not data:
            data = build_pipeline_steps(self.w_meta, self.mod_objs, self.metrics, self.riven_stats, getattr(self, "test_result", None))
            self.pipeline_data = data
        self.pipeline_title_label.setText(
            "⚔️ 배수 파이프라인 (근접 무기)" if data["is_melee"] else "⚡ 배수 파이프라인 (원거리 무기)")
        status_dps = data["status_dps"]
        if status_dps > 0:
            self.pipeline_split_label.setText(
                f"직접 {data['direct_burst_dps']:,.0f} + 상태이상 DoT {status_dps:,.0f} = 버스트 {data['burst_dps']:,.0f} DPS")
            self.pipeline_split_label.setStyleSheet("color: #ff4d6d; font-size: 10px; font-weight: bold; border: none;")
        else:
            self.pipeline_split_label.setText(f"직접 타격 기준 · 기대 {data['expected_dps']:,.0f} / 버스트 {data['burst_dps']:,.0f} DPS")
            self.pipeline_split_label.setStyleSheet("color: #94a3b8; font-size: 10px; border: none;")

        _clear_layout(self.pipeline_cards_layout)
        self.pipeline_cards = []
        stretches = {"base": 8, "damage": 10, "elemental": 9, "crit": 11, "speed_ms": 10, "status": 11, "result": 13}
        for idx, step in enumerate(data["steps"]):
            if idx > 0:
                op_text = step["operator"] or "→"
                op_color = "#ff4d6d" if op_text == "+" else "#00e5ff"
                arrow = QLabel(op_text)
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setFixedWidth(12)
                arrow.setStyleSheet(f"color: {op_color}; font-size: 12px; font-weight: bold; border: none; padding: 0px;")
                arrow.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
                self.pipeline_cards_layout.addWidget(arrow)

            accent = step["accent"]
            card = QFrame()
            card.setObjectName("pipelineCard")
            card.setProperty("stepKey", step["key"])
            card.setMinimumWidth(0)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            card.setStyleSheet(
                f"QFrame#pipelineCard {{ background-color: #142336; border: 1px solid #243b55; "
                f"border-top: 2px solid {accent}; border-radius: 6px; }}")
            card.setToolTip(step["tooltip"])

            box = QVBoxLayout(card)
            box.setContentsMargins(4, 4, 4, 4)
            box.setSpacing(2)

            stage_lbl = QLabel(step["title"])
            stage_lbl.setObjectName("pipelineStage")
            stage_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            stage_lbl.setWordWrap(True)
            stage_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
            stage_lbl.setStyleSheet("color: #cbd5e1; font-size: 9px; font-weight: bold; border: none;")
            box.addWidget(stage_lbl)

            badge_lbl = QLabel(step["badge"])
            badge_lbl.setObjectName("pipelineBadge")
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            badge_lbl.setStyleSheet(
                f"color: {accent}; background-color: #0a1019; border: 1px solid {accent}; "
                f"border-radius: 8px; padding: 1px 3px; font-size: 10px; font-weight: bold;")
            box.addWidget(badge_lbl)

            if step["key"] == "result":
                exp_lbl = QLabel(f"기대 {step['expected_dps']:,.0f}")
                exp_lbl.setObjectName("pipelineValue")
                exp_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                exp_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                exp_lbl.setStyleSheet("color: #00e5ff; font-size: 10px; font-weight: bold; border: none;")
                burst_lbl = QLabel(f"버스트 {step['burst_dps']:,.0f}")
                burst_lbl.setObjectName("pipelineSubValue")
                burst_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                burst_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                burst_lbl.setStyleSheet("color: #ffd700; font-size: 10px; font-weight: bold; border: none;")
                box.addWidget(exp_lbl)
                box.addWidget(burst_lbl)
            else:
                val_lbl = QLabel(step["value_text"])
                val_lbl.setObjectName("pipelineValue")
                val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                val_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
                val_lbl.setStyleSheet("color: #f8fafc; font-size: 11px; font-weight: bold; border: none;")
                sub_lbl = QLabel(step["sub_text"])
                sub_lbl.setObjectName("pipelineSub")
                sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sub_lbl.setWordWrap(True)
                sub_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
                sub_lbl.setStyleSheet("color: #94a3b8; font-size: 9px; border: none;")
                box.addWidget(val_lbl)
                box.addWidget(sub_lbl)

            self.pipeline_cards_layout.addWidget(card, stretches.get(step["key"], 10))
            self.pipeline_cards.append(card)

    def _display_metrics(self):
        test = getattr(self, "test_result", None)
        return test["metrics"] if test and test["is_test_active"] else (self.metrics or {})

    def _on_numeric_test_changed(self, *_):
        self.test_summary_label.setText(self._compute_test()["summary"])
        self.text_browser.setHtml(self.generate_html_content())
        self.populate_table()
        self.refresh_dashboard()

    def reset_numeric_test(self):
        controls = (self.combo_mult_combo, self.sniper_mult_combo, self.status_types_spin, self.on_kill_check)
        for w in controls:
            w.blockSignals(True)
        self.combo_mult_combo.setCurrentIndex(0)
        self.sniper_mult_combo.setCurrentIndex(0)
        self.status_types_spin.setValue(0)
        self.on_kill_check.setChecked(False)
        for w in controls:
            w.blockSignals(False)
        self._sync_test_controls_visibility()
        self._sync_gladiator_spin()
        self._on_numeric_test_changed()

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
        self.heat_check = QCheckBox(f"화염 방깎 -{HEAT_STRIP * 100:.0f}%")
        self.arcane_check = QCheckBox(f"아케인 풀스택 +{ARCANE_DAMAGE_BONUS * 100:.0f}%")
        for i, check in enumerate((self.headshot_check, self.viral_check, self.corrosive_check, self.heat_check, self.arcane_check)):
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
        metrics = self._display_metrics()
        values = {"expected_dps": metrics.get("sustained_dps"), "burst_dps": metrics.get("burst_dps"),
                  "peak": metrics.get("max_crit_hit"), "trough": metrics.get("min_hit")}
        for key, lbl in self.kpi_labels.items():
            val = values[key]
            lbl.setText(f"{float(val):,.0f}" if isinstance(val, (int, float)) else "-")
        self.update_pipeline()
        self.populate_visuals()
        self.update_simulation()

    def update_simulation(self, *_):
        metrics, test = self._display_metrics(), getattr(self, "test_result", None) or {}
        base_dps = metrics.get("sustained_dps") or metrics.get("burst_dps") or 0.0
        mods = prepared_effective_mods(self.w_meta, self.mod_objs, self.riven_stats)
        target = SIM_TARGETS[max(0, self.target_combo.currentIndex())]
        is_melee = is_melee_weapon(self.w_meta)
        # Avoid diluting arcane scaling with stacked CO/GunCO when numeric test is OFF.
        if test.get("is_test_active"):
            bonus = test["damage_bonus_total"]
        elif isinstance(metrics.get("effective_mod_dmg"), (int, float)):
            bonus = float(metrics["effective_mod_dmg"])
        else:
            bonus = sum(float(m.get("damage") or m.get("base_damage") or 0.0) for m in mods)

        hs_display = _resolve_headshot_mult(metrics, is_melee=is_melee)
        self.headshot_check.setText(f"헤드샷 x{hs_display:.2f}" if abs(hs_display - round(hs_display)) > 1e-3 else f"헤드샷 x{hs_display:g}")
        self.arcane_check.setText(
            "아케인 풀스택 (원거리 전용)" if is_melee else f"아케인 풀스택 +{ARCANE_DAMAGE_BONUS * 100:.0f}%"
        )

        sim = simulate_combat(
            base_dps,
            target,
            headshot=self.headshot_check.isChecked(),
            viral=self.viral_check.isChecked(),
            corrosive=self.corrosive_check.isChecked(),
            heat=self.heat_check.isChecked(),
            arcane=self.arcane_check.isChecked(),
            damage_bonus=bonus,
            metrics=metrics,
            is_melee=is_melee,
        )
        sim["damage_bonus"] = bonus
        self.last_simulation = sim
        self.sim_dps_label.setText(f"실효 DPS: {sim['effective_dps']:,.0f}")
        ttk = sim["ttk"]
        self.sim_ttk_label.setText("처치 소요 시간(TTK): ∞ (피해 불가)" if math.isinf(ttk) else f"처치 소요 시간(TTK): {ttk:,.2f}초")
        slash_note = f" (출혈 트루 {sim['slash_effective_dps']:,.0f} 포함)" if sim.get("slash_effective_dps", 0.0) > 0 else ""
        self.sim_detail_label.setText(
            f"방어력 {sim['armor']:,.0f} → 피해 감쇄 {sim['damage_reduction'] * 100:.1f}% · "
            f"체력 {sim['health']:,.0f} · 상황 배수 x{sim['multiplier']:.2f} · 기준 DPS {float(base_dps):,.0f}{slash_note}")

    def populate_visuals(self):
        _clear_layout(self.mod_grid)
        _clear_layout(self.badge_layout)
        mods = prepared_effective_mods(self.w_meta, self.mod_objs, self.riven_stats)
        totals = stat_totals(mods)
        base_cc, base_cd = self._crit_base()
        metrics = self.metrics or {}
        base_dps = float(metrics.get("sustained_dps") or metrics.get("burst_dps") or 0.0)
        is_melee = is_melee_weapon(self.w_meta)
        lock_ms = bool(metrics.get("lock_multishot")) or any(_mod_locks_multishot(m) for m in mods)
        axes, labels = (MELEE_RADAR_AXES, MELEE_STAT_LABELS) if is_melee else (RADAR_AXES, STAT_LABELS)

        cells = [None] * 8
        loose = []
        for m in mods:
            if m.get("name") == "Innate Trait":
                continue
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
                share = mod_dps_share(m, totals, base_cc, base_cd, is_melee)
                name = QLabel(m.get("kr_name") or m.get("name") or "?")
                name.setWordWrap(True)
                name.setStyleSheet("color: #facc15; font-weight: bold; border: none;")
                pct = QLabel(f"{share * 100:+.1f}%")
                pct.setStyleSheet("color: #00e5ff; border: none;")
                box.addWidget(name)
                box.addWidget(pct)
                opts = [f"{labels[k]} {mod_stat(m, k) * 100:+.0f}%" for k in ALL_SHARE_KEYS
                        if mod_stat(m, k) and not (is_melee and k == "multishot")]
                if _mod_locks_multishot(m):
                    opts.append("멀티샷 고정")
                card.setToolTip("\n".join([m.get("kr_name") or m.get("name") or "?"] + (opts or ["유틸리티 (DPS 옵션 없음)"])
                                          + [f"단독 DPS 기여도: {share * 100:+.1f}% (≈ {base_dps * share:,.0f} DPS)"]))
                self.mod_cards.append(card)
            self.mod_grid.addWidget(card, idx // 4, idx % 4)

        self.radar_values = [min(1.0, max(0.0, totals[k] / cap)) for k, _, cap in axes]
        self.radar_chart.set_values(self.radar_values, [label for _, label, _ in axes])

        self.weakness_badges = []
        issues = diagnose_weaknesses(totals, base_cc, is_melee=is_melee, lock_multishot=lock_ms) if mods else []
        for text in issues or ["오디스 진단: 배수 버킷 밸런스 양호" if mods else "오디스 진단: 장착 모드 데이터 없음"]:
            badge = QLabel(("⚠ " if issues else "✔ ") + text)
            badge.setObjectName("weaknessBadge")
            badge.setProperty("ok", not issues)
            badge.setWordWrap(True)
            self.badge_layout.addWidget(badge)
            self.weakness_badges.append(badge)

    def generate_html_content(self):
        text = getattr(self, 'breakdown_text', '') or ''
        test = getattr(self, 'test_result', None)
        test_lines = test['breakdown_text'].split('\n') if test and test.get('is_test_active') and test.get('breakdown_text') else []
        pipeline = getattr(self, 'pipeline_data', None) or build_pipeline_steps(
            self.w_meta, self.mod_objs, self.metrics, self.riven_stats, test)
        has_build = bool(self.w_meta or self.mod_objs or self.metrics)
        if not text and not test_lines and not has_build:
            return """
            <html>
            <head>
                <style>
                    body { background-color: #0a1019; color: #ffd700; }
                </style>
            </head>
            <body>
                <h1>No Damage Breakdown Available</h1>
            </body>
            </html>
            """

        esc = html.escape

        def hl(s):  # colour every +XX% green and -XX% crimson
            def _color(match):
                token = match.group(1)
                color = "#ff4d6d" if token.startswith("-") else "#4ade80"
                return f"<span style='color:{color}; font-weight:bold;'>{token}</span>"
            return re.sub(r"([+\-]\d[\d,.]*%)", _color, esc(s))

        out = ["<html><head><style>"
               "body { background-color: #0a1019; color: #e2e8f0; }"
               "h3 { color: #ffd700; margin: 2px 0 6px 0; }"
               ".section-header { color: #ffd700; font-weight: bold; font-size: 13px; margin: 10px 0 4px 0; }"
               ".lbl { color: #94a3b8; font-size: 11px; }"
               ".val { color: #00e5ff; font-weight: bold; font-size: 13px; }"
               ".mod { color: #ffd700; font-weight: bold; }"
               ".result { color: #ffd700; font-weight: bold; font-size: 13px; }"
               ".bullet-item { color: #fde68a; margin: 2px 0; }"
               ".total-highlight { background-color: #ffd700; color: #0a1019; font-weight: bold; padding: 4px; }"
               "</style></head><body><h3>Damage Calculation Breakdown</h3>"]
        if test_lines:  # active test results sit on top so they are visible without scrolling
            rows = "".join(f"<p class='bullet-item'>{hl(line)}</p>" for line in test_lines[1:])
            out.append("<table width='100%' cellspacing='0' cellpadding='8' border='1' bgcolor='#142336' style='border-color:#ffd700;'>"
                       f"<tr><td><p style='color:#ffd700; font-weight:bold; font-size:13px; margin:0 0 4px 0;'>{esc(test_lines[0])}</p>{rows}</td></tr></table>")

        if not text and has_build:
            pipe_cells = "".join(
                f"<td bgcolor='#142336' align='center' style='border:1px solid {s['accent']};'>"
                f"<span style='color:#94a3b8; font-size:10px;'>{esc(s['title'])}</span><br/>"
                f"<span style='color:{s['accent']}; font-weight:bold;'>{esc(s['badge'])}</span><br/>"
                f"<span style='color:#f8fafc; font-weight:bold;'>{esc(s['value_text'])}</span></td>"
                for s in pipeline["steps"]
            )
            out.append("<p class='section-header'>배수 파이프라인 요약</p>"
                       f"<table width='100%' cellspacing='4' cellpadding='6' bgcolor='#0a1019'><tr>{pipe_cells}</tr></table>")

        stats, section = [], 0

        def flush_stats():  # Section 1: compact 3-column dark stat cards
            cells = [f"<td bgcolor='#142336'><span class='lbl'>{esc(k)}</span><br/><span class='val'>{esc(v)}</span></td>" for k, v in stats]
            if cells:
                out.append("<table width='100%' cellspacing='4' cellpadding='5'>"
                           + "".join("<tr>" + "".join(cells[i:i + 3]) + "</tr>" for i in range(0, len(cells), 3)) + "</table>")
            stats.clear()

        for line in (line.strip() for line in text.split('\n')):
            if section == 1 and line.startswith('- ') and ': ' in line:
                stats.append(line[2:].split(': ', 1))
                continue
            flush_stats()
            if not line:
                continue
            if re.match(r"[1-7]\.", line):
                section = int(line[0])
                out.append(f"<p class='section-header'>{esc(line)}</p>")
            elif line.startswith('↳'):
                out.append("<table width='100%' cellspacing='2' cellpadding='6'><tr>"
                           "<td width='4' bgcolor='#00d2ff'>&nbsp;</td>"
                           f"<td bgcolor='#142336' style='color:#00e5ff; font-weight:bold;'>{hl(line)}</td></tr></table>")
            elif line.startswith('- ') and ': ' in line:
                name, vals = line[2:].split(': ', 1)
                out.append(f"<p style='margin: 2px 0 2px 8px;'><span class='mod'>{esc(name)}</span> <span style='color:#cbd5e1;'>{hl(vals)}</span></p>")
            elif line[0] in '①②③④⑤⑥⑦':  # Section 3: step cards with a cyan left accent
                left, sep, right = line.rpartition(' = ')
                body = f"{hl(left)} = <span class='result'>{esc(right)}</span>" if sep else hl(line)
                accent_bar = "#b388ff" if line[0] in '⑥⑦' else "#00d2ff"
                out.append(f"<table width='100%' cellspacing='2' cellpadding='6'><tr><td width='4' bgcolor='{accent_bar}'>&nbsp;</td>"
                           f"<td bgcolor='#142336'>{body}</td></tr></table>")
            elif line.startswith('•'):
                out.append(f"<p class='bullet-item'>{hl(line)}</p>")
            elif line.startswith('Total:'):
                out.append(f"<p class='total-highlight'>{esc(line)}</p>")
            else:
                out.append(f"<p>{hl(line)}</p>")
        flush_stats()

        if pipeline["status_dps"] > 0 or pipeline["status_entries"]:
            sb_parts = " · ".join(
                f"<span style='color:#b388ff; font-weight:bold;'>{esc(lbl)}</span> "
                f"<span style='color:#ff4d6d; font-weight:bold;'>{val:,.1f}</span>"
                for lbl, val in pipeline["status_entries"]
            ) or f"<span style='color:#ff4d6d; font-weight:bold;'>+{pipeline['status_dps']:,.1f} DPS</span>"
            out.append("<table width='100%' cellspacing='2' cellpadding='6'><tr>"
                       "<td width='4' bgcolor='#ff4d6d'>&nbsp;</td>"
                       "<td bgcolor='#142336'>"
                       "<span style='color:#ff4d6d; font-weight:bold;'>상태이상 DoT 파이프라인</span> · "
                       f"<span style='color:#00e5ff;'>직접 버스트 {pipeline['direct_burst_dps']:,.0f}</span> + "
                       f"<span style='color:#ff4d6d; font-weight:bold;'>상태이상 DoT {pipeline['status_dps']:,.0f}</span> = "
                       f"<span style='color:#ffd700; font-weight:bold;'>{pipeline['burst_dps']:,.0f} DPS</span><br/>"
                       f"<span style='color:#cbd5e1; font-size:11px;'>세부 기여: {sb_parts}</span>"
                       "</td></tr></table>")

        out.append("</body></html>")
        return "".join(out)

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
        test = getattr(self, 'test_result', None) or {}

        prepared_mods = _ENGINE_HELPER._prepare_mods(self.w_meta, list(self.mod_objs or [])) if self.w_meta else list(self.mod_objs or [])
        lock_ms = bool((self.metrics or {}).get("lock_multishot")) or any(_mod_locks_multishot(m) for m in prepared_mods)
        for m in prepared_mods:
            # The riven's values get their own row below; this is only its slot marker.
            if (self.riven_stats and m.get('name') == 'Riven Mod') or m.get('name') == 'Innate Trait':
                continue
            mod_name = m.get('kr_name') or m.get('name')
            extra, cond_notes = conditional_effects(m, test)
            damage = float(m.get('damage') or m.get('base_damage') or 0.0) + extra['damage']
            multishot = 0.0 if lock_ms else (float(m.get('multishot') or 0.0) + extra['multishot'])
            elemental_damage = float(m.get('elemental_damage') or 0.0) + extra['elemental_damage']
            crit_chance = float(m.get('crit_chance') or 0.0) + extra['crit_chance']
            crit_damage = float(m.get('crit_damage') or 0.0) + extra['crit_damage']
            fire_rate = float(m.get('fire_rate') or 0.0) + extra['fire_rate']

            total_damage += damage
            total_multishot += multishot
            total_elemental_damage += elemental_damage
            total_crit_chance += crit_chance
            total_crit_damage += crit_damage
            total_fire_rate += fire_rate

            is_zero = not any([damage, multishot, elemental_damage, crit_chance, crit_damage, fire_rate])
            note = "[스탠스]" if "stance" in str(m.get("type", "")).lower() else ("[유틸리티]" if is_zero else "-")
            if cond_notes:
                note = " / ".join(cond_notes)

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

        glad_cc = test.get('glad_cc_bonus', 0.0) if test.get('is_test_active') else 0.0
        if glad_cc:
            total_crit_chance += glad_cc
            data.append(["글래디에이터 세트", "-", "-", "-", percent(glad_cc), "-", "-",
                         f"{test['gladiator_stacks']}세트 × 10% × 연속기 {test['combo_mult'] - 1:g}"])

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
        last_row = len(data) - 1
        for row, row_data in enumerate(data):
            is_summary = (row == last_row)
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter if col == 7 else Qt.AlignmentFlag.AlignCenter)
                if is_summary:
                    item.setBackground(QColor("#142336"))
                    item.setForeground(QColor("#ffd700"))
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                else:
                    if value != "0" and value != "-":
                        item.setBackground(QColor("#142336"))
                    if col == 0:
                        color = "#b388ff" if value == "Riven" else ("#ffd700" if value == "글래디에이터 세트" else "#e2e8f0")
                        item.setForeground(QColor(color))
                    elif value == "-":
                        item.setForeground(QColor("#64748b"))
                    elif isinstance(value, str) and value.startswith("-"):
                        item.setForeground(QColor("#ff4d6d"))
                    elif isinstance(value, str) and value.startswith("+"):
                        item.setForeground(QColor("#4ade80"))
                    elif col == 7:
                        item.setForeground(QColor("#94a3b8" if value in ("-", "[유틸리티]", "[스탠스]") else "#b388ff"))
                self.table_widget.setItem(row, col, item)
        for col in range(7):
            self.table_widget.resizeColumnToContents(col)

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

        self._sync_test_controls_visibility()
        self._sync_gladiator_spin()
        self._on_numeric_test_changed()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = DamageBreakdownDialog()
    dialog.show()
    sys.exit(app.exec())
