import os
import json
from typing import Dict, Any, Optional, List
import difflib
import re
from scripts.path_config import get_path

class WFDataIndexer:
    def __init__(self, data_dir='data/raw_wfcd'):
        self.data_dir = get_path(data_dir) if not os.path.isabs(data_dir) else data_dir
        self.weapons_index = {}
        self.mods_index = {}
        self.load_data()

    def load_data(self):
            ko_path = os.path.join(self.data_dir, 'ko.json')
            self.ko_dict = {}
            if os.path.exists(ko_path):
                try:
                    with open(ko_path, 'r', encoding='utf-8') as f:
                        self.ko_dict = json.load(f)
                except Exception:
                    pass

            files = ['Primary.json', 'Secondary.json', 'Melee.json', 'Arch-Gun.json', 'Arch-Melee.json', 'Warframes.json', 'Mods.json', 'weapon_arcanes.json']
            for file in files:
                file_path = os.path.join(self.data_dir, file)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if file in ('Mods.json', 'weapon_arcanes.json'):
                            self.index_mods(data, is_arcane=(file == 'weapon_arcanes.json'))
                        elif file == 'Warframes.json':
                            self.index_warframes(data)
                        else:
                            self.index_weapons(data)

            mod_ocr_aliases_path = os.path.join(self.data_dir, 'mod_ocr_aliases.json')
            self.mod_ocr_aliases = {}
            if os.path.exists(mod_ocr_aliases_path):
                try:
                    with open(mod_ocr_aliases_path, 'r', encoding='utf-8') as f:
                        self.mod_ocr_aliases = json.load(f).get('exact_typos', {})
                except Exception:
                    pass

    def index_weapons(self, data: List[Dict[str, Any]]) -> None:
        for weapon in data:
            name = weapon.get('name', '').lower()
            metadata = {
                'name': weapon.get('name', ''),
                'category': weapon.get('category', ''),
                'type': weapon.get('type', ''),
                'total_damage': weapon.get('totalDamage', 0) or sum(attack.get('damagePerShot', 0) for attack in weapon.get('attacks', [])),
                'crit_chance': weapon.get('criticalChance', weapon.get('critChance', 0)) / 100 if weapon.get('criticalChance', weapon.get('critChance', 0)) > 1 else weapon.get('criticalChance', weapon.get('critChance', 0)),
                'crit_mult': weapon.get('criticalMultiplier', weapon.get('critMultiplier', 0)),
                'fire_rate': weapon.get('fireRate', 0),
                'status_chance': weapon.get('procChance', weapon.get('statusChance', 0)) / 100 if weapon.get('procChance', weapon.get('statusChance', 0)) > 1 else weapon.get('procChance', weapon.get('statusChance', 0)),
                'magazineSize': weapon.get('magazineSize', 0),
                'reloadTime': weapon.get('reloadTime', 0),
                'base_multishot': float(weapon.get('multishot', 1) or 1)
            }
        
            # Look up the official Korean name
            unique_name = weapon.get('uniqueName', '')
            kr_entry = self.ko_dict.get(unique_name, {})
            kr_name = kr_entry.get('name', '') if isinstance(kr_entry, dict) else ''
            if kr_name:
                metadata['kr_name'] = kr_name
                self.weapons_index[kr_name.lower()] = metadata
                self.weapons_index[kr_name.lower().replace(' ', '')] = metadata
                self.weapons_index[kr_name.lower().replace('-', '').replace(' ', '')] = metadata
                self.weapons_index[kr_name.lower().replace('-', ' ')] = metadata
        
            # Index by English name
            self.weapons_index[name] = metadata
            self.weapons_index[name.replace(' ', '').lower()] = metadata
            self.weapons_index[name.replace('-', '').replace(' ', '').lower()] = metadata
            self.weapons_index[name.replace('-', ' ').lower()] = metadata
        
            # Special aliases
            if name == 'laetum':
                self.weapons_index['라에툼'] = metadata
            if name == 'burston':
                self.weapons_index['버스턴'] = metadata
        
            # Scan attacks for specific types
            attacks = weapon.get('attacks', [])
            metadata['attacks'] = attacks
            # Multi-mode weapons leave top-level stats empty; the first attack holds the real values.
            if not metadata['crit_chance'] and attacks and attacks[0].get('crit_chance'):
                metadata['crit_chance'] = attacks[0]['crit_chance'] / 100.0
                metadata['crit_mult'] = attacks[0].get('crit_mult', metadata['crit_mult'])
                metadata['fire_rate'] = attacks[0].get('speed', metadata['fire_rate'])
                metadata['total_damage'] = sum(attacks[0].get('damage', {}).values()) or metadata['total_damage']
            radial_attack = next((attack for attack in attacks if attack.get('shot_type', '').lower() == 'aoe' or 'radial' in attack.get('name', '').lower() or 'explosion' in attack.get('name', '').lower()), None)
            incarnon_attack = next((attack for attack in attacks if 'incarnon' in attack.get('name', '').lower()), None)
        
            if radial_attack:
                metadata['radial_attack'] = radial_attack
            if incarnon_attack:
                metadata['incarnon_attack'] = incarnon_attack
                if radial_attack and incarnon_attack:
                    metadata['incarnon_aoe'] = radial_attack

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
                    'weak_point_damage': 0.0, 'combo_crit': 0.0, 'combo_status': 0.0, 'status_type_damage': 0.0,
                    'heavy_crit_chance': 0.0, 'weak_point_crit_chance': 0.0, 'lock_multishot': False,
                    'flat_status': 0.0, 'flat_crit_chance': 0.0, 'flat_crit_damage': 0.0,
                    'faction': {}, 'on_kill': []
                }

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

        if re.match(r'on [^:]+:', s):
            m = re.match(r'on (?:melee )?kill:\s*\+(\d+(?:\.\d+)?)%\s+(.+?)\s+for\s+\d+s\.\s*stacks up to (\d+)x', s)
            if m:
                key_map = {
                    'multishot': 'multishot',
                    'critical damage': 'crit_damage',
                    'critical chance': 'crit_chance',
                    'status chance': 'status',
                    'damage': 'damage',
                    'direct damage per status type affecting the target': 'status_type_direct'
                }
                key = key_map.get(m.group(2))
                if key:
                    stats.setdefault('on_kill', [])
                    stats['on_kill'].append({
                        'stat': key,
                        'value': float(m.group(1)) / 100.0,
                        'stacks': int(m.group(3))
                    })
                return

        m = re.match(r'x(\d+(?:\.\d+)?) damage to (\w+)', s)
        if m:
            stats.setdefault('faction', {})
            stats['faction'][m.group(2)] = float(m.group(1)) - 1.0
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
            'finisher damage': 'finisher_damage',
            'weak point damage': 'weak_point_damage',
            'headshot damage': 'weak_point_damage',
            'to headshot multiplier': 'weak_point_damage',
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
        # 1. Clean Lich/Sister/Coda prefix
        text = input_text
        for prefix in ['쿠바', 'kuva', '테넷', 'tenet', '코다', 'coda']:
            idx = text.lower().find(prefix.lower())
            if idx != -1:
                text = text[idx:]
                break

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
