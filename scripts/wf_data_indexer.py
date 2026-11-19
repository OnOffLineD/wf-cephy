import os
import json
from typing import Dict, Any, Optional, List, Tuple
import re
from scripts.path_config import get_path
from scripts.innate_traits import get_incarnon_data

WEAPON_TYPE_OVERRIDES: Dict[str, str] = {
    'coda bubonico': 'Shotgun',
    'perigale prime': 'Sniper',
    'mutalist cernos': 'Bow',
    'sancti castanas': 'Throwing',
}

EXALTED_CLASSIFICATION: Dict[str, Tuple[str, str]] = {
    'artemis bow': ('Primary', 'Bow'),
    'artemis bow prime': ('Primary', 'Bow'),
    'neutralizer': ('Primary', 'Sniper'),
    'dex pixia': ('Secondary', 'Pistol'),
    'dex pixia prime': ('Secondary', 'Pistol'),
    'regulators': ('Secondary', 'Pistol'),
    'regulators prime': ('Secondary', 'Pistol'),
    'noctua': ('Secondary', 'Pistol'),
    'glory': ('Secondary', 'Pistol'),
    'arquebex': ('Arch-Gun', 'Arch-Gun'),
    'ironbride': ('Arch-Melee', 'Arch-Melee'),
}

_KO_DAMAGE_TO_EN: Dict[str, str] = {
    '충격': 'impact', '관통': 'puncture', '베기': 'slash',
    '화염': 'heat', '냉기': 'cold', '전기': 'electricity', '독성': 'toxin',
    '폭발': 'blast', '방사능': 'radiation', '가스': 'gas', '자성': 'magnetic',
    '바이러스': 'viral', '부식': 'corrosive', '보이드': 'void', '타우': 'tau',
}

_KO_TRIGGER_TO_EN: Dict[str, str] = {
    '자동': 'Auto', '반자동': 'Semi', '충전형': 'Charge',
    '지속형': 'Held', '점사': 'Burst', '액티브': 'Active',
}

_ADVERSARY_HEADER_RE = re.compile(
    r'(?:(?:dual|듀얼)\s+)?(?:쿠바|테넷|코다|(?:kuva|tenet|coda)\b)',
    re.IGNORECASE,
)


