try:
    import torch
except Exception:
    pass

import os
import re
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from PIL import Image, ImageChops, ImageEnhance, ImageOps

try:
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR
    rapid_ocr_engine = RapidOCR()
except Exception:
    rapid_ocr_engine = None

try:
    import winocr
except ImportError:
    winocr = None

from scripts.wf_data_indexer import WFDataIndexer
from scripts.jamo_matcher import match_mods_jamo
from scripts.build_store import BuildStore, GRID_SLOTS, RIVEN_MOD, canonical_slot, is_riven_name, slot_order
from scripts.riven_reroll_reader import STAT_DISPLAY, looks_like_reroll_screen, parse_stat_line, read_reroll_screen
from scripts.innate_traits import BONUS_ELEMENTS, BONUS_MAX, BONUS_MIN, bonus_in, is_adversary, parse_bonus_answer, set_bonus


def looks_like_riven_card(slot_text: str) -> bool:
    """On the Korean client only riven names are in Latin letters (코린트 Crita-armatox).

    OCR splits such names across lines, so a name pattern can't be relied on. One pass can also
    produce a stray Latin word, so the word has to appear in at least two passes.
    """
    if not re.search(r'[가-힣]', slot_text):
        return False
    passes = [p for p in slot_text.split('|||')]
    return sum(1 for p in passes if re.search(r'(?<![A-Za-z])[A-Za-z][a-z]{3,}', p)) >= 2