def _norm_damage_dict(dmg: Optional[Dict[str, Any]]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, v in (dmg or {}).items():
        if not v:
            continue
        nk = 'electric' if str(k).lower() == 'electricity' else str(k).lower()
        out[nk] = out.get(nk, 0.0) + float(v)
    return out


def _is_aoe_attack(attack: Dict[str, Any]) -> bool:
    name_l = str(attack.get('name', '')).lower()
    return (
        str(attack.get('shot_type', '')).lower() == 'aoe'
        or 'radial' in name_l
        or 'explosion' in name_l
        or 'detonation' in name_l
        or 'aoe' in name_l
        or 'cloud' in name_l
    )


def _split_normal_and_incarnon_attacks(attacks: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Split attacks into (normal_attacks, incarnon_attacks), keeping trailing unlabeled Incarnon AoE (e.g. Laetum)."""
    normal: List[Dict[str, Any]] = []
    incarnon: List[Dict[str, Any]] = []
    seen_incarnon = False
    for atk in attacks:
        name_l = str(atk.get('name', '')).lower()
        if 'incarnon' in name_l:
            seen_incarnon = True
            incarnon.append(atk)
        elif seen_incarnon and _is_aoe_attack(atk) and 'slam' not in name_l:
            # Unlabeled AoE right after an Incarnon attack (e.g. Laetum 'Auto Radial Attack').
            incarnon.append(atk)
        else:
            normal.append(atk)
    return normal, incarnon


def _make_mode_entry(
    primary: Dict[str, Any],
    radial: Optional[Dict[str, Any]],
    fallback_cc: float,
    fallback_cm: float,
    fallback_sc: float,
    fallback_fr: float,
    multishot: float,
    is_beam: bool,
) -> Dict[str, Any]:
    dmg_types = _norm_damage_dict(primary.get('damage'))
    rad_types = _norm_damage_dict(radial.get('damage')) if radial else {}
    raw_cc = primary.get('crit_chance')
    cc = (float(raw_cc) / 100.0 if float(raw_cc) > 1.0 else float(raw_cc)) if raw_cc is not None else fallback_cc
    raw_sc = primary.get('status_chance')
    sc = (float(raw_sc) / 100.0 if float(raw_sc) > 1.0 else float(raw_sc)) if raw_sc is not None else fallback_sc
    cm = float(primary.get('crit_mult') or fallback_cm)
    chg = float(primary.get('charge_time') or 0.0)
    fr = float(primary.get('speed') or 0.0)
    if fr <= 0.0:
        fr = (1.0 / chg) if chg > 0.0 else fallback_fr
    return {
        'name': str(primary.get('name') or ''),
        'damage': sum(dmg_types.values()),
        'damage_types': dmg_types,
        'radial_damage': sum(rad_types.values()),
        'radial_damage_types': rad_types,
        'crit_chance': cc,
        'crit_mult': cm,
        'status_chance': sc,
        'multishot': float(multishot),
        'fire_rate': fr,
        'charge_time': chg,
        'is_beam': bool(is_beam),
    }


class WFDataIndexer:
    def __init__(self, data_dir='data/raw_wfcd'):
        self.data_dir = get_path(data_dir) if not os.path.isabs(data_dir) else data_dir
        self.weapons_index = {}
        self.mods_index = {}
        self._catalog_omega: Dict[str, float] = {}
        self.load_data()

    def _register_weapon_keys(self, metadata: Dict[str, Any], en_name: str, kr_name: str = '') -> None:
        name = en_name.lower()
        if kr_name:
            metadata['kr_name'] = kr_name
            self.weapons_index[kr_name.lower()] = metadata
            self.weapons_index[kr_name.lower().replace(' ', '')] = metadata
            self.weapons_index[kr_name.lower().replace('-', '').replace(' ', '')] = metadata
            self.weapons_index[kr_name.lower().replace('-', ' ')] = metadata

        self.weapons_index[name] = metadata
        self.weapons_index[name.replace(' ', '')] = metadata
        self.weapons_index[name.replace('-', '').replace(' ', '')] = metadata
        self.weapons_index[name.replace('-', ' ')] = metadata

    def load_data(self):
            ko_path = os.path.join(self.data_dir, 'ko.json')
            self.ko_dict = {}
            if os.path.exists(ko_path):
                try:
                    with open(ko_path, 'r', encoding='utf-8') as f:
                        self.ko_dict = json.load(f)
                except Exception:
                    pass

            # Load game_catalog.json once for optional omega_attenuation overrides & Exalted weapon hydration.
            catalog_entries: List[Dict[str, Any]] = []
            default_raw_dir = get_path('data/raw_wfcd')
            catalog_candidates = [os.path.join(os.path.dirname(self.data_dir), 'game_catalog.json')]
            if os.path.normcase(os.path.abspath(self.data_dir)) == os.path.normcase(os.path.abspath(default_raw_dir)):
                catalog_candidates.append(get_path('data', 'game_catalog.json'))
            for cat_path in catalog_candidates:
                if os.path.exists(cat_path):
                    try:
                        with open(cat_path, 'r', encoding='utf-8') as f:
                            catalog_entries = json.load(f).get('entries', [])
                        break
                    except Exception:
                        pass
            self._catalog_omega = {}
            for entry in catalog_entries:
                if entry.get('kind') == 'weapon' and entry.get('en'):
                    omega = entry.get('omega_attenuation') or entry.get('omegaAttenuation')
                    if omega:
                        self._catalog_omega[str(entry['en']).lower()] = float(omega)

            files = ['Primary.json', 'Secondary.json', 'Melee.json', 'Arch-Gun.json', 'Arch-Melee.json', 'Warframes.json', 'Mods.json']
            for file in files:
                file_path = os.path.join(self.data_dir, file)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if file == 'Mods.json':
                            self.index_mods(data, is_arcane=False)
                        elif file == 'Warframes.json':
                            self.index_warframes(data)
                        else:
                            self.index_weapons(data)

            # Prefer curated data/weapon_arcanes.json when running on default data_dir; fallback to data_dir copy.
            arcane_paths = []
            if os.path.normcase(os.path.abspath(self.data_dir)) == os.path.normcase(os.path.abspath(default_raw_dir)):
                arcane_paths.append(get_path('data', 'weapon_arcanes.json'))
            arcane_paths.append(os.path.join(self.data_dir, 'weapon_arcanes.json'))
            for apath in arcane_paths:
                if os.path.exists(apath):
                    with open(apath, 'r', encoding='utf-8') as f:
                        self.index_mods(json.load(f), is_arcane=True)
                    break

            if catalog_entries:
                self.index_exalted_weapons(catalog_entries)

            mod_ocr_aliases_path = os.path.join(self.data_dir, 'mod_ocr_aliases.json')
            self.mod_ocr_aliases = {}
            if os.path.exists(mod_ocr_aliases_path):
                try:
                    with open(mod_ocr_aliases_path, 'r', encoding='utf-8') as f:
                        self.mod_ocr_aliases = json.load(f).get('exact_typos', {})
                except Exception:
                    pass

    def _build_attack_modes(
        self,
        metadata: Dict[str, Any],
        normal_attacks: List[Dict[str, Any]],
        incarnon_attacks: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        modes: Dict[str, Dict[str, Any]] = {}
        base_cc = float(metadata.get('crit_chance') or 0.0)
        base_cm = float(metadata.get('crit_mult') or 1.5)
        base_sc = float(metadata.get('status_chance') or 0.0)
        base_fr = float(metadata.get('fire_rate') or 1.0)
        base_ms = float(metadata.get('base_multishot') or 1.0)
        is_beam = bool(metadata.get('is_beam', False))
        is_melee = metadata.get('category') == 'Melee'

        # Pair non-AoE attacks with immediately following AoE attacks of the same firing mode.
        def _pair_at(seq: List[Dict[str, Any]], idx: int) -> Optional[Dict[str, Any]]:
            if idx + 1 < len(seq) and _is_aoe_attack(seq[idx + 1]):
                a_name = str(seq[idx].get('name', '')).lower()
                b_name = str(seq[idx + 1].get('name', '')).lower()
                if 'slam' in b_name and 'slam' not in a_name:
                    return None
                return seq[idx + 1]
            return None

        ordered_normal = [a for a in metadata.get('attacks', []) if a in normal_attacks]
        if ordered_normal:
            primary_atk = ordered_normal[0]
            # Find paired radial attack right after primary_atk in the original normal_attacks order.
            try:
                orig_idx = normal_attacks.index(primary_atk)
            except ValueError:
                orig_idx = -1
            paired_rad = _pair_at(normal_attacks, orig_idx) if orig_idx >= 0 else None
            # For weapons like Kuva Zarr / Bramma / Acceltra, normal_attacks[0] is direct & [1] is radial.
            if paired_rad is None and len(normal_attacks) >= 2 and primary_atk is normal_attacks[0] and _is_aoe_attack(normal_attacks[1]):
                if not is_melee or 'slam' not in str(normal_attacks[1].get('name', '')).lower():
                    paired_rad = normal_attacks[1]
            modes['normal'] = _make_mode_entry(
                primary_atk, paired_rad, base_cc, base_cm, base_sc, base_fr, base_ms, is_beam
            )

        for idx, atk in enumerate(normal_attacks):
            name_l = str(atk.get('name', '')).lower()
            paired = _pair_at(normal_attacks, idx)
            if is_melee and ('charged throw recall explosion' in name_l or ('throw recall explosion' in name_l and 'heavy_throw' not in modes)):
                modes['heavy_throw'] = _make_mode_entry(
                    atk, None, base_cc, base_cm, base_sc, base_fr, 1.0, False
                )
                continue
            if _is_aoe_attack(atk):
                continue
            if 'perfect' in name_l and 'perfect' not in modes:
                modes['perfect'] = _make_mode_entry(atk, paired, base_cc, base_cm, base_sc, base_fr, base_ms, False)
            elif ('charged' in name_l or 'charge' in name_l) and 'uncharged' not in name_l and 'charged' not in modes:
                modes['charged'] = _make_mode_entry(atk, paired, base_cc, base_cm, base_sc, base_fr, base_ms, False)
            elif ('quick' in name_l or 'uncharged' in name_l) and 'quick' not in modes:
                modes['quick'] = _make_mode_entry(atk, paired, base_cc, base_cm, base_sc, base_fr, base_ms, False)
            elif (
                any(k in name_l for k in ('alt-fire', 'alt fire', 'barrage', 'full auto', 'burst', 'plasma bomb', 'glaive', 'grenade', 'ranged', 'spear', 'held', 'lock-on'))
                and atk is not (ordered_normal[0] if ordered_normal else None)
                and 'alt_fire' not in modes
            ):
                alt_beam = 'held' in name_l or 'beam' in name_l
                alt_ms = 1.0 if (alt_beam or paired is not None) else base_ms
                modes['alt_fire'] = _make_mode_entry(atk, paired, base_cc, base_cm, base_sc, base_fr, alt_ms, alt_beam)

        if incarnon_attacks:
            inc_direct = next((a for a in incarnon_attacks if not _is_aoe_attack(a)), incarnon_attacks[0])
            inc_aoe = next((a for a in incarnon_attacks if a is not inc_direct and _is_aoe_attack(a)), None)
            inc_info = get_incarnon_data(metadata.get('name', ''))
            inc_is_beam = bool(inc_info.get('is_beam')) if inc_info else (
                'beam' in str(inc_direct.get('shot_type', '')).lower()
            )
            # Incarnon projectile/beam transformations default to 1.0 base multishot unless shotgun-pellet form.
            inc_ms = 1.0 if (inc_is_beam or inc_aoe is not None or str(inc_direct.get('shot_type', '')).lower() == 'projectile') else base_ms
            modes['incarnon'] = _make_mode_entry(
                inc_direct, inc_aoe, base_cc, base_cm, base_sc, base_fr, inc_ms, inc_is_beam
            )

        return modes

    def index_weapons(self, data: List[Dict[str, Any]]) -> None:
        for weapon in data:
            unique_name = weapon.get('uniqueName', '')
            # Skip duplicate quest Grimoire and PvP Zaw tip stubs.
            if unique_name.endswith('TnDoppelgangerGrimoire') or 'pvpvariant' in unique_name.lower():
                continue

            raw_name = weapon.get('name', '')
            name = raw_name.lower()
            category = weapon.get('category', '')
            w_type = WEAPON_TYPE_OVERRIDES.get(name, weapon.get('type', ''))
            if category == 'Melee' and w_type == 'Rifle':
                w_type = 'Melee'

            trigger = str(weapon.get('trigger') or '')
            raw_cc = weapon.get('criticalChance', weapon.get('critChance', 0)) or 0
            raw_sc = weapon.get('procChance', weapon.get('statusChance', 0)) or 0
            omega_val = self._catalog_omega.get(name) or weapon.get('omegaAttenuation') or 0.0

            metadata: Dict[str, Any] = {
                'name': raw_name,
                'category': category,
                'type': w_type,
                'trigger': trigger,
                'is_beam': trigger.lower() == 'held',
                'disposition': int(weapon.get('disposition') or 0),
                'omega_attenuation': float(omega_val),
                'max_level_cap': int(weapon.get('maxLevelCap') or 30),
                'wind_up': float(weapon.get('windUp') or 0.0),
                'follow_through': float(weapon.get('followThrough') or 0.0),
                'slam_attack': float(weapon.get('slamAttack') or 0.0),
                'heavy_slam_attack': float(weapon.get('heavySlamAttack') or 0.0),
                'combo_duration': float(weapon.get('comboDuration') or 0.0),
                'range': float(weapon.get('range') or 0.0),
                'total_damage': weapon.get('totalDamage', 0) or sum(
                    attack.get('damagePerShot', 0)
                    for attack in weapon.get('attacks', [])
                    if 'incarnon' not in str(attack.get('name', '')).lower()
                ),
                'crit_chance': raw_cc / 100 if raw_cc > 1 else raw_cc,
                'crit_mult': weapon.get('criticalMultiplier', weapon.get('critMultiplier', 0)),
                'fire_rate': weapon.get('fireRate', 0),
                'status_chance': raw_sc / 100 if raw_sc > 1 else raw_sc,
                'magazineSize': weapon.get('magazineSize', 0),
                'reloadTime': weapon.get('reloadTime', 0),
                'base_multishot': float(weapon.get('multishot', 1) or 1),
            }
            # Unmodded heavy attack hit (melee); the engine scales it by the same mods as normal hits.
            if weapon.get('heavyAttackDamage'):
                metadata['heavy_damage'] = float(weapon['heavyAttackDamage'])

            # Look up the official Korean name
            kr_entry = self.ko_dict.get(unique_name, {})
            kr_name = kr_entry.get('name', '') if isinstance(kr_entry, dict) else ''
            self._register_weapon_keys(metadata, raw_name, kr_name)

            # Special aliases
            if name == 'laetum':
                self.weapons_index['라에툼'] = metadata
            if name == 'burston':
                self.weapons_index['버스턴'] = metadata

            # Scan attacks for specific types (including trailing unlabeled Incarnon AoE like Laetum).
            attacks = list(weapon.get('attacks', []))
            normal_attacks, incarnon_attacks = _split_normal_and_incarnon_attacks(attacks)
            first_normal = normal_attacks[0] if normal_attacks else (attacks[0] if attacks else None)

            # Multi-mode weapons leave top-level stats empty (e.g. Dark Split-Sword); copy from first normal attack.
            if not metadata['crit_chance'] and first_normal and first_normal.get('crit_chance'):
                metadata['crit_chance'] = first_normal['crit_chance'] / 100.0
                metadata['crit_mult'] = first_normal.get('crit_mult', metadata['crit_mult'])
                metadata['fire_rate'] = first_normal.get('speed', metadata['fire_rate'])
                metadata['total_damage'] = sum(first_normal.get('damage', {}).values()) or metadata['total_damage']
                if first_normal.get('status_chance'):
                    metadata['status_chance'] = first_normal['status_chance'] / 100.0

            # Align Frankenstein top-level stats (e.g. Nataruk, Epitaph/Prime, Fulmin/Prime, Lanka)
            # where total_damage matches one specific non-AoE mode while top-level CC/CM or attacks[0] belong to another.
            top_dmg = float(metadata['total_damage'] or 0.0)
            if top_dmg > 0.0 and len(normal_attacks) > 1:
                exact_non_aoe = [
                    a for a in normal_attacks
                    if not _is_aoe_attack(a)
                    and sum((a.get('damage') or {}).values()) > 0
                    and abs(sum((a.get('damage') or {}).values()) - top_dmg) <= 0.02 * top_dmg
                ]
                if exact_non_aoe:
                    canonical = next(
                        (a for a in exact_non_aoe if 'perfect' in str(a.get('name', '')).lower()),
                        exact_non_aoe[0],
                    )
                    atk_cc = float(canonical.get('crit_chance') or 0.0) / 100.0
                    atk_cm = float(canonical.get('crit_mult') or 0.0)
                    atk_sc = float(canonical.get('status_chance') or 0.0) / 100.0
                    cc_mismatch = atk_cc > 0 and abs(float(metadata['crit_chance'] or 0.0) - atk_cc) > 0.02
                    cm_mismatch = atk_cm > 0 and abs(float(metadata['crit_mult'] or 0.0) - atk_cm) > 0.05
                    wrong_first = canonical is not normal_attacks[0]
                    if cc_mismatch or cm_mismatch or wrong_first:
                        if atk_cc > 0:
                            metadata['crit_chance'] = atk_cc
                        if atk_cm > 0:
                            metadata['crit_mult'] = atk_cm
                        if atk_sc > 0 and (abs(float(metadata['status_chance'] or 0.0) - atk_sc) > 0.02 or not metadata['status_chance']):
                            metadata['status_chance'] = atk_sc
                        if not metadata['fire_rate'] and canonical.get('speed'):
                            metadata['fire_rate'] = float(canonical['speed'])
                        if wrong_first and canonical in attacks:
                            attacks = [canonical] + [a for a in attacks if a is not canonical]

            # Charge weapons with missing top-level fireRate (e.g. Lanka fireRate=0): fall back to 1 / charge_time.
            if not metadata['fire_rate']:
                charge_src = next((a for a in attacks if a.get('charge_time')), None)
                if charge_src and float(charge_src['charge_time']) > 0:
                    metadata['fire_rate'] = 1.0 / float(charge_src['charge_time'])

            metadata['attacks'] = attacks

            radial_attack = next(
                (attack for attack in normal_attacks if _is_aoe_attack(attack)),
                None,
            )
            incarnon_attack = next(
                (attack for attack in incarnon_attacks if not _is_aoe_attack(attack)),
                next(iter(incarnon_attacks), None),
            )
            incarnon_aoe = next(
                (
                    attack for attack in incarnon_attacks
                    if attack is not incarnon_attack and _is_aoe_attack(attack)
                ),
                None,
            )

            if radial_attack:
                metadata['radial_attack'] = radial_attack
            if incarnon_attack:
                metadata['incarnon_attack'] = incarnon_attack
            if incarnon_aoe:
                metadata['incarnon_aoe'] = incarnon_aoe

            metadata['attack_modes'] = self._build_attack_modes(metadata, normal_attacks, incarnon_attacks)

    def index_exalted_weapons(self, catalog_entries: List[Dict[str, Any]]) -> None:
        """Hydrate Exalted / Special weapons from game_catalog.json (absent from raw_wfcd)."""
        for entry in catalog_entries:
            if entry.get('kind') != 'weapon' or entry.get('category') != '특수 무기':
                continue
            total_dmg = float(entry.get('total_damage') or 0.0)
            en_name = str(entry.get('en') or '').strip()
            if not en_name or total_dmg <= 0.0 or en_name.lower() in self.weapons_index:
                continue

            kr_name = str(entry.get('ko') or '').strip()
            cat, w_type = EXALTED_CLASSIFICATION.get(en_name.lower(), ('Melee', 'Melee'))
            raw_trig = str(entry.get('trigger') or '')
            trigger = _KO_TRIGGER_TO_EN.get(raw_trig, raw_trig)
            is_beam = trigger.lower() == 'held'

            raw_dmg_ko = entry.get('damage') or {}
            en_dmg: Dict[str, float] = {}
            for k_ko, val in raw_dmg_ko.items():
                if val:
                    en_k = _KO_DAMAGE_TO_EN.get(k_ko, str(k_ko).lower())
                    en_dmg[en_k] = en_dmg.get(en_k, 0.0) + float(val)

            cc = float(entry.get('crit_chance') or 0.0)
            cm = float(entry.get('crit_mult') or 2.0)
            sc = float(entry.get('status_chance') or 0.0)
            fr = float(entry.get('fire_rate') or 1.0)
            ms = float(entry.get('multishot') or 1.0)
            mag = int(entry.get('magazine') or 0)
            rld = float(entry.get('reload') or 0.0)

            attack = {
                'name': 'Normal Attack',
                'damage': en_dmg or {'impact': total_dmg},
                'crit_chance': cc * 100.0,
                'crit_mult': cm,
                'status_chance': sc * 100.0,
                'speed': fr,
            }
            metadata: Dict[str, Any] = {
                'name': en_name,
                'category': cat,
                'type': w_type,
                'is_exalted': True,
                'trigger': trigger,
                'is_beam': is_beam,
                'disposition': 0,
                'omega_attenuation': 0.0,
                'max_level_cap': 30,
                'wind_up': 0.0,
                'follow_through': 0.0,
                'slam_attack': 0.0,
                'heavy_slam_attack': 0.0,
                'combo_duration': 0.0,
                'range': float(entry.get('range') or 0.0),
                'total_damage': total_dmg,
                'crit_chance': cc,
                'crit_mult': cm,
                'fire_rate': fr,
                'status_chance': sc,
                'magazineSize': mag,
                'reloadTime': rld,
                'base_multishot': ms,
                'attacks': [attack],
            }
            metadata['attack_modes'] = {
                'normal': _make_mode_entry(attack, None, cc, cm, sc, fr, ms, is_beam)
            }
            self._register_weapon_keys(metadata, en_name, kr_name)

    def index_warframes(self, data: List[Dict[str, Any]]) -> None:
        for wf in data:
            name = wf.get('name', '').lower()
            metadata = {
                'name': wf.get('name', ''),
                'category': 'Warframe',
                'type': 'Warframe',
                'health': wf.get('health', 100),
                'shield': wf.get('shield', 100),
                'armor': wf.get('armor', 100),
                'energy': wf.get('power', 100),
                'sprintSpeed': wf.get('sprintSpeed', 1.0)
            }
            unique_name = wf.get('uniqueName', '')
            kr_entry = self.ko_dict.get(unique_name, {})
            kr_name = kr_entry.get('name', '') if isinstance(kr_entry, dict) else ''
            if kr_name:
                metadata['kr_name'] = kr_name
                self.weapons_index[kr_name.lower()] = metadata
                self.weapons_index[kr_name.lower().replace(' ', '')] = metadata
                self.weapons_index[kr_name.lower().replace('-', '').replace(' ', '')] = metadata
                self.weapons_index[kr_name.lower().replace('-', ' ')] = metadata
            self.weapons_index[name] = metadata
            self.weapons_index[name.replace(' ', '').lower()] = metadata
            self.weapons_index[name.replace('-', '').replace(' ', '').lower()] = metadata
            self.weapons_index[name.replace('-', ' ').lower()] = metadata

    def index_mods(self, data, is_arcane=False):
        NON_ARCANES = {
            'melee elementalist', 'rifle elementalist', 'shotgun elementalist', 'pistol elementalist',
            "dreamer's wrath", "opportunity's reach", "discipline's merit", "master's tenet",
            'semi-rifle cannonade', 'shotgun cannonade', 'pistol cannonade'
        }
        for mod in data:
                name = mod.get('name', '').lower()
                unique_name = mod.get('uniqueName', '')
            
                # Skip fake/flawed entries
                if unique_name.endswith(('Expert', 'Beginner', 'Intermediate')) and not name.startswith('primed '):
                    continue
            
                kr_entry = self.ko_dict.get(unique_name, {})
                kr_name = mod.get('kr_name') or (kr_entry.get('name', '') if isinstance(kr_entry, dict) else '')
        
                type = mod.get('type', '')
                compatName = mod.get('compatName', '')
                fusionLimit = mod.get('fusionLimit', 0)
        
                stats = {
                    'damage': 0.0, 'multishot': 0.0, 'crit_chance': 0.0, 'crit_damage': 0.0, 
                    'fire_rate': 0.0, 'status': 0.0, 'toxin': 0.0, 'cold': 0.0, 'heat': 0.0, 
                    'electric': 0.0, 'viral': 0.0, 'corrosive': 0.0, 'radiation': 0.0, 
                    'magnetic': 0.0, 'blast': 0.0, 'gas': 0.0, 'slash': 0.0, 'impact': 0.0, 
                    'puncture': 0.0, 'elemental_damage': 0.0,
                    'status_damage': 0.0, 'slam_damage': 0.0, 'heavy_damage_bonus': 0.0, 'finisher_damage': 0.0,
                    'wind_up_speed': 0.0, 'initial_combo': 0.0,
                    'weak_point_damage': 0.0, 'headshot_bonus': 0.0,
                    'combo_crit': 0.0, 'combo_status': 0.0, 'status_type_damage': 0.0,
                    'heavy_crit_chance': 0.0, 'weak_point_crit_chance': 0.0,
                    'lock_multishot': False, 'lock_fire_rate': False, 'bow_fire_rate_mult': 1.0,
                    'flat_status': 0.0, 'flat_crit_chance': 0.0, 'flat_crit_damage': 0.0,
                    'faction': {}, 'on_kill': [], 'on_weakpoint': []
                }

                desc_l = str(mod.get('description') or '').lower()
                if 'fire rate cannot be modified' in desc_l:
                    stats['lock_fire_rate'] = True
                if 'multishot cannot be modified' in desc_l:
                    stats['lock_multishot'] = True

                if mod.get('levelStats'):
                    for s in mod['levelStats'][-1].get('stats', []):
                        self._classify_mod_stat(str(s), stats)

                # Drop locations don't count: ordinary mods like Reach also come from Conclave.
                is_pvp = ('pvpmods' in unique_name.lower()) or ('conclave' in str(type).lower())
                mod_is_arcane = is_arcane and (name not in NON_ARCANES)
                mod_entry = {
                    'name': mod.get('name', ''),
                    'uniqueName': unique_name,
                    'is_pvp': is_pvp,
                    'type': type,
                    'compatName': compatName,
                    'fusionLimit': fusionLimit,
                    'is_arcane': mod_is_arcane,
                    'modSet': mod.get('modSet'),
                    'modSetValues': mod.get('modSetValues'),
                    **stats
                }
        
                if kr_name:
                    mod_entry['kr_name'] = kr_name
                    self._update_mod_index(kr_name.lower(), mod_entry)
                    self._update_mod_index(kr_name.lower().replace(' ', ''), mod_entry)
        
                self._update_mod_index(name, mod_entry)
                self._update_mod_index(name.replace(' ', '').lower(), mod_entry)

    def _classify_mod_stat(self, raw: str, stats: Dict[str, Any]) -> None:
        s = raw.replace('\\n', ' ').replace('\n', ' ')
        s = re.sub(r'<[^>]+>', '', s).strip().lower()

        if 'fire rate cannot be modified' in s:
            stats['lock_fire_rate'] = True
        if 'multishot cannot be modified' in s:
            stats['lock_multishot'] = True

        # Multi-clause conditional lines (e.g. Galvanized Scope / Crosshairs: On Weak Point Hit + On Weak Point Kill).
        clauses = [
            c.strip() for c in re.split(r'(?=(?:^|\s)on\s+(?:weak\s+point\s+|melee\s+|headshot\s+)?(?:hit|kill)\s*:)', s)
            if c.strip()
        ]
        if len(clauses) > 1:
            for clause in clauses:
                self._classify_mod_stat(clause, stats)
            return

        if re.match(r'on [^:]+:', s):
            m = re.match(
                r'on (?:melee |weak point |headshot )?kill:\s*\+(\d+(?:\.\d+)?)(%?)\s+(.+?)(?:\s+when aiming)?\s+for\s+\d+s(?:\.\s*stacks up to (\d+)x)?',
                s,
            )
            if m:
                key_map = {
                    'multishot': 'multishot',
                    'critical damage': 'crit_damage',
                    'critical chance': 'crit_chance',
                    'status chance': 'status',
                    'damage': 'damage',
                    'attack speed': 'attack_speed',
                    'initial combo': 'initial_combo',
                    'direct damage per status type affecting the target': 'status_type_direct',
                }
                key = key_map.get(m.group(3).strip())
                if key:
                    val = float(m.group(1)) / 100.0 if m.group(2) == '%' else float(m.group(1))
                    stacks = int(m.group(4)) if m.group(4) else 1
                    stats.setdefault('on_kill', [])
                    stats['on_kill'].append({
                        'stat': key,
                        'value': val,
                        'stacks': stacks,
                    })
                return

            m_wp = re.match(
                r'on (?:weak point|headshot) hits?(?:\s+with primary fire)?:\s*\+(\d+(?:\.\d+)?)%\s+(.+?)(?:\s+when aiming)?\s+for\s+\d+s(?:\.\s*stacks up to (\d+)x)?',
                s,
            )
            if m_wp:
                wp_map = {
                    'critical chance': 'crit_chance',
                    'critical damage': 'crit_damage',
                    'weak point damage': 'weak_point_damage',
                }
                key = wp_map.get(m_wp.group(2).strip())
                if key:
                    stacks = int(m_wp.group(3)) if m_wp.group(3) else 1
                    stats.setdefault('on_weakpoint', [])
                    stats['on_weakpoint'].append({
                        'stat': key,
                        'value': float(m_wp.group(1)) / 100.0,
                        'stacks': stacks,
                    })
                return

        m = re.match(r'x(\d+(?:\.\d+)?) damage to (\w+)', s)
        if m:
            stats.setdefault('faction', {})
            stats['faction'][m.group(2)] = float(m.group(1)) - 1.0
            return

        # Flat non-percentage stats: "+30 Initial Combo", "+16 Initial Combo".
        m = re.match(r'\+(\d+(?:\.\d+)?)\s+initial combo$', s)
        if m:
            stats['initial_combo'] = stats.get('initial_combo', 0.0) + float(m.group(1))
            return

        # Flat stats added after multipliers: "+20 Final Status Chance", "+25% Base Critical Chance".
        m = re.match(r'\+(\d+(?:\.\d+)?)%?\s+(?:final|base|flat)\s+status chance$', s)
        if m:
            stats['flat_status'] = stats.get('flat_status', 0.0) + float(m.group(1)) / 100.0
            return
        m = re.match(r'\+(\d+(?:\.\d+)?)%\s+(?:final|base)\s+critical chance$', s)
        if m:
            stats['flat_crit_chance'] = stats.get('flat_crit_chance', 0.0) + float(m.group(1)) / 100.0
            return
        m = re.match(r'\+(\d+(?:\.\d+)?)x\s+final critical damage multiplier$', s)
        if m:
            stats['flat_crit_damage'] = stats.get('flat_crit_damage', 0.0) + float(m.group(1))
            return

        m = re.match(r'([+-]\d+(?:\.\d+)?)%\s+(.+)$', s)
        if not m:
            return

        val = float(m.group(1)) / 100.0
        rest = m.group(2)
        phrase = re.sub(r'\s*\(.*?\)', '', rest).strip()
        # Acuity: "+350% Weak Point Critical Chance. Multishot cannot be modified."
        if 'multishot cannot be modified' in phrase:
            stats['lock_multishot'] = True
            phrase = phrase.split('.')[0].strip()

        direct = {
            'damage': 'damage',
            'melee damage': 'damage',
            'multishot': 'multishot',
            'critical chance': 'crit_chance',
            'critical damage': 'crit_damage',
            'fire rate': 'fire_rate',
            'attack speed': 'fire_rate',
            'magazine capacity': 'magazine_capacity',
            'reload speed': 'reload_speed',
            'status chance': 'status',
            'status damage': 'status_damage',
            'slam attack damage': 'slam_damage',
            'heavy attack damage': 'heavy_damage_bonus',
            'melee damage on heavy attack': 'heavy_damage_bonus',
            'heavy attack wind up speed': 'wind_up_speed',
            'finisher damage': 'finisher_damage',
            'weak point damage': 'weak_point_damage',
            'headshot damage': 'weak_point_damage',
            'to headshot multiplier': 'headshot_bonus',
            'weak point critical chance': 'weak_point_crit_chance',
            'critical chance stacks with combo multiplier': 'combo_crit',
            'status chance per combo multiplier': 'combo_status',
            'melee damage per status type affecting the target': 'status_type_damage',
            'slash': 'slash',
            'impact': 'impact',
            'puncture': 'puncture'
        }

        if phrase in direct:
            stats.setdefault(direct[phrase], 0.0)
            stats[direct[phrase]] += val
            if phrase == 'critical chance' and 'x2 for heavy' in rest:
                stats.setdefault('heavy_crit_chance', 0.0)
                stats['heavy_crit_chance'] += val
            if phrase == 'fire rate' and 'x2 for bows' in rest:
                stats['bow_fire_rate_mult'] = 2.0
            return

        elements = {
            'toxin': 'toxin',
            'cold': 'cold',
            'heat': 'heat',
            'electricity': 'electric',
            'viral': 'viral',
            'corrosive': 'corrosive',
            'radiation': 'radiation',
            'magnetic': 'magnetic',
            'blast': 'blast',
            'gas': 'gas'
        }

        if phrase in elements:
            stats.setdefault(elements[phrase], 0.0)
            stats[elements[phrase]] += val
            stats.setdefault('elemental_damage', 0.0)
            stats['elemental_damage'] += val

    def _update_mod_index(self, key, mod_entry):
        if key in self.mods_index:
            existing_entry = self.mods_index[key]
            # Don't overwrite complete mod entry from Mods.json with shell entry from weapon_arcanes.json
            if existing_entry.get('uniqueName') and not mod_entry.get('uniqueName'):
                if mod_entry.get('kr_name') and not existing_entry.get('kr_name'):
                    existing_entry['kr_name'] = mod_entry['kr_name']
                return
            if mod_entry['fusionLimit'] >= existing_entry['fusionLimit']:
                self.mods_index[key] = mod_entry
        else:
            self.mods_index[key] = mod_entry

    def match_weapon_strict(self, query: str, min_ratio: float = 88.0) -> Optional[Dict[str, Any]]:
        """For chat text, where a loose match turns everyday words into weapons. OCR uses fuzzy_match_weapon."""
        from scripts.jamo_matcher import decompose_hangul
        from rapidfuzz import fuzz

        key = query.lower().replace(' ', '')
        if key in self.weapons_index:
            return self.weapons_index[key]
        if len(key) < 3:
            return None
        decomposed = decompose_hangul(key)
        best, best_ratio = None, 0.0
        for candidate, meta in self.weapons_index.items():
            joined = candidate.replace(' ', '')
            if abs(len(joined) - len(key)) > 2:
                continue
            ratio = fuzz.ratio(decomposed, decompose_hangul(joined))
            if ratio > best_ratio:
                best, best_ratio = meta, ratio
        return best if best_ratio >= min_ratio else None

    def fuzzy_match_weapon(self, input_text: str) -> Optional[Dict[str, Any]]:
        # 1. Clean Lich/Sister/Coda prefix (preserving leading 'Dual '/'듀얼 ' for Dual Coda Torxica)
        text = input_text
        m_adv = _ADVERSARY_HEADER_RE.search(text)
        if m_adv:
            text = text[m_adv.start():]

        text = re.sub(r'\[.*?\]|\(.*?\)', ' ', text)
        text = re.sub(r'[가-힣a-zA-Z0-9]*\s*(?:업그레이드|레이드)\s*[/:\s]*', ' ', text)
        text = re.sub(r'수용량\s*\d+/\d+|구성\s*[A-Za-z0-9]|랭크\s*없음|\b\d+\b|표고|보느', ' ', text)
        text = re.sub(r'\b(mki-|mki |mk-1|mk 1)\b', 'mk1-', text, flags=re.I)
        text = re.sub(r'[\.…\^~`!@#$%&*+=|:;?<>/{}\[\]\(\)\-\_]', ' ', text)

        words = [w.strip().lower() for w in text.split() if w.strip()]
        if not words:
            return None

        # Check for truncation: If text contains ellipsis/dot ('.', '...', '?') and only contains a prefix without a specific weapon name following, RETURN NONE.
        if any(char in text for char in '.?') and len(words) <= 1 and words[0] in ['쿠바', 'kuva', '테넷', 'tenet', '코다', 'coda']:
            return None

        # If after cleaning, remaining words are only modifier/prefix words
        if len(words) == 1 and words[0] in ['쿠바', 'kuva', '테넷', 'tenet', '코다', 'coda']:
            return None

        # Match n-grams from longest to shortest
        for n in range(len(words), 0, -1):
            for i in range(len(words) - n + 1):
                ngram_spaced = ' '.join(words[i:i+n])
                ngram_joined = ''.join(words[i:i+n])
                if ngram_spaced in self.weapons_index:
                    return self.weapons_index[ngram_spaced]
                if ngram_joined in self.weapons_index:
                    return self.weapons_index[ngram_joined]

                # Truncated name prefix match (e.g. '쿠바구울' -> '쿠바구울소우')
                if len(ngram_joined) >= 3 and any(k in ngram_joined for k in ['쿠바', 'kuva', '테넷', 'tenet', '코다', 'coda', '프라임', 'prime', '구울', 'ghoul', '반달', 'vandal', '레이스', 'wraith']):
                    candidates = [meta for k, meta in self.weapons_index.items() if k.replace(' ', '').startswith(ngram_joined) and ngram_joined in k.replace(' ', '').lower()]
                    if candidates:
                        return candidates[0]

        # 2. Fuzzy Jamo matching across weapons_index
        try:
            from scripts.jamo_matcher import decompose_hangul
            from rapidfuzz import fuzz
            clean_joined = ''.join(words)
            if len(clean_joined) >= 2:
                decomp_in = decompose_hangul(clean_joined)
                best_cand = None
                best_ratio = 0.0
                for k, meta in self.weapons_index.items():
                    k_clean = k.replace(' ', '')
                    if abs(len(k_clean) - len(clean_joined)) > 5:
                        continue
                    decomp_k = decompose_hangul(k_clean)
                    r = fuzz.ratio(decomp_in, decomp_k)
                    if r > best_ratio:
                        best_ratio = r
                        best_cand = meta
                if best_cand and best_ratio >= 72.0:
                    return best_cand
        except Exception:
            pass

        return None

    def match_mod(self, text: str, category: Optional[str] = None) -> Optional[Dict[str, Any]]:
            # Clean input text: remove brackets and punctuation
            text = re.sub(r'\[.*?\]|\(.*?\)', '', text)
            text_clean = re.sub(r'[\d\+\-\*=\[\]\(\)\.,`~!\'\";:\/\\^|_?{}]+', '', text).replace(' ', '').lower()

            # Return None if text length is less than 2
            if len(text_clean) < 2:
                return None

            # Check for OCR aliases
            for alias, mod_name in sorted(self.mod_ocr_aliases.items(), key=lambda x: len(x[0]), reverse=True):
                if alias == text_clean or (alias in text_clean and len(text_clean) <= len(alias) + 2):
                    match = self.mods_index.get(mod_name.lower()) or self.mods_index.get(mod_name.lower().replace(' ', ''))
                    if match:
                        return match

            # Initialize best match
            best_match = None
            best_score = 0

            # Define category mappings
            category_mapping = {
                'Primary': ('primary', 'rifle', 'shotgun', 'bow', 'sniper', 'assault'),
                'Secondary': ('secondary', 'pistol', 'thrown'),
                'Melee': ('melee', 'stance', 'claw', 'sword', 'nikana', 'glaive', 'hammer', 'scythe', 'polearm', 'staff', 'dagger', 'dual', 'heavy')
            }

            # Iterate over mods in the index
            for mod_name, mod_data in self.mods_index.items():
                mod_name_clean = mod_name.replace(' ', '').lower()
                kr_name = mod_data.get('kr_name', '').replace(' ', '').lower()
                en_name = mod_data.get('name', '').replace(' ', '').lower()

                # Check if category matches
                if category:
                    allowed_categories = category_mapping.get(category, [])
                    combined_compat = f"{mod_data.get('compatName', '')} {mod_data.get('type', '')}".lower()
                    if not any(cat.lower() in combined_compat for cat in allowed_categories):
                        continue

                # Exact match
                if text_clean == mod_name_clean or text_clean == kr_name or text_clean == en_name:
                    return mod_data

                # No-space match
                if text_clean in mod_name_clean or text_clean in kr_name or text_clean in en_name:
                    return mod_data

                # Substring match (prefer longest)
                if kr_name and len(kr_name) >= 3 and kr_name in text_clean:
                    if len(kr_name) > best_score:
                        best_match = mod_data
                        best_score = len(kr_name)
                elif en_name and len(en_name) >= 3 and en_name in text_clean:
                    if len(en_name) > best_score:
                        best_match = mod_data
                        best_score = len(en_name)

            return best_match

    def extract_all_mods(self, ocr_text: str, weapon_category: Optional[str] = None) -> List[Dict[str, Any]]:
        # Clean OCR text
        cleaned_text = ocr_text.lower().replace(' ', '')
        
        # Sort mods_index keys by length in descending order
        sorted_mod_keys = sorted(self.mods_index.keys(), key=len, reverse=True)
        
        # Initialize result list and buffer
        result = []
        buffer = cleaned_text
        
        # Iterate over sorted mod keys
        for mod_name in sorted_mod_keys:
            if len(mod_name) < 3:
                continue
            
            # Check if mod name is in the buffer
            if mod_name in buffer:
                mod_entry = self.mods_index[mod_name]
                
                # Filter by weapon category if provided
                if weapon_category:
                    mod_type = mod_entry.get('type', '').lower()
                    if weapon_category == 'secondary' and mod_type in ['melee', 'companion', 'warframe']:
                        continue
                    if weapon_category == 'melee' and mod_type in ['secondary', 'primary', 'companion']:
                        continue
                    if weapon_category == 'primary' and mod_type in ['secondary', 'melee', 'companion']:
                        continue
                
                # Append matched mod entry without duplicates
                if mod_entry not in result:
                    result.append(mod_entry)
                
                # Mask matched text with spaces
                buffer = buffer.replace(mod_name, ' ' * len(mod_name))
                
                # Stop when 8 mods are found
                if len(result) == 8:
                    break
        
        return result