class ScreenModAnalyzer:

    STAT_PATTERNS = {
        "crit_chance": [r"치명타\s*확률", r"critical\s*chance", r"치확"],
        "crit_damage": [r"치명타\s*피해", r"critical\s*damage", r"치피"],
        "finisher_damage": [r"마무리\s*일격\s*피해", r"마무리\s*일격", r"finisher\s*damage"],
        "initial_combo": [r"기본\s*연속기", r"초기\s*연속기", r"initial\s*combo"],
        "multishot": [r"멀티샷", r"multishot", r"멀샷"],
        "base_damage": [
            r"(?<!치명타\s)(?<!치명타)(?<!일격\s)(?<!일격)(?<!마무리\s)(?<!마무리)(?<!헤드샷\s)(?<!헤드샷)(?<!관통\s)(?<!관통)(?<!충격\s)(?<!충격)(?<!베기\s)(?<!베기)피해(?![\w%])",
            r"(?<!critical\s)(?<!finisher\s)(?<!headshot\s)(?<!puncture\s)(?<!impact\s)(?<!slash\s)damage(?![\w%])",
            r"기초\s*피해"
        ],
        "fire_rate": [r"연사력", r"fire\s*rate", r"공격\s*속도", r"공속", r"attack\s*speed"],
        "status_chance": [r"상태이상\s*확률", r"status\s*chance", r"상확"],
        "elemental_damage": [r"화염", r"전기", r"독성", r"냉기", r"heat", r"electricity", r"toxin", r"cold"]
    }

    def __init__(self, preferred_ocr: str = "winocr"):
        self.preferred_ocr = preferred_ocr
        self.indexer = WFDataIndexer()
        self.build_store = BuildStore()
        # Riven values entered before the build is confirmed, kept until it is saved.
        self.entered_rivens: Dict[str, Dict[str, float]] = {}
        # Valence Bonus the player told us per adversary weapon, reused for later scans this session.
        self.bonus_elements: Dict[str, Tuple[str, float]] = {}
        self.pending_bonus: Optional[Dict[str, Any]] = None
        self.pending_screenshot = None
        self.incarnon_traits = self._load_incarnon_traits()
        try:
            from scripts.yolo_slot_detector import YOLOSlotDetector
            self.yolo_detector = YOLOSlotDetector()
        except Exception:
            self.yolo_detector = None

    def _load_incarnon_traits(self) -> Dict[str, str]:
        traits_path = Path(__file__).resolve().parent.parent / "data" / "incarnon_traits.json"
        if traits_path.exists():
            try:
                return json.loads(traits_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def get_incarnon_trait_description(self, weapon_name: str, inc_attack: Optional[Dict[str, Any]] = None) -> str:
        w_lower = weapon_name.lower()
        for key, desc in self.incarnon_traits.items():
            if key in w_lower:
                return desc

        if inc_attack and isinstance(inc_attack, dict):
            shot_type = str(inc_attack.get("shot_type", ""))
            dmg_dict = inc_attack.get("damage", {})
            top_elem = max(dmg_dict.items(), key=lambda x: x[1])[0] if isinstance(dmg_dict, dict) and dmg_dict else ""

            elem_names = {
                "heat": "초고열 화염", "toxin": "치명적 맹독", "electricity": "연쇄 전격",
                "cold": "극저온 결빙", "radiation": "방사능", "corrosive": "장갑 부식",
                "viral": "바이러스 확산", "blast": "연쇄 폭발", "slash": "치명적 베기"
            }
            elem_str = elem_names.get(top_elem.lower(), "고출력 에너지")

            if "beam" in shot_type.lower() or "continuous" in shot_type.lower():
                mode_str = "연쇄 광선/빔 방사"
            elif inc_attack.get("radial_attack") or "aoe" in shot_type.lower():
                mode_str = "광역 폭발탄"
            elif "projectile" in shot_type.lower():
                mode_str = "특수 가속 투사체"
            else:
                mode_str = "특수 변신 탄환"

            return f"게이지 완충 시 {elem_str} {mode_str} 모드로 전장 제압!"

        return "게이지 완충 시 인카논 고유 변신 화력으로 전장 초토화!"

    def ocr_image(self, image_input) -> str:
            try:
                if isinstance(image_input, str):
                    img = Image.open(image_input)
                else:
                    img = image_input

                # Convert to RGB
                img = img.convert("RGB")

                # Upscale if width < 1600
                if img.width < 1600:
                    img = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)

                if self.preferred_ocr == 'rapidocr' and rapid_ocr_engine is not None:
                    np_img = np.array(img)
                    result, _ = rapid_ocr_engine(np_img)
                    if result:
                        lines = [item[1] for item in result if item and len(item) > 1]
                        if lines:
                            return '\n'.join(lines)

                # Fall back to winocr if preferred or rapidocr failed
                if winocr is None:
                    return ""

                # Create high-contrast grayscale version
                img_gray = img.convert("L")
                img_high_contrast = ImageOps.autocontrast(img_gray)

                # Run OCR on original and high-contrast images
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                ocr_result_original = loop.run_until_complete(winocr.recognize_pil(img, lang="ko"))
                ocr_result_high_contrast = loop.run_until_complete(winocr.recognize_pil(img_high_contrast, lang="ko"))

                loop.close()

                # Extract lines from OCR results
                lines_orig = [l.text if hasattr(l, 'text') else str(l) for l in ocr_result_original.lines]
                lines_contrast = [l.text if hasattr(l, 'text') else str(l) for l in ocr_result_high_contrast.lines]

                # Deduplicate lines while maintaining order
                seen = set()
                deduplicated_lines = []
                for line in lines_orig + lines_contrast:
                    if line not in seen:
                        seen.add(line)
                        deduplicated_lines.append(line)

                merged_text = "\n".join(deduplicated_lines)

                return merged_text
            except Exception as e:
                return f"[OCR Error] {str(e)}"

    def diagnose_screenshot(self, image_input, forced_weapon_meta=None) -> Dict[str, Any]:
            # A question about the previous scan's bonus no longer applies once a new screen arrives.
            self.pending_bonus = None
            if isinstance(image_input, str):
                if os.path.exists(image_input):
                    img = Image.open(image_input)
                else:
                    img = Image.new("RGB", (300, 100), color=(0, 0, 0))
            else:
                img = image_input
            w, h = img.size

            # Run full-image OCR
            full_text = self.ocr_image(img)
            if looks_like_reroll_screen(full_text):
                compare = self._diagnose_reroll_screen(img)
                if compare:
                    return compare
            parsed = self.parse_stats(full_text)

            # Check for pending riven and parsed stats (only if NOT a full modding screen)
            is_full_modding_screen = ('업그레이드' in full_text or '수용량' in full_text or '기본 공격' in full_text or (w >= 900 and h >= 500))
            if is_full_modding_screen and self.has_pending_riven():
                self.clear_pending_riven()

            if self.has_pending_riven() and parsed.get('stats') and not is_full_modding_screen:
                ctx = self.pending_riven_context
                w_meta_ctx = ctx["w_meta"]
                left_stats_ctx = ctx.get("left_stats", {})
                mod_objs_ctx = ctx.get("mod_objs", [])
                riven_name_ctx = ctx.get("riven_name", "리벤 모드")
                base_metrics_ctx = ctx.get("base_metrics", {})
                riven_stats = parsed.get('stats')

                with_riven_metrics = self.calculate_comprehensive_metrics(
                    w_meta_ctx,
                    left_stats=left_stats_ctx,
                    mod_objs=mod_objs_ctx,
                    riven_stats=riven_stats,
                    riven_in_panel=True
                )
                base_metrics_ctx = self._riven_free_metrics(w_meta_ctx, left_stats_ctx, mod_objs_ctx, riven_stats, base_metrics_ctx)
                report = self.format_riven_comparison_report(
                    w_meta_ctx,
                    riven_name_ctx,
                    riven_stats,
                    base_metrics_ctx,
                    with_riven_metrics
                )
                calculation_breakdown = self.format_calculation_breakdown(w_meta_ctx, mod_objs_ctx, with_riven_metrics, riven_stats=riven_stats)
                self.clear_pending_riven()
                return {
                    "success": True,
                    "is_riven_report": True,
                    "weapon": w_meta_ctx["name"],
                    "riven_name": riven_name_ctx,
                    "riven_stats": riven_stats,
                    "stats": left_stats_ctx,
                    "metrics": with_riven_metrics,
                    "base_metrics": base_metrics_ctx,
                    "message": report,
                    "calculation_breakdown": calculation_breakdown,
                    "raw_ocr": full_text
                }

            # Header OCR for weapon (YOLO exact header crop first)
            w_meta = forced_weapon_meta
            header_text = ""
            if not w_meta:
                if self.yolo_detector and self.yolo_detector.is_available():
                    try:
                        layout = self.yolo_detector.detect_layout(img)
                        h_box = layout.get("name_header_box")
                        if h_box:
                            h_crop = img.crop(h_box)
                            h_crop = h_crop.resize((h_crop.width * 2, h_crop.height * 2), Image.Resampling.LANCZOS)
                            header_text = self.ocr_image(h_crop)
                            m_title = re.search(r'(?:업그레이드|레이드)\s*[/:\s]\s*([가-힣a-zA-Z0-9\s\-]+?)(?:\s*\[|\s*$|\n)', header_text)
                            if m_title:
                                cand_w = m_title.group(1).strip().replace('해이트', '헤이트')
                                w_meta = self.indexer.fuzzy_match_weapon(cand_w)
                            if not w_meta:
                                w_meta = self.indexer.fuzzy_match_weapon(header_text)
                    except Exception:
                        pass

                if not w_meta:
                    header = img.crop((0, 0, int(w * 0.65), int(h * 0.22)))
                    header_text = self.ocr_image(header)
                    m_title = re.search(r'(?:업그레이드|레이드)\s*[/:\s]\s*([가-힣a-zA-Z0-9\s\-]+?)(?:\s*\[|\s*$|\n)', header_text)
                    if m_title:
                        cand_w = m_title.group(1).strip().replace('해이트', '헤이트')
                        w_meta = self.indexer.fuzzy_match_weapon(cand_w)
                    if not w_meta:
                        w_meta = self.indexer.fuzzy_match_weapon(header_text)
                if not w_meta:
                    wide_header = img.crop((0, 0, int(w * 0.75), int(h * 0.25)))
                    wide_text = self.ocr_image(wide_header)
                    m_title = re.search(r'(?:업그레이드|레이드)\s*[/:\s]\s*([가-힣a-zA-Z0-9\s\-]+?)(?:\s*\[|\s*$|\n)', wide_text)
                    if m_title:
                        cand_w = m_title.group(1).strip().replace('해이트', '헤이트')
                        w_meta = self.indexer.fuzzy_match_weapon(cand_w)
                    if not w_meta:
                        w_meta = self.indexer.fuzzy_match_weapon(wide_text)

            # 1. winocr slot-by-slot grid crop
            slot_res = self.crop_and_ocr_mod_slots(img, category=w_meta.get("category") if w_meta else None)
            slot_results = slot_res.get("slot_results", [])

            # If weapon header was missing, try inferring from slot OCR (Riven prefix, augment, or mod affinity)
            is_weapon_inferred = False
            riven_affixes = ['acri', 'tin', 'tox', 'cron', 'ata', 'mag', 'can', 'con', 'ada', 'pha', 'visi', 'sati', 'gni', 'hexa', 'zore', 'lexi', 'pur', 'feva', 'geli', 'deci', 'dex', 'tenta', 'dra', 'para', 'sci', 'boon', 'crita', 'locti']
            if not w_meta:
                for s_name, s_text in slot_results:
                    if not s_text: continue
                    has_riven_kw = any(kw in s_text.lower() for kw in ['리벤', 'riven', 'critatak', '크리타탁']) or any(kw in s_text.lower() for kw in riven_affixes)
                    if not has_riven_kw:
                        continue
                    # Check token directly preceding the riven affix or hyphen
                    m_affix = re.search(r'([가-힣a-zA-Z0-9]{2,})[\s\-_]+(?:[a-zA-Z가-힣]{2,}-[a-zA-Z가-힣]{2,}|(?:acri|crita|visi|sati|hexa|deci|igni|geli|toxi|locti|croni|feva|lexi|tenta)[a-z]{2,6}|critatak|크리타탁)', s_text, re.I)
                    if m_affix:
                        target_token = m_affix.group(1)
                        cand = self.indexer.fuzzy_match_weapon(target_token)
                        if cand and cand.get("name") not in ["Riven", "Primed", "Galvanized", "Amalgam", "Pride"]:
                            if cand.get("category") != "Warframe":
                                w_meta = cand
                                break

            if not w_meta:
                from scripts.jamo_matcher import CATEGORY_MAPPING, decompose_hangul
                from rapidfuzz import fuzz
                all_cands = []
                seen_c = set()
                for k, mod in self.indexer.mods_index.items():
                    m_n = mod.get("name")
                    if not m_n or m_n in seen_c: continue
                    seen_c.add(m_n)
                    kr = mod.get("kr_name", "")
                    if kr: all_cands.append((decompose_hangul(kr.replace(" ", "")), kr, mod))
                    all_cands.append((decompose_hangul(m_n.lower().replace(" ", "")), m_n, mod))

                matched_cats = {"primary": 0, "secondary": 0, "melee": 0, "warframe": 0}
                for s_name, s_text in slot_results:
                    if not s_text: continue
                    m_cand, sc = self._match_single_slot(s_text, all_cands)
                    if m_cand and sc >= 55.0:
                        m_t = (m_cand.get("type") or "").lower()
                        for c_key, c_types in CATEGORY_MAPPING.items():
                            if any(ct in m_t for ct in c_types):
                                matched_cats[c_key] += 1
                                break

                best_cat = max(matched_cats, key=matched_cats.get)
                if matched_cats[best_cat] >= 2:
                    is_weapon_inferred = True
                    cat_display = {
                        "primary": ("인식된 주무기 (소총 규격)", "Primary", "Rifle"),
                        "secondary": ("인식된 보조무기 (권총 규격)", "Secondary", "Pistol"),
                        "melee": ("인식된 근접무기", "Melee", "Melee"),
                        "warframe": ("인식된 워프레임", "Warframe", "Warframe")
                    }.get(best_cat, ("인식된 무기", "Primary", "Rifle"))
                    w_meta = {
                        "name": cat_display[0],
                        "kr_name": cat_display[0],
                        "category": cat_display[1],
                        "type": cat_display[2],
                        "is_inferred": True,
                        "crit_chance": 0.20,
                        "crit_mult": 2.0,
                        "fire_rate": 10.0,
                        "status_chance": 0.20,
                        "total_damage": 100.0
                    }

            if not w_meta:
                self.pending_screenshot = {"img": img, "parsed": parsed, "header_text": header_text}
                return {
                    "success": False,
                    "needs_clarification": True,
                    "message": (
                        "**[세팔론 오디스 문의]** 오퍼레이터님! 모딩창 상단의 무기 이름이 잘리거나 흐릿하여 어떤 무기인지 도저히 분간하기 어렵습니다! 😭\n\n"
                        "💬 **혹시 분석하려는 무기의 이름이 무엇인지 알려주시겠습니까?**\n"
                        "무기 이름을 채팅으로 말씀해 주시면 즉시 화력 진단을 재개하겠습니다!\n\n"
                        "⚠️ **재촬영 요청 가이드**:\n"
                        "1. 또는 모딩창 맨 위 좌측의 무기 이름이 포함되도록 다시 캡처해 주셔도 좋습니다.\n"
                        "2. 8개 모드 슬롯이 잘리지 않도록 캡처창을 조절해 주십시오!"
                    ),
                    "raw_ocr": header_text
                }

            if is_weapon_inferred:
                self.pending_screenshot = {"img": img, "parsed": parsed, "header_text": header_text}
            else:
                self.pending_screenshot = None

            left_stats = self.extract_left_panel_stats(img, full_text=full_text)
            if left_stats is None:
                left_stats = {}
            bonus_note = self._resolve_bonus(w_meta, left_stats)

            category = (w_meta.get("category") or "").lower()
            from scripts.jamo_matcher import CATEGORY_MAPPING, decompose_hangul
            from rapidfuzz import fuzz


            # 2. Dedicated slot matching
            candidates = self._build_slot_candidates(w_meta, category)

            slot_matches = []
            assigned_slots = {}
            seen_mod_names = set()
            riven_name = None

            for slot_idx, (slot_name, s_text) in enumerate(slot_results):
                w_kr = w_meta.get('kr_name', '').lower()
                w_en = w_meta.get('name', '').lower()
                w_kr_base = w_kr.split()[-1] if w_kr else ""
                w_en_base = w_en.split()[-1] if w_en else ""

                has_hyphen_affix = bool(re.search(r'[a-zA-Z가-힣]{2,}-[a-zA-Z가-힣]{2,}', s_text))
                has_weapon_name = False
                if w_kr and w_kr in s_text.lower():
                    has_weapon_name = True
                elif w_kr_base and len(w_kr_base) >= 2:
                    if w_kr_base in s_text.lower() or fuzz.partial_ratio(decompose_hangul(w_kr_base), decompose_hangul(s_text.replace(" ", ""))) >= 75:
                        has_weapon_name = True
                if w_en and w_en in s_text.lower():
                    has_weapon_name = True
                elif w_en_base and len(w_en_base) >= 3 and w_en_base in s_text.lower():
                    has_weapon_name = True

                riven_affixes = ['acri', 'tin', 'tox', 'cron', 'ata', 'mag', 'can', 'con', 'ada', 'pha', 'visi', 'sati', 'gni', 'hexa', 'zore', 'lexi', 'pur', 'feva', 'geli', 'deci', 'dex', 'tenta', 'dra', 'para', 'sci', 'boon', 'crita', 'locti']
                has_two_stat_riven = bool(re.search(r'(?:acri|crita|visi|sati|hexa|deci|igni|geli|toxi|locti|croni|feva|lexi|tenta)[a-z]{2,6}', s_text, re.I))
                is_riven = (
                    any(kw in s_text.lower() for kw in ['리벤', 'riven', 'critatak', '크리타탁']) or
                    (has_hyphen_affix and (has_weapon_name or any(kw in s_text.lower() for kw in riven_affixes))) or
                    has_two_stat_riven or
                    (has_weapon_name and any(kw in s_text.lower() for kw in riven_affixes)) or
                    looks_like_riven_card(s_text)
                )

                if is_riven:
                    assigned_slots[slot_idx] = (slot_name, {"name": "Riven Mod", "kr_name": "리벤 모드"}, 100.0)
                    riven_name = s_text
                    continue

                slot_cands = self._match_single_slot(s_text, candidates, return_all=True)
                for score, m_cand in slot_cands:
                    slot_matches.append((score, slot_idx, slot_name, m_cand))

            slot_matches.sort(key=lambda x: x[0], reverse=True)
            for score, slot_idx, slot_name, m_obj in slot_matches:
                if slot_idx in assigned_slots:
                    continue
                m_name = m_obj["name"]
                if m_name in seen_mod_names:
                    continue
                if f"Primed {m_name}" in seen_mod_names:
                    continue
                if m_name.startswith("Primed ") and m_name.replace("Primed ", "") in seen_mod_names:
                    base_n = m_name.replace("Primed ", "")
                    seen_mod_names.discard(base_n)
                    for k, v in list(assigned_slots.items()):
                        if v[1]["name"] == base_n:
                            del assigned_slots[k]
                seen_mod_names.add(m_name)
                assigned_slots[slot_idx] = (slot_name, m_obj, score)

            # slot_index keeps top-left to bottom-right order for elemental combination; Exilus is considered after the grid.
            unique_mod_entries = [dict(assigned_slots[k][1], slot_index=(99 if assigned_slots[k][0] == "Exilus" else k), slot_name=assigned_slots[k][0]) for k in sorted(assigned_slots.keys())]

            # Fallback to general jamo matching if slot extraction yielded fewer than 4 mods
            if len(unique_mod_entries) < 4 and not slot_res.get("yolo_used", False):
                jamo_mods = match_mods_jamo(slot_res.get("merged_text", ""), self.indexer.mods_index, category=category, w_meta=w_meta)
                for m in jamo_mods:
                    if m["name"] not in seen_mod_names:
                        seen_mod_names.add(m["name"])
                        unique_mod_entries.append(m)

            max_slots = 10 if category in ["melee", "warframe"] else 9
            unique_mod_entries = unique_mod_entries[:max_slots]

            # Format detected mods
            formatted_mods = []
            for mod in unique_mod_entries:
                kr_name = mod.get("kr_name", mod["name"])
                formatted_mods.append(f"{kr_name} ({mod['name']})")

            metrics = self.calculate_comprehensive_metrics(w_meta, left_stats=left_stats, mod_objs=unique_mod_entries)
            arcane = self._detect_arcane(img, w_meta.get("category"))
            metrics["arcane"] = arcane
            if w_meta.get("category") != "Warframe":
                metrics["full_stack"] = self.damage_engine.compute_full_stack(w_meta, left_stats=left_stats, mod_objs=unique_mod_entries, arcane=arcane if arcane and arcane.get("modeled") else None)
            briefing = self.format_ordis_briefing(w_meta, formatted_mods, metrics)
            review_msg = self.format_mod_review_briefing(w_meta, formatted_mods, equipped_slot_count=slot_res.get('equipped_slot_count', 0), riven_name=riven_name)
            breakdown_msg = self.format_calculation_breakdown(w_meta, unique_mod_entries, metrics)

            if is_weapon_inferred:
                inferred_note = (
                    "💡 **[알림: 무기명 자동 추정]** 상단 무기 이름이 잘려 있어 장착된 모드 구성을 기반으로 기본 규격 화력을 계산했습니다.\n"
                    "채팅으로 정확한 무기 이름(예: '마이터', '소벡', '쿠바 자르')을 입력해 주시면 고유 스펙 및 인카논 특성을 즉시 반영합니다!\n\n"
                )
                briefing = inferred_note + briefing
                review_msg = inferred_note + review_msg

            self.entered_rivens.pop(w_meta['name'], None)
            if riven_name:
                self._await_riven_values(w_meta, left_stats, unique_mod_entries, riven_name)
                briefing += self._riven_notice()

            self.last_diagnosis_result = {
                'weapon': w_meta['name'],
                'w_meta': w_meta,
                'detected_mods': formatted_mods,
                'mod_objs': unique_mod_entries,
                'metrics': metrics,
                'message': briefing,
                'review_message': review_msg,
                'calculation_breakdown': breakdown_msg,
                'equipped_slot_count': slot_res.get('equipped_slot_count', 0)
            }

            result = {
                "success": True,
                "weapon": w_meta['name'],
                "stats": left_stats,
                "detected_mods": formatted_mods,
                "message": briefing,
                "review_message": review_msg,
                "calculation_breakdown": breakdown_msg,
                "equipped_slot_count": slot_res.get('equipped_slot_count', 0),
                "recognized_mod_count": len(formatted_mods),
                "metrics": metrics,
                "w_meta": w_meta,
                "mod_objs": unique_mod_entries,
                "raw_ocr": full_text
            }
            if bonus_note:
                result["message"] += bonus_note
                result["review_message"] += bonus_note
            if bonus_note == self._bonus_question(w_meta):
                result["needs_bonus_element"] = True
                self.pending_bonus = result
            return result

    def _resolve_bonus(self, w_meta: Dict[str, Any], stats: Dict[str, float]) -> str:
        """Fills in an adversary weapon's Valence Bonus and returns the line telling the player where it came from.

        The panel wins; otherwise a value the player gave earlier this session; otherwise we ask.
        """
        self.pending_bonus = None
        if not is_adversary(w_meta):
            return ""
        name = w_meta.get('kr_name') or w_meta['name']
        seen = bonus_in(stats)
        if seen:
            self.bonus_elements[w_meta['name']] = seen
            return ""
        known = self.bonus_elements.get(w_meta['name'])
        if known:
            set_bonus(stats, *known)
            return (f"\n\n🧪 **[보너스 속성]** {name}의 보너스 속성은 지난번에 알려주신 "
                    f"**{BONUS_ELEMENTS[known[0]]} {known[1] * 100:g}%**로 계산했습니다. 바뀌었다면 `자성 45`처럼 다시 알려 주십시오.")
        return self._bonus_question(w_meta)

    @staticmethod
    def _bonus_question(w_meta: Dict[str, Any]) -> str:
        name = w_meta.get('kr_name') or w_meta['name']
        return (f"\n\n🧪 **[보너스 속성 확인]** {name}은(는) 대적자 무기라 보너스 속성이 붙어 있는데, 패널에서 읽지 못했습니다.\n"
                f"💬 **보너스 속성과 수치가 어떻게 되나요?** 아래 버튼을 누르시거나 `자성 45`처럼 입력해 주십시오 "
                f"(충격·화염·냉기·전기·독성·자성·방사능, {BONUS_MIN * 100:g}~{BONUS_MAX * 100:g}%). 알려주시기 전까지는 계산에 넣지 않습니다.")

    def has_pending_bonus(self) -> bool:
        return self.pending_bonus is not None

    def clear_pending_bonus(self) -> None:
        self.pending_bonus = None

    def resume_pending_bonus(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Applies a chat answer to the waiting scan. None when the message isn't an answer at all."""
        if not self.has_pending_bonus():
            return None
        parsed = parse_bonus_answer(user_input)
        if not parsed:
            return None
        element, fraction = parsed
        if fraction is None:
            fraction = BONUS_MAX
        if not BONUS_MIN - 1e-9 <= fraction <= BONUS_MAX + 1e-9:
            return {'success': False, 'message': f"보너스 속성 수치는 {BONUS_MIN * 100:g}~{BONUS_MAX * 100:g}% 사이입니다. 다시 한 번 알려 주십시오 (예: `자성 45`)."}
        return {'success': True, 'data': self.apply_bonus_element(self.pending_bonus, element, fraction)}

    def apply_bonus_element(self, res: Dict[str, Any], element: str, fraction: float) -> Dict[str, Any]:
        """Sets the scan's Valence Bonus, remembers it for this weapon and recalculates the review."""
        w_meta = res['w_meta']
        stats = res.setdefault('stats', {})
        # In place: a waiting riven question holds the same stats and must see the bonus too.
        set_bonus(stats, element, fraction)
        self.bonus_elements[w_meta['name']] = (element, fraction)
        self.pending_bonus = None
        if self.has_pending_riven() and self.pending_riven_context.get('w_meta', {}).get('name') == w_meta['name']:
            ctx = self.pending_riven_context
            ctx['base_metrics'] = self.calculate_comprehensive_metrics(w_meta, left_stats=ctx['left_stats'], mod_objs=ctx['mod_objs'], riven_stats=None)

        mods = res.get('mod_objs') or []
        metrics = self.calculate_comprehensive_metrics(w_meta, left_stats=stats, mod_objs=mods)
        arcane = (res.get('metrics') or {}).get('arcane')
        metrics['arcane'] = arcane
        if w_meta.get('category') != 'Warframe':
            metrics['full_stack'] = self.damage_engine.compute_full_stack(w_meta, left_stats=stats, mod_objs=mods, arcane=arcane if arcane and arcane.get('modeled') else None)
        formatted = res.get('detected_mods') or []
        has_riven = any(m.get('name') == RIVEN_MOD for m in mods)
        note = f"\n\n🧪 **[보너스 속성]** {BONUS_ELEMENTS[element]} {fraction * 100:g}%를 반영했습니다."
        res.update(
            metrics=metrics,
            needs_bonus_element=False,
            message=self.format_ordis_briefing(w_meta, formatted, metrics) + (self._riven_notice() if self.has_pending_riven() else "") + note,
            review_message=self.format_mod_review_briefing(w_meta, formatted, equipped_slot_count=res.get('equipped_slot_count', len(formatted)), riven_name='리벤 모드' if has_riven else None) + note,
            calculation_breakdown=self.format_calculation_breakdown(w_meta, mods, metrics),
        )
        return res

    def _await_riven_values(self, w_meta: Dict[str, Any], left_stats: Optional[Dict[str, float]], mods: List[Dict[str, Any]], riven_name: str) -> None:
        self.pending_riven_context = {
            "w_meta": w_meta,
            "left_stats": left_stats,
            "mod_objs": mods,
            "riven_name": riven_name,
            "base_metrics": self.calculate_comprehensive_metrics(w_meta, left_stats=left_stats, mod_objs=mods, riven_stats=None)
        }

    @staticmethod
    def _riven_notice() -> str:
        return (
            f"\n\n🔮 **[세팔론 오디스 - 리벤 모드 감지 알림]**\n"
            f"오퍼레이터님! 슬롯에서 **장착된 리벤 모드**를 포착했습니다!\n"
            f"리벤 모드는 플레이어마다 고유 옵션 수치(치확/치피/피해/멀티샷 등)가 천차만별입니다.\n"
            f"💬 **리벤 수치가 어떻게 되나요?** 채팅창에 바로 입력(예: `치확 150 치피 120` 또는 `피해 165 멀샷 90`)하시거나,\n"
            f"📸 리벤 모드 팝업 창을 캡처(`F9` 또는 `Ctrl+V`)해 주시면 리벤 적용 전후 정밀 DPS를 즉시 재계산해 드리겠습니다!"
        )

    def format_ordis_briefing(self, w_meta: Dict[str, Any], detected_mods: List[str], metrics: Dict[str, Any]) -> str:
        weapon_display = f"{w_meta.get('name', '')} ({w_meta.get('kr_name', '')})" if w_meta.get('kr_name') else w_meta.get('name', '')
        mods_str = ", ".join(detected_mods) if detected_mods else "없음 (기본 순정)"

        s_dps = metrics.get("sustained_dps", 0)
        b_dps = metrics.get("burst_dps", 0)
        max_c = metrics.get("max_crit_hit", 0)
        min_h = metrics.get("min_hit", 0)

        exp_h = metrics.get("expected_hit", 0)

        is_melee = w_meta.get("category") == "Melee"
        base_title = "기본 근접 공격 (기본 화력)" if is_melee else "일반 사격 (기본 폼 화력)"
        hit_unit = "1타당 약" if is_melee else "1발당 약"

        final_ms = metrics.get("final_ms", 1.0)
        per_pellet = metrics.get("per_pellet_dmg", min_h)
        ms_min = metrics.get("ms_min_pellets", 1)
        ms_max = metrics.get("ms_max_pellets", 1)
        ms_extra = metrics.get("ms_extra_pct", 0.0)

        lines = [
            f"**[세팔론 오디스 - 하이브리드 종합 진단 리포트]**",
            f"🎯 **분석 대상 무기**: `{weapon_display}`",
            f"🧩 **감지된 모드/옵션**: {mods_str}\n",
            f"📊 **[{base_title}]**:",
            f"• **지속 평균 DPS**: `{s_dps:,.0f}`",
            f"• **순간 폭딜 (Burst DPS)**: `{b_dps:,.0f}`",
        ]

        if not is_melee and final_ms > 1.0:
            lines.extend([
                f"• **🔥 최고점 (치명타 최고 롤)**: 1사격당 약 `{max_c:,.0f}` (최대 {ms_max}발 올크리 시)",
                f"• **🎯 단발 평균 기대치**: 1사격당 약 `{exp_h:,.0f}` (평균 {final_ms:.1f}발 발사)",
                f"• **🛡️ 최저점 (비크리 최저 보장)**: 1사격당 약 `{min_h:,.0f}` (최소 {ms_min}발 확정 적중 시)",
                f"• **💥 멀티샷 구조**: 총 `{final_ms:.1f}발` (최소 `{ms_min}발` 확정 / `{ms_extra:.0f}%` 확률로 `{ms_max}발` 발사, 발사체당 순수 `{per_pellet:,.1f}` 피해)",
            ])
        else:
            lines.extend([
                f"• **🔥 최고점 (치명타 최고 롤)**: {hit_unit} `{max_c:,.0f}`",
                f"• **🎯 단발 평균 기대치**: {hit_unit} `{exp_h:,.0f}`",
                f"• **🛡️ 최저점 (비크리 최저 보장)**: {hit_unit} `{min_h:,.0f}`",
            ])

        if not is_melee:
            hs_max = metrics.get("headshot_max_crit_hit", max_c)
            # Right after the body-shot peak line (always the first line added above).
            lines.insert(7, f"• **🎯 헤드샷 최고점 (약점 치명타 최고 롤)**: `{hs_max:,.0f}` (약점 배율 {metrics.get('wp_mult', 3.0):.2f}배 × 헤드크리 2배, 약점 치확 {metrics.get('final_cc_wp', 0.0) * 100:.0f}%)")
            if metrics.get("lock_multishot"):
                lines.append(f"• **🔒 멀티샷 고정**: 어큐이티(Acuity) 장착으로 멀티샷이 기본값 `{final_ms:.1f}발`로 고정되어 멀티샷 모드가 적용되지 않습니다.")

        if metrics.get("incarnon"):
            inc = metrics["incarnon"]
            trait = self.get_incarnon_trait_description(w_meta.get('name', ''), inc.get("attack_meta"))
            lines.append(f"\n🌀 **[인카논 변신 폼 (Incarnon Genesis)]**:")
            lines.append(f"• **변신 순간 폭딜**: 약 `{inc.get('burst_dps', 0):,.0f} DPS`")
            lines.append(f"• **인카논 단발 기대치**: 1발당 약 `{inc.get('expected_hit', 0):,.0f}`")
            lines.append(f"• **특성**: {trait}")

        if metrics.get("energy_disk"):
            ed = metrics["energy_disk"]
            lines.append(f"\n🌀 **[고유 특성: 회전 에너지 디스크 (Energy Disk)]**:")
            lines.append(f"• **슬라이드 강공격 투사체 피해**: 약 `{ed.get('damage', 0):,.0f}` (지속 회전 다단히트)")

        if metrics.get("innate"):
            lines.append(f"\n🧬 **[고유 특성]**:")
            lines.extend(f"• {line}" for line in metrics["innate"])

        if metrics.get("radial"):
            rad = metrics["radial"]
            if is_melee:
                lines.append(f"\n🔨 **[지면 강타 충격파 (Slam Radial)]**:")
                lines.append(f"• **강타 충격파 단발**: 약 `{rad.get('base_damage', 0):,.0f}`")
            else:
                lines.append(f"\n💥 **[범위 폭발 피해 (Radial AoE)]**:")
                lines.append(f"• **폭발 단발 피해**: 약 `{rad.get('base_damage', 0):,.0f}`")

        if metrics.get("heavy"):
            hev = metrics["heavy"]
            lines.append(f"\n⚔️ **[근접 강공격 (Heavy Attack)]**:")
            lines.append(f"• **강공격 최고 단발**: 약 `{hev.get('heavy_hit', 0):,.0f}`")

        if metrics.get("hunter_munitions"):
            hm = metrics["hunter_munitions"]
            lines.append(f"\n🩸 **[헌터 뮤니션즈 트루 대미지]**:")
            lines.append(f"• **크리티컬 베기 틱**: 틱당 약 `{hm.get('bleed_tick', 0):,.0f}` (방어력 100% 무시!)")

        if metrics.get("arcane"):
            arc = metrics["arcane"]
            arc_note = "풀스택에 반영" if arc.get("modeled") else "효과 수치 미등록, 계산 미반영"
            lines.append(f"\n✨ **장착 아케인**: {arc.get('kr_name', arc.get('name'))} ({arc_note})")

        if metrics.get("full_stack") and metrics["full_stack"].get("assumptions"):
            fs = metrics["full_stack"]
            lines.append(f"\n🔥 **[조건부 버프 풀스택 추정 ({', '.join(fs['assumptions'])})]**:")
            lines.append(f"• **순간 폭딜**: 약 `{fs.get('burst_dps', 0):,.0f} DPS`")
            if fs.get("headshot_burst_dps"):
                lines.append(f"• **치명타 헤드샷 폭딜 (약점 3배)**: 약 `{fs['headshot_burst_dps']:,.0f} DPS`")
            if fs.get("heavy_hit"):
                lines.append(f"• **강공격 기대 단발**: 약 `{fs['heavy_hit']:,.0f}`")

        lines.extend(self._format_elements(metrics))

        if not metrics.get("used_panel_total", True):
            lines.append("\n⚠️ **참고**: 좌측 패널의 총계를 읽지 못해 코덱스 수치와 인식된 모드로 추정한 값입니다. 패널을 스크롤해 총계가 보이게 다시 캡처하면 더 정확합니다.")
        lines.append(f"\n💬 **오디스의 한마디**: 오퍼레이터님, 계산을 마쳤습니다! 전장을 찢어발기십시오!")
        return "\n".join(lines)

    def parse_stats(self, ocr_text: str) -> Dict[str, Any]:
            result = {
                "weapon": None,
                "weapon_meta": None,
                "stats": {},
                "detected_mods": [],
                "mod_entries": [],
                "raw_lines": [line.strip() for line in ocr_text.splitlines() if line.strip()]
            }
        
            # Sanitize OCR text
            sanitized_text = re.sub(r'(?<=\d)O(?=\d)', '0', ocr_text)
            sanitized_text = re.sub(r'(?<=\d)(l|I)(?=\d)', '1', sanitized_text)
            sanitized_text = re.sub(r',(?=\d)', '.', sanitized_text)
            sanitized_text = re.sub(r'\s*%\s*', '%', sanitized_text)
            sanitized_text = re.sub(r'\s*\.\s*', '.', sanitized_text)
        
            # 1. Weapon Detection (Line by line, then full text)
            if hasattr(self, 'indexer') and self.indexer:
                for line_str in result["raw_lines"]:
                    matched_w = self.indexer.fuzzy_match_weapon(line_str)
                    if matched_w:
                        result["weapon"] = matched_w['name']
                        result["weapon_meta"] = matched_w
                        break
            
                if not result["weapon"]:
                    matched_w = self.indexer.fuzzy_match_weapon(sanitized_text)
                    if matched_w:
                        result["weapon"] = matched_w['name']
                        result["weapon_meta"] = matched_w

                # 2. Extract mods using weapon category filter
                weapon_cat = result["weapon_meta"].get("category") if result["weapon_meta"] else None
                if hasattr(self, 'indexer') and self.indexer:
                    extracted_mods = self.indexer.extract_all_mods(sanitized_text, weapon_category=weapon_cat)
                    result["mod_entries"] = extracted_mods
                    result["detected_mods"] = [m.get("kr_name") or m.get("name") for m in extracted_mods]

                # 3. Extract numerical stats (Riven or UI numbers e.g. +145% 피해, +90% 멀티샷)
                for line_str in result["raw_lines"]:
                    num_match = re.search(r'([+-]?\d+(?:\.\d+)?)\s*(%?)', line_str)
                    if num_match:
                        raw_val = float(num_match.group(1))
                        percent = num_match.group(2) == '%'
                        for stat_key, patterns in self.STAT_PATTERNS.items():
                            if any(re.search(p, line_str, re.IGNORECASE) for p in patterns):
                                if stat_key == 'initial_combo':
                                    result["stats"][stat_key] = raw_val
                                elif percent:
                                    result["stats"][stat_key] = raw_val / 100.0
                                    if stat_key == 'elemental_damage':
                                        element = next((el for el, pat in (('heat', r'화염|heat'), ('cold', r'냉기|cold'), ('electric', r'전기|electricity'), ('toxin', r'독성|toxin')) if re.search(pat, line_str, re.IGNORECASE)), None)
                                        if element:
                                            result["stats"][element] = raw_val / 100.0
                                else:
                                    result["stats"][stat_key] = raw_val
                                break

            return result

    def _detect_screen_layout(self, img) -> Tuple[bool, int, int]:
        w, h = img.size
        ar = w / float(h) if h > 0 else 1.77
        bottom_crop = img.crop((int(w * 0.10), int(h * 0.62), int(w * 0.90), h))
        b_text = self.ocr_image(bottom_crop)
        inventory_keywords = ["해제", "튜토리얼", "정렬", "중복", "미보유", "호환", "모드 융합", "변환", "수용량 잔여", "장착"]
        has_inv_keywords = any(k in b_text for k in inventory_keywords)
        b_lines = [l for l in b_text.splitlines() if l.strip()]
        is_fullscreen = has_inv_keywords or (ar < 1.9 and len(b_lines) >= 3 and not ("모두 표시" in b_text and len(b_lines) <= 2))

        if is_fullscreen and ar > 1.85:
            target_w = int(h * (16.0 / 9.0))
            offset_x = max(0, int((w - target_w) / 2))
            base_w = target_w
        else:
            offset_x = 0
            base_w = w
        return is_fullscreen, offset_x, base_w

    def crop_and_ocr_mod_slots(self, img, category=None) -> Dict[str, Any]:
        if isinstance(img, str):
            img = Image.open(img)
        w, h = img.size

        yolo_used = False
        slot_boxes = []
        equipped_slot_count = 0

        is_fullscreen, offset_x, base_w = self._detect_screen_layout(img)
        ar = w / float(h) if h > 0 else 1.77
        min_slots = 7 if (not is_fullscreen and (h < 550 or ar >= 2.0)) else 4

        if self.yolo_detector and self.yolo_detector.is_available():
            try:
                layout = self.yolo_detector.detect_layout(img)
                if layout.get("total_detected", 0) >= min_slots:
                    for s_name in ["AuraStance", "Exilus"]:
                        s_info = layout.get("special_slots", {}).get(s_name)
                        if s_info and s_info.get("box"):
                            slot_boxes.append((s_name, s_info["box"], s_info.get("is_empty", False), s_info.get("is_riven", False)))
                    for k in sorted(layout.get("main_slots", {}).keys()):
                        s_info = layout["main_slots"][k]
                        if s_info and s_info.get("box"):
                            slot_boxes.append((k, s_info["box"], s_info.get("is_empty", False), s_info.get("is_riven", False)))
                    if len(slot_boxes) >= min_slots:
                        yolo_used = True
                        equipped_slot_count = layout.get("equipped_slot_count", 0)
            except Exception:
                yolo_used = False

        if not yolo_used:
            ar = w / float(h) if h > 0 else 1.77
            # Case 1: Tight crop of 8 mod slots (2 rows x 4 columns)
            if (2.0 <= ar <= 5.0 and not is_fullscreen) or (not is_fullscreen and h < 550 and ar >= 1.8):
                cw = w / 4.0
                rh = h / 2.0
                raw_boxes = [
                    ("R1_C1", (int(0 * cw), int(0 * rh), int(1 * cw), int(1 * rh))),
                    ("R1_C2", (int(1 * cw), int(0 * rh), int(2 * cw), int(1 * rh))),
                    ("R1_C3", (int(2 * cw), int(0 * rh), int(3 * cw), int(1 * rh))),
                    ("R1_C4", (int(3 * cw), int(0 * rh), int(4 * cw), int(1 * rh))),
                    ("R2_C1", (int(0 * cw), int(1 * rh), int(1 * cw), int(2 * rh))),
                    ("R2_C2", (int(1 * cw), int(1 * rh), int(2 * cw), int(2 * rh))),
                    ("R2_C3", (int(2 * cw), int(1 * rh), int(3 * cw), int(2 * rh))),
                    ("R2_C4", (int(3 * cw), int(1 * rh), int(4 * cw), int(2 * rh))),
                ]
            elif 1.1 <= ar < 2.0 and not is_fullscreen and h < 750:
                # 3-row crop: top row (Aura/Exilus) ~ 28%, bottom 2 rows (8 main slots) ~ 72%
                top_h = int(h * 0.28)
                main_h = h - top_h
                cw = w / 4.0
                rh = main_h / 2.0
                raw_boxes = [
                    ("AuraStance", (int(w * 0.40), 0, int(w * 0.65), top_h)),
                    ("Exilus", (int(w * 0.70), 0, int(w * 0.95), top_h)),
                    ("R1_C1", (int(0 * cw), top_h + int(0 * rh), int(1 * cw), top_h + int(1 * rh))),
                    ("R1_C2", (int(1 * cw), top_h + int(0 * rh), int(2 * cw), top_h + int(1 * rh))),
                    ("R1_C3", (int(2 * cw), top_h + int(0 * rh), int(3 * cw), top_h + int(1 * rh))),
                    ("R1_C4", (int(3 * cw), top_h + int(0 * rh), int(4 * cw), top_h + int(1 * rh))),
                    ("R2_C1", (int(0 * cw), top_h + int(1 * rh), int(1 * cw), top_h + int(2 * rh))),
                    ("R2_C2", (int(1 * cw), top_h + int(1 * rh), int(2 * cw), top_h + int(2 * rh))),
                    ("R2_C3", (int(2 * cw), top_h + int(1 * rh), int(3 * cw), top_h + int(2 * rh))),
                    ("R2_C4", (int(3 * cw), top_h + int(1 * rh), int(4 * cw), top_h + int(2 * rh))),
                ]
            elif ar < 1.0 and not is_fullscreen:
                # Single mod crop (e.g. Riven card)
                raw_boxes = [("R1_C1", (0, 0, w, h))]
            elif not is_fullscreen:
                raw_boxes = [
                    ("Stance", (offset_x + int(base_w * 0.48), int(h * 0.20), offset_x + int(base_w * 0.65), int(h * 0.42))),
                    ("R1_C1", (offset_x + int(base_w * 0.26), int(h * 0.43), offset_x + int(base_w * 0.42), int(h * 0.68))),
                    ("R1_C2", (offset_x + int(base_w * 0.41), int(h * 0.43), offset_x + int(base_w * 0.57), int(h * 0.68))),
                    ("R1_C3", (offset_x + int(base_w * 0.56), int(h * 0.43), offset_x + int(base_w * 0.72), int(h * 0.68))),
                    ("R1_C4", (offset_x + int(base_w * 0.71), int(h * 0.43), offset_x + int(base_w * 0.87), int(h * 0.68))),
                    ("R2_C1", (offset_x + int(base_w * 0.26), int(h * 0.68), offset_x + int(base_w * 0.42), int(h * 0.94))),
                    ("R2_C2", (offset_x + int(base_w * 0.41), int(h * 0.68), offset_x + int(base_w * 0.57), int(h * 0.94))),
                    ("R2_C3", (offset_x + int(base_w * 0.56), int(h * 0.68), offset_x + int(base_w * 0.72), int(h * 0.94))),
                    ("R2_C4", (offset_x + int(base_w * 0.71), int(h * 0.68), offset_x + int(base_w * 0.87), int(h * 0.94))),
                ]
            else:
                raw_boxes = [
                    ("Stance", (offset_x + int(base_w * 0.53), int(h * 0.17), offset_x + int(base_w * 0.67), int(h * 0.27))),
                    ("R1_C1", (offset_x + int(base_w * 0.33), int(h * 0.29), offset_x + int(base_w * 0.47), int(h * 0.42))),
                    ("R1_C2", (offset_x + int(base_w * 0.47), int(h * 0.29), offset_x + int(base_w * 0.60), int(h * 0.42))),
                    ("R1_C3", (offset_x + int(base_w * 0.60), int(h * 0.29), offset_x + int(base_w * 0.73), int(h * 0.42))),
                    ("R1_C4", (offset_x + int(base_w * 0.73), int(h * 0.29), offset_x + int(base_w * 0.87), int(h * 0.42))),
                    ("R2_C1", (offset_x + int(base_w * 0.33), int(h * 0.42), offset_x + int(base_w * 0.47), int(h * 0.55))),
                    ("R2_C2", (offset_x + int(base_w * 0.47), int(h * 0.42), offset_x + int(base_w * 0.60), int(h * 0.55))),
                    ("R2_C3", (offset_x + int(base_w * 0.60), int(h * 0.42), offset_x + int(base_w * 0.73), int(h * 0.55))),
                    ("R2_C4", (offset_x + int(base_w * 0.73), int(h * 0.42), offset_x + int(base_w * 0.87), int(h * 0.55))),
                ]
            slot_boxes = [(name, box, False) for name, box in raw_boxes]

        slot_results = []
        scale = 3 if not is_fullscreen else 2
        for item in slot_boxes:
            slot_name, box = item[0], item[1]
            is_empty = item[2] if len(item) > 2 else False
            is_riven_slot = item[3] if len(item) > 3 else False
            if is_empty:
                slot_results.append((slot_name, ""))
                continue

            crop = img.crop(box)
            if not yolo_used:
                gray_arr = np.array(crop.convert('L'))
                std_val = float(np.std(gray_arr))
                bright_ratio = float(np.mean(gray_arr > 150))
                if slot_name != 'Stance' and std_val > 28.0 and bright_ratio > 0.02:
                    equipped_slot_count += 1

            t_raw = self.ocr_image(crop)
            up = crop.resize((crop.width * scale, crop.height * scale), Image.Resampling.LANCZOS)
            t_up = self.ocr_image(up)
            gray = up.convert('L')
            bin_img = gray.point(lambda x: 255 if x > 135 else 0, mode='1')
            t_bin = self.ocr_image(bin_img.convert('L'))

            # Dedicated title strip OCR (focuses on mod name, avoids card art)
            ch = crop.height
            strip = crop.crop((0, int(ch * 0.12), crop.width, int(ch * 0.65)))
            t_str1 = self.ocr_image(strip)
            t_str2 = self.ocr_image(strip.resize((strip.width * 2, strip.height * 2), Image.Resampling.LANCZOS))
            t_str3 = self.ocr_image(strip.resize((strip.width * 3, strip.height * 3), Image.Resampling.LANCZOS))

            # White-text mask variants: remove card-art background so WinRT OCR reads the title cleanly
            norm_texts = []
            mask_scale = 2.0 if crop.width < 400 else 1.0
            tall_strip = crop.crop((0, int(ch * 0.10), crop.width, int(ch * 0.85)))
            for m_src, thr in ((strip, 205), (strip, 220), (strip, 190), (tall_strip, 205), (tall_strip, 220)):
                m_arr = (np.array(m_src.convert('RGB')).min(axis=2) >= thr).astype(np.uint8) * 255
                m_img = Image.fromarray(255 - m_arr).convert('L')
                m_img = m_img.resize((max(8, int(m_img.width * mask_scale)), max(8, int(m_img.height * mask_scale))), Image.Resampling.LANCZOS)
                m_img = ImageOps.expand(m_img, border=20, fill=255).convert('RGB')
                norm_texts.append(self.ocr_image(m_img))

            combined_text = f'{t_raw} ||| {t_up} ||| {t_bin} ||| {t_str1} ||| {t_str2} ||| {t_str3} ||| ' + ' ||| '.join(norm_texts)
            combined_text = combined_text.strip()
            if is_riven_slot:
                combined_text = f"리벤 riven {combined_text}".strip()
            combined_text = re.sub(r'유니신1?ズ|컨터유니션즈|헌터\s*유니션즈|건터\s*유니션즈', '헌터 뮤니션즈', combined_text)
            combined_text = re.sub(r'[人入ㅅ2]\s*코\s*[프끄豇표고*虹]?|코고', '스코프', combined_text)
            combined_text = re.sub(r'갈[Bb]|르晷나|聖나|[가-힣\?]?바나이즈[드뚜S]?|갈[dH]\s*나이즈드|(?<!갈바)나이즈드|길바나이즈드|결구', '갈바나이즈드', combined_text)
            combined_text = re.sub(r'보래E?C[öo]ltatak|Crit[uüäöa-zQ]*tak|Crltatak', '브래튼 Critatak', combined_text, flags=re.I)
            combined_text = re.sub(r'\b라임드슈레드\b', '프라임드 슈레드', combined_text)
            combined_text = re.sub(r'[효크目å됴뇨]\s*라이\s*[오으호]?', '크라이오', combined_text)
            combined_text = re.sub(r'어큐이(?:EI|E\||디|터|티)', '어큐이티', combined_text)
            combined_text = re.sub(r'(?:프라[함림럼힘]|표라임|교라임|노라임|노라이드|缸라임)(?:드|c|대|大)?', '프라임드', combined_text)
            combined_text = re.sub(r'(?:^|\s)(?:라임드|l임드|부라임드|꾸라임드|가임드)', ' 프라임드', combined_text)
            combined_text = re.sub(r'(?:[눔푼][안인]트|폴[험헠]크)', '포인트', combined_text)
            combined_text = re.sub(r'(?:블[험헠]크|붇랭크|듣랭크|블램크|뙤부햇크|뿐:푳乶크|부鬱븤)', '블랭크', combined_text)
            combined_text = re.sub(r'(?:포인트[,\s\/]*블랭크|프라임드\s*포인트|프라함드\s*눔안트|프라힘드눔안트)', '프라임드 포인트 블랭크', combined_text)
            combined_text = re.sub(r'(?:근[i|]?피[다터][국클]?립|리[`\'!]*\s*[표쪡테파]터\s*[클뒐뭫럮쭾]*|昷다하|리표터)', '리피터 클립', combined_text)
            combined_text = re.sub(r'(?:꼬건|년?사거|삿거|산거|들건|잣건)', '샷건', combined_text)
            combined_text = re.sub(r'(?:에?탐[己리\s]*\s*[자스츠]트|멘\s*탐[리\s]*[-~]?\s*[츠스]|수?엔[怍屯\s\?]*[I|화리][흐츠리&톼고주스트\-0-9]*|멘탈리[자스츠]트?|[a-zA-Z가-힣\?]*[쮸빨탈멘랼]리[츠스]트|일리엔[!빨탈]리스트|일리엔!랼리스트|리엔나리고)', '엘리멘탈리스트', combined_text)
            combined_text = re.sub(r'(?:가?전래스[그疇]?|수전하스|가~래스그|[질칠실]일\s*그래스프|자그래스)', '칠링 그래스프', combined_text)
            combined_text = re.sub(r'(?:수\(?부한|브나이[주즈][cd\.]*|令四91즈c|[깐깔길]?갈?브[테나][이즈트=]+헬|[가-힣\?!]*\s*브나이[주즈트=]+\s*헬)', '갈바나이즈드 헬', combined_text)
            combined_text = re.sub(r'(?:갈하나아[질즈]|힐바나이[죄즈]드|바나OL즈c|하나OL즈c|부반브으l들\.나|수하L@즈c|바나이즈[cd])', '갈바나이즈드', combined_text)
            combined_text = re.sub(r'갈바나이즈드\s*(?:[한할함]|헬팀|헬)', '갈바나이즈드 헬', combined_text)
            combined_text = re.sub(r'(?:[0oO]H시드|애시로|애시드\s*[월쉘][즈스]?)', '애시드 쉘즈', combined_text)
            combined_text = re.sub(r'(?:클레[-\s]*인피[-\s]*|듬레\'?Å?한[덮협]?[뉴특]?[쵸뇨1言]*|글러츠한표[규녂][료뇨][1트]*|클레-」인)', '클렌즈 인페스티드', combined_text)
            slot_results.append((slot_name, combined_text))

        return {
            "slot_results": slot_results,
            "merged_text": "\n".join(t.replace(' ||| ', ' ') for _, t in slot_results if t),
            "is_fullscreen": is_fullscreen,
            "offset_x": offset_x,
            "base_w": base_w,
            "equipped_slot_count": equipped_slot_count,
            "yolo_used": yolo_used
        }

    def extract_left_panel_stats(self, img, full_text: Optional[str] = None) -> Dict[str, float]:
            if isinstance(img, str):
                img = Image.open(img)
            stats: Dict[str, float] = {}
            rows = self._ocr_panel_rows(img) if self.preferred_ocr == 'winocr' else []

            if full_text:
                for line in full_text.splitlines():
                    m = re.match(r'^\s*([^\d+\-]+?)\s*[:=]?\s*([+\-]?\d.*)$', line)
                    if m:
                        rows.append((m.group(1), m.group(2)))

            prev_is_heavy = False
            for label, value in rows:
                compact = re.sub(r'\s+', '', label)
                if re.search(r'강공격', compact) and not value.strip():
                    prev_is_heavy = True
                    continue
                if prev_is_heavy and re.fullmatch(r'피해\W*', compact) and 'heavy_damage' not in stats:
                    parsed = self._parse_panel_value(value, 'heavy_damage')
                    if parsed is not None:
                        stats['heavy_damage'] = parsed
                    prev_is_heavy = False
                    continue
                prev_is_heavy = False

                key = self._match_panel_label(label)
                if key and key.startswith('el_') and '%' in value and ('valence_' + key[3:]) not in stats:
                    m_pct = re.search(r'(\d+(?:\.\d+)?)\s*%', value)
                    if m_pct:
                        stats['valence_' + key[3:]] = float(m_pct.group(1)) / 100.0
                    continue

                if key is None or key in stats or not value.strip():
                    continue

                parsed = self._parse_panel_value(value, key)
                if parsed is not None:
                    stats[key] = parsed

            return stats

    def calculate_comprehensive_metrics(self, w_meta: Dict[str, Any], left_stats: Optional[Dict[str, float]] = None, mod_objs: Optional[List[Dict[str, Any]]] = None, riven_stats: Optional[Dict[str, float]] = None, riven_in_panel: bool = False) -> Dict[str, Any]:
            from scripts.warframe_damage_engine import WarframeDamageEngine
            if not hasattr(self, 'damage_engine') or not self.damage_engine:
                self.damage_engine = WarframeDamageEngine()
            return self.damage_engine.compute_metrics(w_meta, left_stats=left_stats, mod_objs=mod_objs, riven_stats=riven_stats, riven_in_panel=riven_in_panel)

    def _riven_free_metrics(self, w_meta: Dict[str, Any], left_stats: Dict[str, float], mod_objs: List[Dict[str, Any]], riven_stats: Dict[str, float], fallback: Dict[str, Any]) -> Dict[str, Any]:
            # A riven-equipped screenshot already has the riven in its panel, so the "before" side must take it out.
            if not left_stats:
                return fallback
            from scripts.warframe_damage_engine import WarframeDamageEngine
            stripped = WarframeDamageEngine().strip_riven_from_panel(left_stats, w_meta, mod_objs, riven_stats)
            return self.calculate_comprehensive_metrics(w_meta, left_stats=stripped, mod_objs=mod_objs)

    def has_pending_diagnosis(self) -> bool:
        return hasattr(self, 'pending_screenshot') and self.pending_screenshot is not None

    def clear_pending_diagnosis(self) -> None:
        self.pending_screenshot = None

    def resume_pending_diagnosis(self, user_input: str) -> Dict[str, Any]:
        if not self.has_pending_diagnosis():
            return {"success": False, "message": "대기 중인 스크린샷이 없습니다."}

        clean_input = re.sub(r'^(이거|그거|저거|무기는|무기)\s*', '', user_input.strip())
        clean_input = re.sub(r'(이야|야|인데|인데요|입니다|임|요|다)$', '', clean_input).strip()
        w_meta = self.indexer.fuzzy_match_weapon(clean_input) or self.indexer.fuzzy_match_weapon(user_input)
        if not w_meta:
            return {
                "success": False,
                "invalid_weapon": True,
                "message": (
                    f"**[세팔론 오디스]** 오퍼레이터님, 말씀해 주신 '{user_input}'(으)로는 워프레임 코덱스에서 무기를 특정하지 못했습니다. 💦\n"
                    "정확한 무기 이름(예: '쿠나이', '토리드', '쿠바 구울소우' 등)으로 다시 한 번 말씀해 주십시오!"
                )
            }

        ctx = self.pending_screenshot
        img = ctx.get("img")
        self.clear_pending_diagnosis()

        res = self.diagnose_screenshot(img, forced_weapon_meta=w_meta)
        clarified_prefix = f"🎯 **[무기 확인 완료: {w_meta['name']}]** 오퍼레이터님께서 알려주신 무기 정보를 바탕으로 진단을 완료했습니다!\n\n"
        if res.get("message"):
            res["message"] = clarified_prefix + res["message"]
        if res.get("review_message"):
            res["review_message"] = clarified_prefix + res["review_message"]
        return res

    def extract_riven_stats_from_screen(self, img) -> Optional[Dict[str, float]]:
        """Read riven card stat lines (e.g. '+150% 치명타 확률') off the screen; None unless 2+ usable stats."""
        text = self.ocr_image(img)
        if not text or text.startswith("[OCR Error]"):
            return None
        stats: Dict[str, float] = {}
        for line in text.splitlines():
            parsed = parse_stat_line(line)
            if parsed is None:
                # The label sometimes comes before the value: '치명타 확률 +150%'.
                m = re.match(r"^\s*([가-힣][가-힣\s]*?)\s*([+-]\s*\d+(?:\.\d+)?)\s*%", line)
                parsed = parse_stat_line(f"{m.group(2)}% {m.group(1)}") if m else None
            if parsed and parsed.get("key"):
                stats[parsed["key"]] = parsed["value"]
        elements = [stats[e] for e in ("heat", "cold", "electric", "toxin") if e in stats]
        if elements:
            stats["elemental_damage"] = sum(elements)
        return stats if len([k for k in stats if k != "elemental_damage"]) >= 2 else None

    def has_pending_riven(self) -> bool:
        return hasattr(self, 'pending_riven_context') and self.pending_riven_context is not None

    def clear_pending_riven(self) -> None:
        self.pending_riven_context = None

    def format_riven_comparison_report(self, w_meta: Dict[str, Any], riven_name: str, riven_stats: Dict[str, float], base_metrics: Dict[str, Any], with_riven_metrics: Dict[str, Any]) -> str:
            weapon_display = f"{w_meta.get('name', '')} ({w_meta.get('kr_name', '')})" if w_meta.get('kr_name') else w_meta.get('name', '')

            stat_kr = {
                "crit_chance": "치명타 확률",
                "crit_damage": "치명타 피해",
                "multishot": "멀티샷",
                "base_damage": "피해",
                "fire_rate": "공격 속도/연사력",
                "status_chance": "상태이상 확률",
                "elemental_damage": "속성 피해",
                "heat": "화염",
                "cold": "냉기",
                "electric": "전기",
                "toxin": "독성",
                "finisher_damage": "마무리 일격 피해",
                "initial_combo": "기본 연속기"
            }

            stat_lines = []
            for k, v in riven_stats.items():
                name = stat_kr.get(k, k)
                if k == 'initial_combo':
                    stat_lines.append(f"- **{name}**: +{v:.1f} (상시 2배수 연속기 발동!)")
                else:
                    pct = v * 100.0
                    stat_lines.append(f"- **{name}**: {pct:+.1f}%")
            stats_formatted = "\n".join(stat_lines) if stat_lines else "- 고유 수치 파싱 완료"

            base_s_dps = base_metrics.get("sustained_dps", 0)
            base_b_dps = base_metrics.get("burst_dps", 0)
            base_max = base_metrics.get("max_crit_hit", 0)
            base_min = base_metrics.get("min_hit", 0)

            r_s_dps = with_riven_metrics.get("sustained_dps", 0)
            r_b_dps = with_riven_metrics.get("burst_dps", 0)
            r_max = with_riven_metrics.get("max_crit_hit", 0)
            r_min = with_riven_metrics.get("min_hit", 0)
            base_hs = base_metrics.get("headshot_max_crit_hit", base_max)
            r_hs = with_riven_metrics.get("headshot_max_crit_hit", r_max)
            hs_note = "" if w_meta.get("category") == "Melee" else f" (헤드샷: {base_hs:,.0f} ➔ **{r_hs:,.0f}**)"

            gain = ((r_s_dps - base_s_dps) / max(1, base_s_dps)) * 100.0

            return (
                f"🎯 **[세팔론 오디스 - 리벤 모드 정밀 분석 리포트]**\n"
                f"오퍼레이터님! **{weapon_display}** 전용 **리벤 모드**의 세부 수치를 완벽히 해독하여 화력 시뮬레이터에 반영했습니다!\n\n"
                f"📊 **측정된 리벤 고유 옵션**:\n{stats_formatted}\n\n"
                f"⚔️ **실전 화력 비교 (리벤 미적용 ➔ 리벤 장착)**:\n"
                f"- **지속 DPS**: {base_s_dps:,.0f} ➔ **{r_s_dps:,.0f}** ({gain:+.1f}%)\n"
                f"- **순간 DPS**: {base_b_dps:,.0f} ➔ **{r_b_dps:,.0f}**\n"
                f"- **치명타 최고점(Peak)**: {base_max:,.0f} ➔ **{r_max:,.0f}**{hs_note}\n"
                f"- **최저 데미지(Trough)**: {base_min:,.0f} ➔ **{r_min:,.0f}**\n\n"
                f"💡 **세팔론 오디스의 평가**: 리벤 모드의 스탯이 무기 기본 스펙과 증폭 연쇄를 일으켜 실전 기대 화력이 {gain:+.1f}% 강화되었습니다!"
                + "\n".join(self._format_elements(with_riven_metrics))
            )

    def resume_pending_riven(self, user_input: Union[str, Dict[str, float]]) -> Dict[str, Any]:
        if not self.has_pending_riven():
            return {'success': False, 'message': '대기 중인 리벤 모드가 없습니다.'}

        riven_stats = {}

        if isinstance(user_input, dict):
            riven_stats = dict(user_input)
        elif isinstance(user_input, str):
            parsed = self.parse_stats(user_input)
            riven_stats.update(parsed.get('stats', {}))

            pat = r'(?i)(치명타\s*확률|치확|크확|cc|ㅊㅎ|치명타\s*피해|치피|크피|cd|ㅊㅍ|멀티샷|멀샷|ms|ㅁㅅ|기본\s*피해|피해|데미지|대미지|dmg|ㅍㅎ|연사력|연사|공격\s*속도|공속|fr|ㄱㅅ|상태이상\s*확률|상확|sc|독|toxin|냉기|얼음|cold|화염|불|heat|전기|elec|속성|베기|slash|팩션|faction|탄창|mag|재장전|reload)\s*[:=+]?\s*([+-]?\d+(?:\.\d+)?)\s*%?'
            for m in re.finditer(pat, user_input):
                label = m.group(1).replace(' ', '').lower()
                val = float(m.group(2))
                if abs(val) > 3.0:
                    val = val / 100.0

                if label in ['치명타확률', '치확', '크확', 'cc', 'ㅊㅎ']:
                    riven_stats['crit_chance'] = val
                elif label in ['치명타피해', '치피', '크피', 'cd', 'ㅊㅍ']:
                    riven_stats['crit_damage'] = val
                elif label in ['멀티샷', '멀샷', 'ms', 'ㅁㅅ']:
                    riven_stats['multishot'] = val
                elif label in ['기본피해', '피해', '데미지', '대미지', 'dmg', 'ㅍㅎ']:
                    riven_stats['base_damage'] = val
                elif label in ['연사력', '연사', '공격속도', '공속', 'fr', 'ㄱㅅ']:
                    riven_stats['fire_rate'] = val
                elif label in ['상태이상확률', '상확', 'sc']:
                    riven_stats['status_chance'] = val
                elif label in ['독', 'toxin', '냉기', '얼음', 'cold', '화염', '불', 'heat', '전기', 'elec', '속성']:
                    riven_stats['elemental_damage'] = riven_stats.get('elemental_damage', 0.0) + val
                    element = {'독': 'toxin', 'toxin': 'toxin', '냉기': 'cold', '얼음': 'cold', 'cold': 'cold', '화염': 'heat', '불': 'heat', 'heat': 'heat', '전기': 'electric', 'elec': 'electric'}.get(label)
                    if element:
                        riven_stats[element] = val
                elif label in ['베기', 'slash']:
                    riven_stats['slash'] = val
                elif label in ['팩션', 'faction']:
                    riven_stats['faction_damage'] = val
                elif label in ['탄창', 'mag']:
                    riven_stats['magazine_capacity'] = val
                elif label in ['재장전', 'reload']:
                    riven_stats['reload_speed'] = val

            if not riven_stats:
                numbers = re.findall(r'[+-]?\d+(?:\.\d+)?', user_input)
                if len(numbers) >= 2:
                    v0 = float(numbers[0]) / (100.0 if abs(float(numbers[0])) > 3.0 else 1.0)
                    v1 = float(numbers[1]) / (100.0 if abs(float(numbers[1])) > 3.0 else 1.0)
                    riven_stats['crit_chance'] = v0
                    riven_stats['crit_damage'] = v1
                    if len(numbers) >= 3:
                        v2 = float(numbers[2]) / (100.0 if abs(float(numbers[2])) > 3.0 else 1.0)
                        riven_stats['multishot'] = v2

        if not riven_stats:
            return {'success': False, 'message': '리벤 수치를 인식하지 못했습니다. 예: 치확 150 치피 120 형태로 입력해 주십시오.'}

        ctx = self.pending_riven_context
        w_meta_ctx = ctx['w_meta']
        left_stats_ctx = ctx.get('left_stats', {})
        mod_objs_ctx = ctx.get('mod_objs', [])
        riven_name_ctx = ctx.get('riven_name', '리벤 모드')
        base_metrics_ctx = ctx.get('base_metrics', {})

        with_riven_metrics = self.calculate_comprehensive_metrics(w_meta_ctx, left_stats=left_stats_ctx, mod_objs=mod_objs_ctx, riven_stats=riven_stats, riven_in_panel=True)
        base_metrics_ctx = self._riven_free_metrics(w_meta_ctx, left_stats_ctx, mod_objs_ctx, riven_stats, base_metrics_ctx)
        report = self.format_riven_comparison_report(w_meta_ctx, riven_name_ctx, riven_stats, base_metrics_ctx, with_riven_metrics)
        breakdown_msg = self.format_calculation_breakdown(w_meta_ctx, mod_objs_ctx, with_riven_metrics, riven_stats=riven_stats)

        self.last_diagnosis_result = {
            'weapon': w_meta_ctx['name'],
            'w_meta': w_meta_ctx,
            'mod_objs': mod_objs_ctx,
            'metrics': with_riven_metrics,
            'message': report,
            'calculation_breakdown': breakdown_msg
        }

        self.clear_pending_riven()
        saved = self.build_store.get_build(w_meta_ctx['name'])
        if saved:
            saved['riven'] = riven_stats
            if saved.get('panel_has_riven'):
                saved['panel_riven'] = riven_stats
            self.build_store.save_build(saved)
        else:
            self.entered_rivens[w_meta_ctx['name']] = riven_stats
        return {
            'success': True,
            'is_riven_report': True,
            'weapon': w_meta_ctx['name'],
            'riven_name': riven_name_ctx,
            'riven_stats': riven_stats,
            'metrics': with_riven_metrics,
            'base_metrics': base_metrics_ctx,
            'w_meta': w_meta_ctx,
            'mod_objs': mod_objs_ctx,
            'message': report,
            'calculation_breakdown': breakdown_msg
        }

    def format_mod_review_briefing(self, w_meta: Dict[str, Any], detected_mods: List[str], equipped_slot_count: int = 8, riven_name: Optional[str] = None) -> str:
        w_name = w_meta.get('name', '')
        w_kr = w_meta.get('kr_name', '')
        weapon_display = f'{w_name} ({w_kr})' if w_kr else w_name
        rec_cnt = len(detected_mods)

        if equipped_slot_count > 0 and rec_cnt == equipped_slot_count:
            status_line = f'✅ **장착 슬롯 대조 완료**: 장착 감지된 슬롯 {equipped_slot_count}개 중 {rec_cnt}개 모두 정상 인식되었습니다! (일치율 100%)'
        elif equipped_slot_count > 0:
            status_line = f'⚠️ **[슬롯 개수 불일치 감지]**: 슬롯에 {equipped_slot_count}개의 모드가 장착된 것으로 보이나 {rec_cnt}개만 인식되었습니다! 아래 목록을 확인해 주세요.'
        else:
            status_line = f'📦 **인식된 모드 수**: {rec_cnt}개'

        mod_lines = []
        if detected_mods:
            for idx, m_str in enumerate(detected_mods, 1):
                mod_lines.append(f'  {idx}. {m_str}')
        else:
            mod_lines.append('  - (인식된 모드 없음 - 순정 상태)')

        lines = [
            '🔍 **[1단계: 무기 및 장착 모드 인식 검토]**',
            f'🎯 **인식된 무기**: {weapon_display}',
            status_line,
            '🧩 **인식된 모드 목록**:',
            *mod_lines
        ]

        if riven_name:
            lines.append(f'\n🔮 **리벤 모드 감지됨**: 리벤 고유 옵션(예: 치확 150 치피 120 또는 리벤 팝업 캡처)을 입력하시면 리벤 수치까지 함께 합산됩니다.')

        lines.append('\n💡 **인식 결과가 맞다면 아래 [✅ 인식 일치 - 데미지 계산 실행] 버튼을 눌러주십시오!**')

        return '\n'.join(lines)

    def format_calculation_breakdown(self, w_meta: Dict[str, Any], mod_objs: List[Dict[str, Any]], metrics: Dict[str, Any], riven_stats: Optional[Dict[str, float]] = None) -> str:
        w_name = w_meta.get('name', '')
        w_kr = w_meta.get('kr_name', '')
        w_disp = f'{w_name} ({w_kr})' if w_kr else w_name
        base_dmg = float(w_meta.get('total_damage', 18.0))
        base_cc = float(w_meta.get('crit_chance', 0.1))
        base_cd = float(w_meta.get('crit_mult', 1.5))
        base_fr = float(w_meta.get('fire_rate', 1.0))

        mod_dmg = 0.0
        mod_ms = 0.0
        mod_elem = 0.0
        mod_cc = 0.0
        mod_cd = 0.0
        mod_fr = 0.0
        mod_details = []

        for mod in mod_objs:
            if mod.get('name') == 'Riven Mod':
                continue
            mod_stats = [
                f"피해 +{mod.get('damage', 0.0)*100:.1f}%" if mod.get('damage', 0.0) != 0 else "",
                f"멀티샷 +{mod.get('multishot', 0.0)*100:.1f}%" if mod.get('multishot', 0.0) != 0 else "",
                f"원소 피해 +{mod.get('elemental_damage', 0.0)*100:.1f}%" if mod.get('elemental_damage', 0.0) != 0 else "",
                f"치명타 확률 +{mod.get('crit_chance', 0.0)*100:.1f}%" if mod.get('crit_chance', 0.0) != 0 else "",
                f"치명타 피해 +{mod.get('crit_damage', 0.0)*100:.1f}%" if mod.get('crit_damage', 0.0) != 0 else "",
                f"연사력 +{mod.get('fire_rate', 0.0)*100:.1f}%" if mod.get('fire_rate', 0.0) != 0 else ""
            ]
            mod_stats = [s for s in mod_stats if s]
            if mod_stats:
                mod_stats_str = ', '.join(mod_stats)
            elif 'stance' in mod.get('type', ''):
                mod_stats_str = '[스탠스]'
            else:
                mod_stats_str = '[유틸리티/효과]'

            kr_n = mod.get('kr_name')
            en_n = mod.get('name', 'Unknown Mod')
            disp_name = f"{kr_n} ({en_n})" if kr_n and kr_n != en_n else en_n
            mod_details.append(f"  - {disp_name}: {mod_stats_str}")

            mod_dmg += mod.get('damage', 0.0)
            mod_ms += mod.get('multishot', 0.0)
            mod_elem += mod.get('elemental_damage', 0.0)
            mod_cc += mod.get('crit_chance', 0.0)
            mod_cd += mod.get('crit_damage', 0.0)
            mod_fr += mod.get('fire_rate', 0.0)

        if riven_stats:
            r_stats = [
                f"피해 +{(riven_stats.get('damage', 0.0) or riven_stats.get('base_damage', 0.0))*100:.1f}%" if (riven_stats.get('damage', 0.0) or riven_stats.get('base_damage', 0.0)) != 0 else "",
                f"멀티샷 +{riven_stats.get('multishot', 0.0)*100:.1f}%" if riven_stats.get('multishot', 0.0) != 0 else "",
                f"원소 피해 +{riven_stats.get('elemental_damage', 0.0)*100:.1f}%" if riven_stats.get('elemental_damage', 0.0) != 0 else "",
                f"치명타 확률 +{riven_stats.get('crit_chance', 0.0)*100:.1f}%" if riven_stats.get('crit_chance', 0.0) != 0 else "",
                f"치명타 피해 +{riven_stats.get('crit_damage', 0.0)*100:.1f}%" if riven_stats.get('crit_damage', 0.0) != 0 else "",
                f"연사력 +{riven_stats.get('fire_rate', 0.0)*100:.1f}%" if riven_stats.get('fire_rate', 0.0) != 0 else ""
            ]
            r_stats = [s for s in r_stats if s]
            riven_stats_str = ', '.join(r_stats) if r_stats else '[옵션 미입력]'
            mod_details.append(f"  - 🔮 리벤 모드 (Riven Mod): {riven_stats_str}")

            mod_dmg += riven_stats.get('damage', 0.0) or riven_stats.get('base_damage', 0.0)
            mod_ms += riven_stats.get('multishot', 0.0)
            mod_elem += riven_stats.get('elemental_damage', 0.0)
            mod_cc += riven_stats.get('crit_chance', 0.0)
            mod_cd += riven_stats.get('crit_damage', 0.0)
            mod_fr += riven_stats.get('fire_rate', 0.0)

        final_dmg = metrics.get('final_dmg', 0)
        final_cc = metrics.get('final_cc', 0)
        final_cd = metrics.get('final_cd', 0)
        final_fr = metrics.get('final_fr', 0)
        min_hit = metrics.get('min_hit', 0)
        max_crit = metrics.get('max_crit_hit', 0)
        exp_hit = metrics.get('expected_hit', 0)
        b_dps = metrics.get('burst_dps', 0)
        s_dps = metrics.get('sustained_dps', 0)
        fs_dps = metrics.get('full_stack', {}).get('burst_dps', 0)
        inc_dps = metrics.get('incarnon', {}).get('burst_dps', 0)

        crit_avg_mult = 1.0 + final_cc * (final_cd - 1.0)
        bleed_tick = 0.35 * base_dmg * (1.0 + mod_dmg) * (1.0 + mod_ms) * crit_avg_mult

        base_ms = float(w_meta.get('base_multishot', 1.0) or w_meta.get('multishot', 1.0) or 1.0)
        final_ms = metrics.get('final_ms', 1.0)
        per_pellet = metrics.get('per_pellet_dmg', min_hit)
        ms_min = metrics.get('ms_min_pellets', 1)
        ms_max = metrics.get('ms_max_pellets', 1)
        ms_extra = metrics.get('ms_extra_pct', 0.0)
        max_non_crit = metrics.get('max_non_crit', min_hit)
        avg_non_crit = final_dmg
        is_melee = w_meta.get('category') == 'Melee'

        tot_parts = []
        if mod_dmg != 0: tot_parts.append(f"피해 {mod_dmg*100:+.1f}%")
        if mod_ms != 0: tot_parts.append(f"멀티샷 {mod_ms*100:+.1f}%")
        if mod_elem != 0: tot_parts.append(f"속성 {mod_elem*100:+.1f}%")
        if mod_cc != 0: tot_parts.append(f"치확 {mod_cc*100:+.1f}%")
        if mod_cd != 0: tot_parts.append(f"치피 {mod_cd*100:+.1f}%")
        if mod_fr != 0: tot_parts.append(f"연사/공속 {mod_fr*100:+.1f}%")
        tot_summary = " | ".join(tot_parts) if tot_parts else "보너스 없음 (순정)"

        breakdown = [
            f"1. 무기 코덱스 기본 스탯 (DB 원본)",
            f"  - 기본 피해: {base_dmg:.1f}",
            f"  - 기본 멀티샷(발사체): {base_ms:.1f}발" if not is_melee else f"  - 사거리: {w_meta.get('range', 2.5):.1f}m",
            f"  - 치명타 확률: {base_cc*100:.1f}%",
            f"  - 치명타 배수: {base_cd:.1f}",
            f"  - 연사력: {base_fr:.1f}",
            "",
            f"2. 인식된 모드 & 리벤 합산 수치 (대입값)",
            *mod_details,
            f"  ↳ 🎯 [총합 적용치]: {tot_summary}",
            "",
            f"3. 단계별 데미지 산출 공식 및 대입 흐름",
            f"  ① 최종 멀티샷 = {base_ms:.1f}발 × (1+멀티샷 모드 {mod_ms*100:+.1f}%) = {final_ms:.1f}발 (최소 {ms_min}발 확정 / {ms_extra:.0f}% 확률로 {ms_max}발 발사);" if not is_melee else f"  ① 근접 타격 판정 = {min_hit:,.1f};",
            f"  ② 순수 발사체당 피해 = {per_pellet:,.1f} (비크리 최저 {ms_min}발 적중 시 {min_hit:,.1f}, 최대 {ms_max}발 적중 시 {max_non_crit:,.1f}, 평균 총계 {avg_non_crit:,.1f});" if not is_melee else f"  ② 비크리 1타(최저점) = {min_hit:,.1f};",
            f"  ③ 치명타 최고점 = 최대 {ms_max}발 적중({max_non_crit:,.1f}) × {final_cd:.2f}배 = {max_crit:,.1f};",
            f"  ④ 기대 단발 = {avg_non_crit:,.1f} × [1 + {final_cc:.2f} × ({final_cd:.2f} - 1)] = {exp_hit:,.1f};",
            f"  ⑤ 순간 폭딜 = {exp_hit:,.1f} × {final_fr:.2f} = {b_dps:,.0f} DPS, 지속 DPS = {b_dps:,.0f} × {(s_dps / b_dps) if b_dps else 1.0:.2f} = {s_dps:,.0f} DPS;"
        ]

        if metrics.get('hunter_munitions'):
            breakdown.append(f"  ⑥ 베기 상태이상 틱딜(헌터 뮤니션즈 트루 데미지) = 0.35 × 발사체 피해({per_pellet:.1f}) × 치명타평균배율({crit_avg_mult:.2f}) = 틱당 약 {metrics['hunter_munitions'].get('bleed_tick', 0):,.1f};")

        if inc_dps > 0 or fs_dps > b_dps:
            breakdown.append(f"  ⑦ 인카논 변신 폼 및 풀스택(아케인+갈바나이즈드) 폭딜 = {fs_dps:,.0f} DPS, 인카논 폭딜 = {inc_dps:,.0f} DPS.")

        return "\n".join(breakdown)

    def _build_slot_candidates(self, w_meta: Dict[str, Any], category: str) -> List[Any]:
        from scripts.jamo_matcher import CATEGORY_MAPPING, decompose_hangul

        allowed = CATEGORY_MAPPING.get(category, [])
        w_type = (w_meta.get("type") or "").lower()
        w_type_norm = "rifle" if w_type == "assault rifle" else w_type
        ranged_classes = ["rifle", "shotgun", "bow", "sniper", "pistol"]
        candidates = []
        seen = set()
        for mod in self.indexer.mods_index.values():
            name = mod.get("name")
            if not name or name in seen or is_riven_name(name): continue
            if mod.get('is_pvp') or 'pvpmods' in str(mod.get('uniqueName', '')).lower() or mod.get('conclave'):
                continue
            m_type = str(mod.get("type", "")).lower()
            m_compat = str(mod.get("compatName", "")).lower()
            if "stance" in m_type:
                if category != "melee":
                    continue
            elif "aura" in m_type:
                if category != "warframe":
                    continue
            else:
                m_compat_norm = "rifle" if m_compat == "assault rifle" else m_compat
                # Rifle mods also fit snipers and bows; class-exclusive mods only fit their own class.
                rifle_family = m_compat_norm == "rifle" and w_type_norm in ("sniper", "bow")
                if w_type_norm in ranged_classes and m_compat_norm in ranged_classes and m_compat_norm != w_type_norm and not rifle_family:
                    continue
                # A compat naming a real weapon is that weapon's augment. An inferred weapon has no name to check.
                if m_compat in self.indexer.weapons_index and not w_meta.get("is_inferred"):
                    w_name_clean = w_meta.get("name", "").lower()
                    w_kr_clean = w_meta.get("kr_name", "").lower()
                    if m_compat not in w_name_clean and m_compat not in w_kr_clean:
                        continue
            # Exclude Arcanes from normal mod slots
            if mod.get('is_arcane') or 'arcane' in m_type or 'arcane' in m_compat:
                continue
            if any(name.startswith(p) for p in ['Primary ', 'Secondary ', 'Melee ']) and 'mod' not in m_type:
                if name in ['Primary Frostbite', 'Primary Merciless', 'Primary Deadhead', 'Primary Blight', 'Primary Crux', 'Primary Exhilarate', 'Primary Obstruct']:
                    continue

            if allowed:
                is_compat = any(cat in m_type or cat in m_compat for cat in allowed)
                if "stance" in m_type and category == "melee":
                    is_compat = True
                elif "aura" in m_type and category == "warframe":
                    is_compat = True
                if not is_compat:
                    continue
            seen.add(name)
            kr = mod.get("kr_name", "")
            if kr:
                candidates.append((decompose_hangul(kr.replace(" ", "")), kr, mod))
            candidates.append((decompose_hangul(name.lower().replace(" ", "")), name, mod))
        return candidates

    def _match_single_slot(self, s_text: str, candidates: List[Any], return_all: bool = False) -> Any:
        from scripts.jamo_matcher import decompose_hangul
        from rapidfuzz import fuzz

        # Each OCR pass is a variant, and so is each of its lines: a mod name is often clean on one line next to noise.
        raw_variants = []
        for chunk in s_text.split('|||'):
            lines = [l for l in chunk.splitlines() if l.strip()]
            if lines:
                raw_variants.append(' '.join(lines))
            if len(lines) > 1:
                raw_variants.extend(lines)
        q_jamos = []
        for v in raw_variants:
            # OCR reads the syllable 이 as 0 next to Hangul (드라0브, 나0 즈드).
            cleaned = re.sub(r'(?<=[가-힣])0+', '이', v)
            cleaned = re.sub(r'[^가-힣a-zA-Z\s]', ' ', cleaned)
            cleaned = re.sub(r'(?<![a-zA-Z])[a-zA-Z]{1,2}(?![a-zA-Z])', ' ', cleaned)
            jamo = decompose_hangul(cleaned.lower().replace(' ', '').replace('\t', ''))
            if jamo and jamo not in q_jamos:
                q_jamos.append(jamo)

        if not q_jamos:
            return [] if return_all else (None, 0.0)

        def partial_weight(cand_len: int, q_len: int) -> float:
            # A short name fully inside long noisy text proves little, so partial matches need real coverage.
            return min(1.0, 0.55 + 0.75 * cand_len / max(q_len, 1))

        prefixes = ('갈바나이즈드 ', '프라임드 ', '프라이머리 ', '세컨더리 ', '아말감 ', '새크리피셜 ', '움브랄 ', 'galvanized ', 'primed ', 'primary ', 'secondary ', 'amalgam ', 'sacrificial ', 'umbral ')
        best_mod = None
        best_score = 0.0
        matches = []

        s_low = s_text.lower()
        has_primed = any(k in s_low for k in ['프라임', '라임드', '임드', '표라임', '프래임', 'primed'])
        has_galv = any(k in s_low for k in ['갈바', '바나', '이즈드', '길바', 'galv'])
        has_amalgam = ('아말' in s_low or 'amalgam' in s_low)
        has_sacrificial = any(k in s_low for k in ['새크', '재크', '세크', '사크', '크리피', '리피셜', '리피설', 'sacrific'])

        # Faction detection in slot text
        has_infested = any(k in s_low for k in ['인페', '페스', '스티드', '감염', 'infested'])
        has_corpus = any(k in s_low for k in ['코퍼', '퍼스', 'corpus'])
        has_grineer = any(k in s_low for k in ['그리', '니어', 'grineer'])
        has_corrupted = any(k in s_low for k in ['커럽', '오로', 'corrupted'])

        for cand_jamo, cand_display, mod in candidates:
            # Skip PvP / Conclave mods
            if mod.get('is_pvp') or 'pvpmods' in str(mod.get('uniqueName', '')).lower() or mod.get('conclave'):
                continue

            disp_low = cand_display.lower()
            is_prefixed = disp_low.startswith(prefixes) and (' ' in disp_low)
            suffix_jamo = decompose_hangul(disp_low.split(' ', 1)[1].replace(' ', '')) if is_prefixed else ''
            cand_score = 0.0

            prefix_ok = True
            if is_prefixed:
                if disp_low.startswith(('프라임드 ', 'primed ')):
                    prefix_ok = has_primed
                elif disp_low.startswith(('갈바나이즈드 ', 'galvanized ')):
                    prefix_ok = has_galv
                elif disp_low.startswith(('아말감 ', 'amalgam ')):
                    prefix_ok = has_amalgam
                elif disp_low.startswith(('새크리피셜 ', 'sacrificial ')):
                    prefix_ok = has_sacrificial

            # Faction Mod Disambiguation (Cleanse, Bane, Expel, Smite)
            is_faction_mod = any(disp_low.startswith(fp) for fp in ['클렌즈 ', 'cleanse ', '베인 ', 'bane ', '익스펠 ', 'expel ', '스마이트 ', 'smite '])
            if is_faction_mod:
                mod_faction = None
                if any(w in disp_low for w in ['인페스티드', 'infested']):
                    mod_faction = 'infested'
                elif any(w in disp_low for w in ['코퍼스', 'corpus']):
                    mod_faction = 'corpus'
                elif any(w in disp_low for w in ['그리니어', 'grineer']):
                    mod_faction = 'grineer'
                elif any(w in disp_low for w in ['커럽티드', '오로킨', 'corrupted']):
                    mod_faction = 'corrupted'

                # If text has a specific faction keyword, drop mismatched faction mods
                if has_infested and mod_faction and mod_faction != 'infested':
                    continue
                if has_corpus and mod_faction and mod_faction != 'corpus':
                    continue
                if has_grineer and mod_faction and mod_faction != 'grineer':
                    continue
                if has_corrupted and mod_faction and mod_faction != 'corrupted':
                    continue

            variant_scores = []
            for q_j in q_jamos:
                r = fuzz.ratio(q_j, cand_jamo)
                if len(q_j) < 6:
                    variant_scores.append(r)
                    continue
                pr = fuzz.partial_ratio(q_j, cand_jamo) * partial_weight(len(cand_jamo), len(q_j))

                if suffix_jamo:
                    suf_pr = fuzz.partial_ratio(q_j, suffix_jamo) * partial_weight(len(suffix_jamo), len(q_j))
                    suf_r = fuzz.ratio(q_j, suffix_jamo)
                    s_val = max(r, pr * 0.90) * 0.40 + max(suf_r, suf_pr) * 0.60
                else:
                    s_val = max(r, pr * 0.90)

                variant_scores.append(s_val)

            # Agreement across OCR passes beats one lucky pass.
            variant_scores.sort(reverse=True)
            top_scores = variant_scores[:3]
            cand_score = variant_scores[0] * 0.7 + (sum(top_scores) / len(top_scores)) * 0.3
            if suffix_jamo:
                # Mods sharing a prefix are only told apart by the rest of the name.
                cand_score += (max(fuzz.ratio(q_j, suffix_jamo) for q_j in q_jamos) - 50.0) * 0.2

            if is_prefixed:
                if not prefix_ok:
                    cand_score -= 22.0
                elif prefix_ok and cand_score > 0:
                    cand_score += 8.0
            elif (has_primed or has_galv or has_amalgam or has_sacrificial) and cand_score > 0:
                # The slot shows a variant prefix, so the plain mod is less likely.
                cand_score -= 8.0

            if is_faction_mod:
                if has_infested and any(w in disp_low for w in ['인페스티드', 'infested']):
                    cand_score += 15.0
                elif has_corpus and any(w in disp_low for w in ['코퍼스', 'corpus']):
                    cand_score += 15.0
                elif has_grineer and any(w in disp_low for w in ['그리니어', 'grineer']):
                    cand_score += 15.0
                elif has_corrupted and any(w in disp_low for w in ['커럽티드', 'corrupted']):
                    cand_score += 15.0

            if return_all:
                if cand_score >= 52.0:
                    matches.append((cand_score, mod))
            elif cand_score > best_score:
                best_score = cand_score
                best_mod = mod

        if return_all:
            matches.sort(key=lambda x: x[0], reverse=True)
            return matches

        return best_mod, best_score

    def _parse_panel_value(self, text: str, key: str) -> Optional[float]:
            tokens = re.findall(r'\d[\d.,]*\d|\d', text)
            if not tokens:
                return None
            token = tokens[-1]
            has_pct = '%' in text

            try:
                parts = re.split(r'[.,]', token)
                if len(parts) == 1:
                    value = float(parts[0])
                elif len(parts) == 2:
                    if ',' in token and len(parts[1]) == 3:
                        value = float(parts[0] + parts[1])
                    elif '.' in token and len(parts[1]) >= 4:
                        value = float(parts[0] + parts[1][:3] + '.' + parts[1][3:])
                    else:
                        value = float(parts[0] + '.' + parts[1])
                elif len(parts) >= 3:
                    if len(parts[-1]) <= 2:
                        value = float(''.join(parts[:-1]) + '.' + parts[-1])
                    else:
                        value = float(''.join(parts))
                else:
                    return None

                if key in ['crit_chance', 'status_chance']:
                    if has_pct or value > 10.0:
                        value = value / 100.0
                    if not (0 < value <= 10):
                        return None
                elif key == 'crit_mult':
                    if not (1.0 <= value <= 30.0) or has_pct:
                        return None
                elif key == 'fire_rate':
                    if not (0.05 <= value <= 60.0) or has_pct:
                        return None
                elif key == 'multishot':
                    if not (1.0 <= value <= 60.0) or has_pct:
                        return None
                elif key in ['total_damage', 'slam_damage', 'slide_damage', 'heavy_damage']:
                    if not (value >= 1.0) or has_pct:
                        return None
                elif key in ['reload_time', 'charge_time']:
                    if not (0.05 <= value <= 30.0) or has_pct:
                        return None
                elif key == 'magazine':
                    if not (1.0 <= value <= 5000.0) or has_pct:
                        return None
                elif key.startswith('el_'):
                    if not (value >= 0.1) or has_pct:
                        return None

                return value
            except ValueError:
                return None

    def _match_panel_label(self, label: str) -> Optional[str]:
            s = re.sub(r'\s+', '', label)
            if re.search(r'범위', s):
                return None
            if re.search(r'[치지]명타?[확라학하]|critchance', s, re.I):
                return 'crit_chance'
            if re.search(r'[치지]명타?[피배]|critdam|critmult', s, re.I):
                return 'crit_mult'
            if re.search(r'상[태대]이상|status', s, re.I):
                return 'status_chance'
            if re.search(r'[멀밀일][티터E]샷?|multishot', s, re.I):
                return 'multishot'
            if re.search(r'연사|공격속도|공속|firerate|attackspeed', s, re.I):
                return 'fire_rate'
            if re.fullmatch(r'[총송출종충]계\W*', s) or re.search(r'총피해|totaldamage', s, re.I):
                return 'total_damage'
            if re.search(r'지[면연]강?타?공격|slam', s, re.I):
                return 'slam_damage'
            if re.search(r'슬라이드|slide', s, re.I):
                return 'slide_damage'
            if re.search(r'재장전|reload', s, re.I):
                return 'reload_time'
            if re.search(r'탄창|magazine', s, re.I):
                return 'magazine'
            if re.search(r'충전시간|chargetime', s, re.I):
                return 'charge_time'
            return self._match_element_label(s)

    def _format_elements(self, metrics: Dict[str, Any]) -> List[str]:
            el = metrics.get('elements')
            if not el or not el.get('types'):
                return []

            kr = {
                'heat': '화염', 'cold': '냉기', 'electric': '전기', 'toxin': '독성',
                'blast': '폭발', 'radiation': '방사능', 'gas': '가스', 'magnetic': '자성',
                'viral': '바이러스', 'corrosive': '부식', 'impact': '충격', 'puncture': '관통', 'slash': '베기'
            }
            faction_kr = {
                'grineer': '그리니어', 'corpus': '코퍼스', 'infested': '인페스티드', 'orokin': '오로킨',
                'sentient': '센티언트', 'narmer': '나르메르', 'murmur': '머머'
            }

            lines = ['\n🧪 **[속성 합성 (슬롯 순서: 좌상단 → 우하단)]**:']
            if el.get('pairs'):
                for a, b, name in el.get('pairs', []):
                    lines.append(f"• {kr.get(a, a)} + {kr.get(b, b)} → **{kr.get(name, name)}**")
            else:
                lines.append('• 합성 없음')

            if not el.get('order_known', True):
                lines.append('⚠️ 일부 모드의 슬롯 위치를 확인하지 못해 합성 순서가 다를 수 있습니다.')

            suffix = {'panel': ' (패널 실측)', 'panel_partial': ' (패널 일부 + 계산값)'}.get(el.get('source'), ' (계산값)')
            if el.get('first_attack_only') and el.get('source') == 'computed':
                suffix += ' - 첫 공격 모드 기준'
            lines.append(f"\n📐 **타입별 피해{suffix}**:")
            for t, d in sorted(el['types'].items(), key=lambda item: item[1], reverse=True):
                lines.append(f"• {kr.get(t, t)}: `{d:,.1f}` ({el['shares'].get(t, 0) * 100:.0f}%)")

            burst = metrics.get('burst_dps', 0)
            fm = el.get('faction_multipliers') or {}
            if fm:
                lines.append('\n🎯 **진영별 순간 폭딜 (방어력 제외)**:')
                for f, m in sorted(fm.items(), key=lambda item: item[1], reverse=True):
                    lines.append(f"• {faction_kr.get(f, f)}: `{burst * m:,.0f}` (×{m:.2f})")

            return lines

    def _match_element_label(self, s: str) -> Optional[str]:
            patterns = [
                (r'방사능|radiation', 'el_radiation'),
                (r'바이러스|viral', 'el_viral'),
                (r'부식|corrosive', 'el_corrosive'),
                (r'자성|magnetic', 'el_magnetic'),
                (r'폭발|blast', 'el_blast'),
                (r'가스|gas', 'el_gas'),
                (r'화염|heat', 'el_heat'),
                (r'냉기|cold', 'el_cold'),
                (r'전기|electricity', 'el_electric'),
                (r'독성|toxin', 'el_toxin'),
                (r'충격|impact', 'el_impact'),
                (r'관통|puncture', 'el_puncture'),
                (r'베기|slash', 'el_slash')
            ]
            for pattern, label in patterns:
                if re.search(pattern, s, re.I):
                    return label
            return None

    def _detect_arcane(self, img, category: Optional[str]) -> Optional[Dict[str, Any]]:
        from rapidfuzz import fuzz
        from pathlib import Path
        import json

        if winocr is None or category not in ('Primary', 'Secondary', 'Melee'):
            return None

        w, h = img.size
        crop = img.convert('RGB').crop((int(w * 0.72), int(h * 0.08), w, int(h * 0.42)))
        crop = crop.resize((crop.width * 3, crop.height * 3), Image.LANCZOS)
        text = self.ocr_image(crop)
        norm = re.sub(r'\s+', '', text).lower()
        if not norm:
            return None

        prefix = category.lower()
        candidates = {}
        for entry in self.indexer.mods_index.values():
            if entry.get('is_arcane') and entry.get('kr_name') and str(entry.get('name', '')).lower().startswith(prefix):
                candidates[entry['kr_name']] = entry['name']

        best_score = 0
        best_candidate = None
        for candidate in candidates:
            score = fuzz.partial_ratio(re.sub(r'\s+', '', candidate).lower(), norm)
            if score > best_score:
                best_score = score
                best_candidate = candidate

        if best_score < 88:
            return None

        return self._arcane_info(candidates[best_candidate])

    def _arcane_info(self, name: Optional[str]) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        try:
            path = Path(__file__).resolve().parent.parent / 'data' / 'arcane_effects.json'
            effects = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            effects = {}
        eff = effects.get(name)
        kr_name = (self.indexer.mods_index.get(name.lower()) or {}).get('kr_name', name)
        return dict(name=name, kr_name=kr_name, modeled=eff is not None, **(eff or dict()))

    # --- Saved builds ---

    def result_slots(self, res: Dict[str, Any]) -> Dict[str, str]:
        slots = {}
        for mod in res.get('mod_objs') or []:
            slot = canonical_slot(mod.get('slot_name'), mod)
            if slot and slot not in slots:
                slots[slot] = mod['name']
        return slots

    def save_scanned_build(self, res: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        w_meta = res.get('w_meta') or {}
        if not w_meta.get('name') or w_meta.get('is_inferred'):
            return None
        slots = self.result_slots(res)
        arcane = (res.get('metrics') or {}).get('arcane') or {}
        build = {
            'weapon': w_meta['name'],
            'kr_name': w_meta.get('kr_name', ''),
            'category': w_meta.get('category', ''),
            'slots': slots,
            'extra': [m['name'] for m in res.get('mod_objs') or [] if m['name'] not in slots.values()],
            'arcane': arcane.get('name'),
            'panel': res.get('stats') or {},
            # A scanned panel already contains an equipped riven, even before its values are known.
            'panel_has_riven': RIVEN_MOD in slots.values(),
            'panel_riven': None,
            'panel_removed': [],
            'riven': None,
        }
        entered = self.entered_rivens.pop(w_meta['name'], None)
        if entered and build['panel_has_riven']:
            build['riven'] = entered
            build['panel_riven'] = entered
        self.build_store.save_build(build)
        return build

    def _resolve_build_mods(self, build: Dict[str, Any]) -> List[Dict[str, Any]]:
        mods = []
        for slot, name in build.get('slots', {}).items():
            if name == RIVEN_MOD:
                mods.append({'name': RIVEN_MOD, 'kr_name': '리벤 모드', 'slot_name': slot, 'slot_index': slot_order(slot)})
            else:
                mods.append(dict(self.indexer.mods_index.get(name.lower()) or {'name': name}, slot_name=slot, slot_index=slot_order(slot)))
        for name in build.get('extra', []):
            mods.append(dict(self.indexer.mods_index.get(name.lower()) or {'name': name}))
        return mods

    def _panel_without_changes(self, build: Dict[str, Any], w_meta: Dict[str, Any], mods: List[Dict[str, Any]], riven_in_panel: Optional[Dict[str, float]]) -> Dict[str, float]:
        """The scanned panel with mods removed since the scan, and the riven it contained, taken out."""
        left = dict(build.get('panel') or {})
        if not left:
            return left
        self.calculate_comprehensive_metrics(w_meta)
        others = [m for m in mods if m.get('name') != RIVEN_MOD]
        for name in build.get('panel_removed', []):
            left = self.damage_engine.strip_riven_from_panel(left, w_meta, others, self.indexer.mods_index.get(name.lower()) or {})
        if riven_in_panel:
            left = self.damage_engine.strip_riven_from_panel(left, w_meta, others, riven_in_panel)
        return left

    def _evaluate_build(self, w_meta: Dict[str, Any], left: Dict[str, float], mods: List[Dict[str, Any]], build: Optional[Dict[str, Any]], riven: Optional[Dict[str, float]], riven_in_panel: bool = False) -> Dict[str, Any]:
        metrics = self.calculate_comprehensive_metrics(w_meta, left_stats=left, mod_objs=mods, riven_stats=riven, riven_in_panel=riven_in_panel)
        arcane = self._arcane_info((build or {}).get('arcane'))
        # With the riven already in the panel, adding it to the full-stack base would count it twice.
        metrics['full_stack'] = self.damage_engine.compute_full_stack(
            w_meta, left_stats=left, mod_objs=mods,
            arcane=arcane if arcane and arcane.get('modeled') else None,
            riven_stats=None if riven_in_panel else riven
        )
        return metrics

    def evaluate_saved_build(self, build: Dict[str, Any]) -> Dict[str, Any]:
        w_meta = self.indexer.weapons_index.get(build['weapon'].lower()) or {'name': build['weapon']}
        mods = self._resolve_build_mods(build)
        # An equipped riven with unknown values can only be read as part of the panel.
        if build.get('panel_has_riven') and not build.get('panel_riven'):
            return self._evaluate_build(w_meta, self._panel_without_changes(build, w_meta, mods, None), mods, build, None)
        left = self._panel_without_changes(build, w_meta, mods, build.get('panel_riven'))
        return self._evaluate_build(w_meta, left, mods, build, build.get('riven'))

    def apply_slot_edits(self, res: Dict[str, Any], edits: Dict[str, str]) -> Dict[str, Any]:
        """Replace recognized mods with the user's corrections and recalculate the review."""
        w_meta = res['w_meta']
        mods = []
        for slot, name in edits.items():
            if slot == 'arcane' or not name:
                continue
            if is_riven_name(name):
                mods.append({'name': RIVEN_MOD, 'kr_name': '리벤 모드', 'slot_name': slot, 'slot_index': slot_order(slot)})
            else:
                mods.append(dict(self.indexer.mods_index.get(name.lower()) or {'name': name}, slot_name=slot, slot_index=slot_order(slot)))
        mods.sort(key=lambda m: m['slot_index'])
        has_riven = any(m['name'] == RIVEN_MOD for m in mods)
        if has_riven:
            # A riven added by hand needs its values asked for, just like one the scan found.
            self._await_riven_values(w_meta, res.get('stats'), mods, '리벤 모드')
        else:
            self.clear_pending_riven()
            self.entered_rivens.pop(w_meta['name'], None)

        metrics = self.calculate_comprehensive_metrics(w_meta, left_stats=res.get('stats'), mod_objs=mods)
        arcane = self._arcane_info(edits.get('arcane')) if 'arcane' in edits else metrics.get('arcane') or (res.get('metrics') or {}).get('arcane')
        metrics['arcane'] = arcane
        metrics['full_stack'] = self.damage_engine.compute_full_stack(w_meta, left_stats=res.get('stats'), mod_objs=mods, arcane=arcane if arcane and arcane.get('modeled') else None)
        formatted = [f"{m.get('kr_name', m['name'])} ({m['name']})" for m in mods]
        res.update(
            mod_objs=mods,
            metrics=metrics,
            detected_mods=formatted,
            recognized_mod_count=len(formatted),
            equipped_slot_count=len(formatted),
            message=self.format_ordis_briefing(w_meta, formatted, metrics) + (self._riven_notice() if has_riven else ""),
            review_message=self.format_mod_review_briefing(w_meta, formatted, equipped_slot_count=len(formatted), riven_name='리벤 모드' if has_riven else None),
            calculation_breakdown=self.format_calculation_breakdown(w_meta, mods, metrics),
        )
        return res

    def mod_choices(self, w_meta: Dict[str, Any]) -> List[Any]:
        """(display name, mod name) pairs for the slot editor."""
        category = (w_meta.get('category') or '').lower()
        seen, choices = set(), []
        for _, _, mod in self._build_slot_candidates(w_meta, category):
            if mod['name'] not in seen:
                seen.add(mod['name'])
                choices.append((mod.get('kr_name') or mod['name'], mod['name']))
        return sorted(choices)

    def arcane_choices(self, w_meta: Dict[str, Any]) -> List[Any]:
        prefix = (w_meta.get('category') or '').lower()
        seen, choices = set(), []
        for mod in self.indexer.mods_index.values():
            name = mod.get('name', '')
            if mod.get('is_arcane') and name.lower().startswith(prefix) and name not in seen:
                seen.add(name)
                choices.append((mod.get('kr_name') or name, name))
        return sorted(choices)

    def format_saved_build(self, build: Dict[str, Any]) -> str:
        def label(slot: str) -> str:
            name = build['slots'].get(slot)
            if not name:
                return '(빈 슬롯)'
            if name == RIVEN_MOD:
                return '리벤 모드'
            return (self.indexer.mods_index.get(name.lower()) or {}).get('kr_name') or name

        weapon = build.get('kr_name') or build['weapon']
        lines = [f"**{weapon}** (저장: {build.get('saved_at', '').replace('T', ' ')[:16]})"]
        if build['slots'].get('stance'):
            lines.append(f"• 스탠스: {label('stance')}")
        if build['slots'].get('exilus'):
            lines.append(f"• 엑실러스: {label('exilus')}")
        lines.append("• 1행: " + " / ".join(label(s) for s in GRID_SLOTS[:4]))
        lines.append("• 2행: " + " / ".join(label(s) for s in GRID_SLOTS[4:]))
        if build.get('extra'):
            lines.append("• 슬롯 미확인: " + ", ".join((self.indexer.mods_index.get(n.lower()) or {}).get('kr_name') or n for n in build['extra']))
        if build.get('arcane'):
            lines.append(f"• 아케인: {self._arcane_info(build['arcane'])['kr_name']}")
        if build.get('riven'):
            lines.append(f"• 리벤 옵션: {self._format_riven_options(build['riven'])}")
        elif RIVEN_MOD in build['slots'].values():
            lines.append("• 리벤 옵션: 아직 모름 (리롤 화면을 찍거나 수치를 입력하면 기록됩니다)")
        return "\n".join(lines)

    def format_saved_damage(self, build: Dict[str, Any]) -> str:
        metrics = self.evaluate_saved_build(build)
        weapon = build.get('kr_name') or build['weapon']
        lines = [
            f"**{weapon}** 저장 빌드 화력:",
            f"• 지속 DPS: `{metrics['sustained_dps']:,.0f}`",
            f"• 순간 DPS: `{metrics['burst_dps']:,.0f}`",
            f"• 최고점: `{metrics['max_crit_hit']:,.0f}` / 최저점: `{metrics['min_hit']:,.0f}`",
        ]
        full_stack = metrics.get('full_stack') or {}
        if full_stack.get('assumptions'):
            lines.append(f"• 풀스택 추정: `{full_stack['burst_dps']:,.0f}` ({', '.join(full_stack['assumptions'])})")
        return "\n".join(lines)

    # --- Riven reroll comparison ---

    @staticmethod
    def _format_riven_options(stats: Dict[str, float]) -> str:
        return ", ".join(f"{STAT_DISPLAY[k]} {v * 100:+g}%" for k, v in stats.items() if k in STAT_DISPLAY) or "없음"

    def _diagnose_reroll_screen(self, img) -> Optional[Dict[str, Any]]:
        reading = read_reroll_screen(img)
        if not reading:
            return None
        text = reading.get('weapon_text', '')
        w_meta = self.indexer.match_weapon_strict(text) or self.indexer.fuzzy_match_weapon(text)
        if not w_meta:
            return {
                'success': False,
                'message': "**[세팔론 오디스]** 오퍼레이터님, 리벤 옵션은 읽었지만 어떤 무기의 리벤인지 확인하지 못했습니다. 카드의 무기 이름이 보이도록 다시 캡처해 주십시오.",
            }
        return self.compare_riven_rolls(w_meta, reading['old'], reading['new'])

    def compare_riven_rolls(self, w_meta: Dict[str, Any], old_card: Dict[str, Any], new_card: Dict[str, Any], removed_slot: Optional[str] = None) -> Dict[str, Any]:
        build = self.build_store.get_build(w_meta['name'])
        working = dict(build) if build else None
        notes = []
        riven_slot = None
        if working:
            working['slots'] = dict(working.get('slots', {}))
            working['panel_removed'] = list(working.get('panel_removed', []))
            riven_slot = next((s for s, n in working['slots'].items() if n == RIVEN_MOD), None)
            if riven_slot is None:
                if removed_slot:
                    working['panel_removed'].append(working['slots'][removed_slot])
                    riven_slot = removed_slot
                else:
                    riven_slot = next((s for s in GRID_SLOTS if s not in working['slots']), None)
                if riven_slot is None:
                    weapon = w_meta.get('kr_name') or w_meta['name']
                    choices = [(s, (self.indexer.mods_index.get(working['slots'][s].lower()) or {}).get('kr_name') or working['slots'][s]) for s in GRID_SLOTS]
                    return {
                        'success': True, 'is_riven_compare': True, 'needs_slot_choice': True, 'choices': choices,
                        'w_meta': w_meta, 'old_card': old_card, 'new_card': new_card,
                        'message': f"**[세팔론 오디스]** {weapon} 저장 빌드에 빈 슬롯이 없습니다. 리벤과 바꿀 모드를 골라 주십시오.",
                    }
                working['slots'][riven_slot] = RIVEN_MOD
            mods = self._resolve_build_mods(working)
            # The left card is the roll currently equipped, so it is what the scanned panel contains.
            riven_in_panel = working.get('panel_riven') or (old_card['stats'] if working.get('panel_has_riven') else None)
            left = self._panel_without_changes(working, w_meta, mods, riven_in_panel)
            if not left:
                notes.append("저장 빌드에 패널 수치가 없어 코덱스와 모드로 계산했습니다.")
        else:
            mods = [{'name': RIVEN_MOD, 'slot_index': 1}]
            left = {}
            notes.append("저장된 빌드가 없어 모드 없이 계산했습니다. 모딩 화면을 스캔하면 실제 빌드 기준으로 비교합니다.")

        before = self._evaluate_build(w_meta, left, mods, working, old_card['stats'])
        after = self._evaluate_build(w_meta, left, mods, working, new_card['stats'])
        rows = [
            ('지속 DPS', before['sustained_dps'], after['sustained_dps']),
            ('순간 DPS', before['burst_dps'], after['burst_dps']),
            ('기대 단발', before['expected_hit'], after['expected_hit']),
            ('최고점', before['max_crit_hit'], after['max_crit_hit']),
            ('최저점', before['min_hit'], after['min_hit']),
        ]
        assumptions = before['full_stack'].get('assumptions') or []
        if assumptions:
            rows.append(('풀스택 추정', before['full_stack']['burst_dps'], after['full_stack']['burst_dps']))
            notes.append(f"풀스택 가정: {', '.join(assumptions)}")
        gain = (after['sustained_dps'] - before['sustained_dps']) / max(before['sustained_dps'], 1e-9) * 100.0
        if abs(gain) < 0.5:
            verdict = "두 옵션의 화력이 거의 같습니다"
        elif gain > 0:
            verdict = f"새 옵션이 {gain:+.1f}% 더 강합니다"
        else:
            verdict = f"이전 옵션이 더 강합니다 (새 옵션 {gain:+.1f}%)"

        weapon = w_meta.get('kr_name') or w_meta['name']
        res = {
            'success': True, 'is_riven_compare': True, 'weapon': w_meta['name'], 'w_meta': w_meta,
            'old_card': old_card, 'new_card': new_card, 'before': before, 'after': after, 'rows': rows,
            'gain': gain, 'verdict': verdict, 'notes': notes, 'has_build': bool(build),
            'riven_slot': riven_slot, 'removed_slot': removed_slot,
        }
        lines = [
            f"🔮 **[리벤 리롤 비교: {weapon}]**",
            f"⚖️ **{verdict}** (지속 DPS 기준)",
            f"• 이전: {self._format_riven_options(old_card['stats'])}",
            f"• 새 옵션: {self._format_riven_options(new_card['stats'])}",
            f"• 지속 DPS: `{rows[0][1]:,.0f}` ➔ `{rows[0][2]:,.0f}`",
            f"• 순간 DPS: `{rows[1][1]:,.0f}` ➔ `{rows[1][2]:,.0f}`",
        ]
        unapplied = [f"{u['label']} {u['value'] * 100:+g}%" for u in old_card.get('unapplied', []) + new_card.get('unapplied', [])]
        unapplied += [f"{STAT_DISPLAY['status_chance']} {c['stats']['status_chance'] * 100:+g}%" for c in (old_card, new_card) if 'status_chance' in c['stats']]
        if unapplied:
            res['unapplied'] = unapplied
            lines.append(f"ℹ️ DPS에 반영되지 않는 옵션: {', '.join(unapplied)}")
        lines.extend(f"💡 {note}" for note in notes)
        res['message'] = "\n".join(lines)
        self.last_riven_compare = res
        return res

    def adopt_new_riven(self, res: Dict[str, Any]) -> str:
        """Record the new roll as the build's riven."""
        weapon = res['w_meta'].get('kr_name') or res['w_meta']['name']
        build = self.build_store.get_build(res['w_meta']['name'])
        if not build:
            return f"**[세팔론 오디스]** {weapon} 저장 빌드가 없어 반영하지 못했습니다. 모딩 화면을 먼저 스캔해 주십시오."
        if res.get('removed_slot'):
            build.setdefault('panel_removed', []).append(build['slots'][res['removed_slot']])
        if build.get('panel_has_riven') and not build.get('panel_riven'):
            build['panel_riven'] = res['old_card']['stats']
        build['slots'][res['riven_slot']] = RIVEN_MOD
        build['riven'] = res['new_card']['stats']
        self.build_store.save_build(build)
        return f"💾 {weapon} 빌드의 리벤을 새 옵션으로 갱신했습니다: {self._format_riven_options(build['riven'])}"

    def _ocr_panel_rows(self, img) -> List[Tuple[str, str]]:
            if winocr is None:
                return []

            w, h = img.size
            bottom = int(h * 0.62) if w / max(h, 1) < 2.2 else h
            panel = img.convert('RGB').crop((0, int(h * 0.05), int(w * 0.38), bottom))

            v1 = ImageOps.autocontrast(panel.convert('L').resize((panel.width * 3, panel.height * 3), Image.LANCZOS)).convert('RGB')
            r, g, b = panel.split()
            m = ImageChops.lighter(ImageChops.lighter(r, g), b)
            v2 = ImageOps.invert(ImageOps.autocontrast(m.resize((panel.width * 4, panel.height * 4), Image.LANCZOS))).convert('RGB')

            def ocr_variant(variant):
                loop = asyncio.new_event_loop()
                try:
                    res = loop.run_until_complete(winocr.recognize_pil(variant, lang='ko'))
                except Exception:
                    res = []
                finally:
                    loop.close()
                return res

            res_v1 = ocr_variant(v1)
            res_v2 = ocr_variant(v2)

            def extract_rows(res):
                labels = []
                values = []
                for line in getattr(res, 'lines', res):
                    label_words = []
                    value_words = []
                    for word in line.words:
                        if re.search(r'\d', word.text) and not re.search(r'[가-힣]', word.text):
                            value_words.append(word.text)
                        else:
                            label_words.append(word.text)
                    if label_words:
                        y = line.words[0].bounding_rect.y
                        labels.append((y, ' '.join(label_words)))
                    if value_words:
                        y = line.words[0].bounding_rect.y
                        values.append((y, ' '.join(value_words)))
                labels.sort()
                gaps = sorted(b[0] - a[0] for a, b in zip(labels, labels[1:]) if b[0] > a[0])
                tol = gaps[len(gaps) // 2] * 0.6 if gaps else 30.0
                rows = []
                for y, label_text in labels:
                    min_dist = float('inf')
                    value_text = ''
                    for vy, value_text_candidate in values:
                        if abs(vy - y) <= tol and abs(vy - y) < min_dist:
                            min_dist = abs(vy - y)
                            value_text = value_text_candidate
                    rows.append((label_text, value_text))
                return rows

            rows_v1 = extract_rows(res_v1)
            rows_v2 = extract_rows(res_v2)

            return rows_v1 + rows_v2

# Compatibility Aliases
RivenOCRAnalyzer = ScreenModAnalyzer
ScreenModDiagnoser = ScreenModAnalyzer
