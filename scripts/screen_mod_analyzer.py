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
from PIL import Image, ImageEnhance, ImageOps

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

from scripts.optimizer_engine import OptimizerEngine
from scripts.wf_data_indexer import WFDataIndexer
from scripts.jamo_matcher import match_mods_jamo

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
        self.engine = OptimizerEngine()
        self.indexer = WFDataIndexer()
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
                    riven_stats=riven_stats
                )
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
                    # Fallback: tokens in slot that has explicit riven keyword
                    if not w_meta and any(k in s_text.lower() for kw in ['리벤', 'riven', 'critatak']):
                        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', s_text)
                        for token in tokens:
                            if len(token) >= 2 and not any(token.lower().startswith(p) for p in ["프라", "갈바", "아말", "라운"]):
                                cand = self.indexer.fuzzy_match_weapon(token)
                                if cand and cand.get("name") not in ["Riven", "Primed", "Galvanized", "Amalgam", "Pride", "Rauta"]:
                                    if cand.get("category") != "Warframe" and not any(k in cand.get("name", "").lower() for k in ["chamber", "shred", "serration", "vital", "clip"]):
                                        w_meta = cand
                                        break
                    if w_meta:
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

            category = (w_meta.get("category") or "").lower()
            from scripts.jamo_matcher import CATEGORY_MAPPING, decompose_hangul
            from rapidfuzz import fuzz

            allowed = CATEGORY_MAPPING.get(category, [])
            w_type = (w_meta.get("type") or "").lower()

            # 2. Gemma 4 E2B Vision extraction (Hybrid)
            vision_text = ""
            if not slot_res.get("yolo_used", False):
                try:
                    import base64
                    import urllib.request
                    is_fs = slot_res.get("is_fullscreen", True)
                    off_x = slot_res.get("offset_x", 0)
                    b_w = slot_res.get("base_w", w)
                    if not is_fs:
                        crop_eq = img.crop((off_x + int(b_w * 0.25), int(h * 0.15), off_x + int(b_w * 0.95), int(h * 0.95)))
                    else:
                        crop_eq = img.crop((off_x + int(b_w * 0.28), int(h * 0.08), off_x + int(b_w * 0.98), int(h * 0.56)))
                    buf = BytesIO()
                    crop_eq.save(buf, format="JPEG", quality=90)
                    img_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    payload = {
                        "model": "gemma4:e2b",
                        "prompt": "이 워프레임 무기 업그레이드 화면에 장착된 모드들의 한국어 이름을 모두 쉼표로 구분해서 나열해줘.",
                        "images": [img_b64],
                        "options": {"num_ctx": 2048, "temperature": 0.1},
                        "stream": False
                    }
                    req = urllib.request.Request(
                        "http://localhost:11434/api/generate",
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        v_data = json.loads(resp.read().decode("utf-8"))
                        vision_text = v_data.get("response", "")
                except Exception:
                    pass

            # 3. Dedicated slot matching
            candidates = []
            seen = set()
            for k, mod in self.indexer.mods_index.items():
                name = mod.get("name")
                if not name or name in seen: continue
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
                    w_type_norm = "rifle" if w_type == "assault rifle" else w_type
                    if w_type_norm in ["rifle", "shotgun", "bow", "sniper", "pistol"] and m_compat_norm in ["rifle", "shotgun", "bow", "sniper", "pistol"] and m_compat_norm != w_type_norm:
                        continue
                    generic_compat = {"primary", "secondary", "melee", "rifle", "shotgun", "pistol", "warframe", "companion", "archwing", "zaw", "kitgun", "heavy weapon", "robotic", "assault rifle", "sniper", "bow"}
                    if m_compat and m_compat not in generic_compat:
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
                        if any(x in m_type for x in ["aura", "warframe", "companion", "archwing"]): continue
                    if not is_compat: continue
                seen.add(name)
                kr = mod.get("kr_name", "")
                if kr:
                    candidates.append((decompose_hangul(kr.replace(" ", "")), kr, mod))
                candidates.append((decompose_hangul(name.lower().replace(" ", "")), name, mod))

            slot_matches = []
            assigned_slots = {}
            seen_mod_names = set()
            riven_name = None

            for slot_idx, (slot_name, s_text) in enumerate(slot_results):
                eval_text = f"{s_text} {vision_text}".strip() if len(s_text) < 4 else s_text

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
                    (has_weapon_name and any(kw in s_text.lower() for kw in riven_affixes))
                )

                if is_riven:
                    assigned_slots[slot_idx] = (slot_name, {"name": "Riven Mod", "kr_name": "리벤 모드"}, 100.0)
                    riven_name = s_text
                    continue

                slot_cands = self._match_single_slot(eval_text, candidates, return_all=True)
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

            unique_mod_entries = [assigned_slots[k][1] for k in sorted(assigned_slots.keys())]

            # Fallback to general jamo matching if slot extraction yielded fewer than 4 mods
            if len(unique_mod_entries) < 4 and not slot_res.get("yolo_used", False):
                combined_text = slot_res.get("merged_text", "") + "\n" + vision_text
                jamo_mods = match_mods_jamo(combined_text, self.indexer.mods_index, category=category, w_meta=w_meta)
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

            metrics = self.calculate_comprehensive_metrics(w_meta, left_stats=left_stats, mod_objs=unique_mod_entries, riven_stats=parsed.get("stats", {}))
            briefing = self.format_ordis_briefing(w_meta, formatted_mods, metrics)
            review_msg = self.format_mod_review_briefing(w_meta, formatted_mods, equipped_slot_count=slot_res.get('equipped_slot_count', 0), riven_name=riven_name)
            breakdown_msg = self.format_calculation_breakdown(w_meta, unique_mod_entries, metrics, riven_stats=parsed.get('stats', {}))

            if is_weapon_inferred:
                inferred_note = (
                    "💡 **[알림: 무기명 자동 추정]** 상단 무기 이름이 잘려 있어 장착된 모드 구성을 기반으로 기본 규격 화력을 계산했습니다.\n"
                    "채팅으로 정확한 무기 이름(예: '마이터', '소벡', '쿠바 자르')을 입력해 주시면 고유 스펙 및 인카논 특성을 즉시 반영합니다!\n\n"
                )
                briefing = inferred_note + briefing
                review_msg = inferred_note + review_msg

            if riven_name:
                non_riven_mods = [m for m in unique_mod_entries if m.get('name') != 'Riven Mod']
                base_metrics_without_riven = self.calculate_comprehensive_metrics(w_meta, left_stats=None, mod_objs=non_riven_mods, riven_stats=None)
                self.pending_riven_context = {
                    "w_meta": w_meta,
                    "left_stats": left_stats,
                    "mod_objs": non_riven_mods,
                    "riven_name": riven_name,
                    "base_metrics": base_metrics_without_riven
                }
                briefing += (
                    f"\n\n🔮 **[세팔론 오디스 - 리벤 모드 감지 알림]**\n"
                    f"오퍼레이터님! 슬롯에서 **장착된 리벤 모드**를 포착했습니다!\n"
                    f"리벤 모드는 플레이어마다 고유 옵션 수치(치확/치피/피해/멀티샷 등)가 천차만별입니다.\n"
                    f"💬 **리벤 수치가 어떻게 되나요?** 채팅창에 바로 입력(예: `치확 150 치피 120` 또는 `피해 165 멀샷 90`)하시거나,\n"
                    f"📸 리벤 모드 팝업 창을 캡처(`F9` 또는 `Ctrl+V`)해 주시면 리벤 적용 전후 정밀 DPS를 즉시 재계산해 드리겠습니다!"
                )

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

            return {
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

        if metrics.get("full_stack"):
            fs = metrics["full_stack"]
            if is_melee:
                arc_name = "블러드 러시 + 12배수 연속기"
                lines.append(f"\n🔥 **[실전 풀스택 포텐셜 ({arc_name})]**:")
                lines.append(f"• **12배수 연속기 순간 폭딜**: 약 `{fs.get('burst_dps', 0):,.0f} DPS`")
            else:
                arc_name = "갈바 샷 + 세컨더리 아케인" if w_meta.get("category") == "Secondary" else "갈바 + 프라이머리 아케인"
                lines.append(f"\n🔥 **[실전 풀스택 포텐셜 ({arc_name})]**:")
                lines.append(f"• **헤드샷 풀스택 순간 폭딜**: 약 `{fs.get('burst_dps', 0):,.0f} DPS`")

        lines.append(f"\n💬 **오디스의 한마디**: 오퍼레이터님, 인카논 폼과 실전 버프까지 완벽하게 계산되었습니다! 전장을 찢어발기십시오!")
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

        if self.yolo_detector and self.yolo_detector.is_available():
            try:
                layout = self.yolo_detector.detect_layout(img)
                if layout.get("total_detected", 0) >= 4:
                    for s_name in ["AuraStance", "Exilus"]:
                        s_info = layout.get("special_slots", {}).get(s_name)
                        if s_info and s_info.get("box"):
                            slot_boxes.append((s_name, s_info["box"], s_info.get("is_empty", False), s_info.get("is_riven", False)))
                    for k in sorted(layout.get("main_slots", {}).keys()):
                        s_info = layout["main_slots"][k]
                        if s_info and s_info.get("box"):
                            slot_boxes.append((k, s_info["box"], s_info.get("is_empty", False), s_info.get("is_riven", False)))
                    if len(slot_boxes) >= 4:
                        yolo_used = True
                        equipped_slot_count = layout.get("equipped_slot_count", 0)
            except Exception:
                yolo_used = False

        is_fullscreen, offset_x, base_w = self._detect_screen_layout(img)

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
        w, h = img.size
        left_crop = img.crop((0, int(h * 0.05), int(w * 0.38), h))
        left_crop = left_crop.resize((left_crop.width * 2, left_crop.height * 2), Image.LANCZOS)
        
        cw, ch = left_crop.size
        labels = []
        values = []
        ocr_text = ""

        if winocr is not None and self.preferred_ocr == "winocr":
            try:
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_closed():
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                res = loop.run_until_complete(winocr.recognize_pil(left_crop, lang="ko"))

                for line in res.lines:
                    txt = " ".join(w.text for w in line.words).strip()
                    if not txt: continue
                    w0 = line.words[0]
                    ry = w0.bounding_rect.y / ch
                    rx = w0.bounding_rect.x / cw
                    if ry > 0.55:  # Below search box / inventory
                        continue
                    if rx < 0.38:
                        labels.append((ry, txt))
                    elif 0.38 <= rx <= 0.85:
                        values.append((ry, txt))
                ocr_text = "\n".join([l[1] for l in labels] + [v[1] for v in values])
            except Exception:
                ocr_text = self.ocr_image(left_crop)
        else:
            ocr_text = self.ocr_image(left_crop)

        stats: Dict[str, float] = {}

        # 1. Coordinate-aligned pairing if labels & values extracted
        if labels and values:
            for l_ry, l_txt in labels:
                best_v = None
                min_d = 0.025
                for v_ry, v_txt in values:
                    d = abs(l_ry - v_ry)
                    if d < min_d:
                        min_d = d
                        best_v = (v_ry, v_txt)
                if best_v:
                    v_str = best_v[1].replace(',', '')
                    m_num = re.search(r'(\d+(?:\.\d+)?)', v_str)
                    val = float(m_num.group(1)) if m_num else None
                    if val is not None:
                        if re.search(r'멀[티터E]|일[티터E]|밀[티터E]|multishot', l_txt, re.I):
                            stats['multishot'] = val
                        elif re.search(r'연사|인시|공격\s*속도|공속|fire\s*rate', l_txt, re.I):
                            stats['fire_rate'] = val
                        elif re.search(r'치.*확|지.*확|crit.*chance', l_txt, re.I):
                            stats['crit_chance'] = val / 100.0 if val > 1.0 else val
                        elif re.search(r'치.*피|지.*피|crit.*dam', l_txt, re.I):
                            stats['crit_mult'] = val
                        elif re.search(r'상.*이상|상해|상확|status', l_txt, re.I):
                            stats['status_chance'] = val / 100.0 if val > 1.0 else val
                        elif re.search(r'총계|총\s*피해|총합|출계|\*계', l_txt, re.I):
                            stats['total_damage'] = val
                        elif re.search(r'지면\s*강|지면', l_txt, re.I):
                            stats['slam_damage'] = val
                        elif re.search(r'슬라이드', l_txt, re.I):
                            stats['slide_damage'] = val
                        elif re.search(r'강\s*공격', l_txt, re.I):
                            stats['heavy_damage'] = val

            # Positional heuristic for fire_rate and multishot under basic attack section
            if 'multishot' not in stats or 'fire_rate' not in stats:
                num_cands = []
                for v_ry, v_txt in values:
                    if 0.10 <= v_ry <= 0.32 and '%' not in v_txt and not re.search(r'[xX배mMsS]', v_txt):
                        for s in re.findall(r'[\d,]+(?:\.\d+)?', v_txt):
                            try:
                                v = float(s.replace(',', ''))
                                if 0 < v < 100: num_cands.append(v)
                            except Exception: pass
                if 'fire_rate' not in stats and len(num_cands) >= 1:
                    stats['fire_rate'] = num_cands[0]
                if 'multishot' not in stats and len(num_cands) >= 2:
                    stats['multishot'] = num_cands[1]

        # 2. Total damage extraction: explicit label or last valid damage number before search box
        if 'total_damage' not in stats and values:
            dmg_cands = []
            for v_ry, v_txt in values:
                if v_ry >= 0.38 and '%' not in v_txt and not re.search(r'[xX배mMsS]', v_txt):
                    for s in re.findall(r'[\d,]+(?:\.\d+)?', v_txt):
                        try:
                            v = float(s.replace(',', ''))
                            if v > 0: dmg_cands.append(v)
                        except Exception: pass
            if dmg_cands:
                stats['total_damage'] = dmg_cands[-1]

        # 3. Supplemental text parsing fallbacks
        combined_text = ocr_text + "\n" + (full_text or "")
        
        if 'crit_mult' not in stats:
            m_cd = re.search(r'(\d+(?:\.\d+)?)\s*[xX배]', combined_text)
            if m_cd:
                stats['crit_mult'] = float(m_cd.group(1))

        if 'crit_chance' not in stats or 'status_chance' not in stats:
            pcts = [float(p) / 100.0 for p in re.findall(r'(\d+(?:\.\d+)?)\s*%', combined_text)]
            if pcts:
                if len(pcts) >= 3 and pcts[0] <= 0.60:
                    stats.setdefault('valence_bonus', pcts[0])
                    stats.setdefault('crit_chance', pcts[1])
                    stats.setdefault('status_chance', pcts[2])
                elif len(pcts) >= 2:
                    stats.setdefault('crit_chance', pcts[0])
                    stats.setdefault('status_chance', pcts[1])
                elif len(pcts) == 1:
                    stats.setdefault('crit_chance', pcts[0])

        if 'multishot' not in stats:
            m_ms = re.search(r'(?:멀[티터E]|일[티터E]|밀[티터E]|multishot)\s*샷?[\s\S]*?(\d+(?:\.\d+)?)', combined_text, re.I)
            if m_ms:
                stats['multishot'] = float(m_ms.group(1))

        if 'fire_rate' not in stats:
            m_fr = re.search(r'(?:연사력|공격\s*속도|공속|fire\s*rate)[\s\S]*?(\d+(?:\.\d+)?)', combined_text, re.I) or re.search(r'(\d+\.\d+)\s*(?:자동|반자동|점사)', combined_text)
            if m_fr:
                stats['fire_rate'] = float(m_fr.group(1))

        if 'total_damage' not in stats:
            m_tot = re.search(r'(?:총계|총\s*피해|총\s*데미지|total\s*damage|총합|출계|\*계|奢기l)[\s\S]*?([\d,]+(?:\.\d+)?)', combined_text)
            if m_tot:
                stats['total_damage'] = float(m_tot.group(1).replace(',', ''))

        for line in combined_text.splitlines():
            l = line.strip()
            if re.search(r'(지면\s*강타|slam)', l, re.I) and 'slam_damage' not in stats:
                m = re.search(r'([\d,]+(?:\.\d+)?)', l)
                if m: stats['slam_damage'] = float(m.group(1).replace(',', ''))
            elif re.search(r'(슬라이드|slide)', l, re.I) and 'slide_damage' not in stats:
                m = re.search(r'([\d,]+(?:\.\d+)?)', l)
                if m: stats['slide_damage'] = float(m.group(1).replace(',', ''))
            elif re.search(r'(강\s*공격|heavy)', l, re.I) and 'heavy_damage' not in stats:
                m = re.search(r'([\d,]+(?:\.\d+)?)', l)
                if m: stats['heavy_damage'] = float(m.group(1).replace(',', ''))

        return stats

    def calculate_comprehensive_metrics(self, w_meta: Dict[str, Any], left_stats: Optional[Dict[str, float]] = None, mod_objs: Optional[List[Dict[str, Any]]] = None, riven_stats: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
            # Default values if None
            left_stats = left_stats or {}
            mod_objs = mod_objs or []

            # Initialize mod stats
            mod_dmg = 0.0
            mod_ms = 0.0
            mod_cc = 0.0
            mod_cd = 0.0
            mod_fr = 0.0
            mod_elem = 0.0

            # Sum mod stats
            for mod in mod_objs:
                if mod.get('name') != 'Riven Mod':  # Skip 'Riven Mod' dummy entry without stats
                    mod_dmg += mod.get('damage', 0.0)
                    mod_ms += mod.get('multishot', 0.0)
                    mod_cc += mod.get('crit_chance', 0.0)
                    mod_cd += mod.get('crit_damage', 0.0)
                    mod_fr += mod.get('fire_rate', 0.0)
                    mod_elem += mod.get('elemental_damage', 0.0)

            # Sum riven stats if provided
            r_dmg = 0.0
            r_ms = 0.0
            r_cc = 0.0
            r_cd = 0.0
            r_fr = 0.0
            r_elem = 0.0
            r_faction_dmg = 0.0
            r_slash = 0.0
            r_impact = 0.0
            r_puncture = 0.0
            r_mag_capacity = 0.0
            r_reload_speed = 0.0
            r_initial_combo = 0.0

            if riven_stats:
                r_dmg = riven_stats.get('base_damage', 0.0) or riven_stats.get('damage', 0.0)
                r_ms = riven_stats.get('multishot', 0.0)
                r_cc = riven_stats.get('crit_chance', 0.0)
                r_cd = riven_stats.get('crit_damage', 0.0)
                r_fr = riven_stats.get('fire_rate', 0.0)
                r_elem = riven_stats.get('elemental_damage', 0.0)
                r_faction_dmg = riven_stats.get('faction_damage', 0.0)
                r_slash = riven_stats.get('slash', 0.0)
                r_impact = riven_stats.get('impact', 0.0)
                r_puncture = riven_stats.get('puncture', 0.0)
                r_mag_capacity = riven_stats.get('magazine_capacity', 0.0)
                r_reload_speed = riven_stats.get('reload_speed', 0.0)
                r_initial_combo = riven_stats.get('initial_combo', 0.0)

                mod_dmg += r_dmg
                mod_ms += r_ms
                mod_cc += r_cc
                mod_cd += r_cd
                mod_fr += r_fr
                mod_elem += r_elem

            base_ms = float(w_meta.get('base_multishot', 1.0) or w_meta.get('multishot', 1.0) or 1.0)
            base_dmg = float(w_meta.get('total_damage', 0.0))
            if base_dmg <= 0:
                base_dmg = float(left_stats.get('total_damage', 100.0))

            # Check if left_stats has ground truth values from in-game UI
            has_left_total = bool(left_stats.get('total_damage') and left_stats['total_damage'] > 0)
            has_left_ms = bool(left_stats.get('multishot') and left_stats['multishot'] > 0)

            if has_left_ms:
                final_ms = float(left_stats['multishot'])
                if riven_stats and r_ms > 0:
                    final_ms = final_ms * (1.0 + r_ms)
            else:
                final_ms = base_ms * (1.0 + mod_ms)

            if has_left_total:
                final_dmg = float(left_stats['total_damage'])
                if riven_stats:
                    final_dmg = final_dmg * (1.0 + r_dmg) * (1.0 + r_ms) * (1.0 + r_elem)
            else:
                final_dmg = base_dmg * (1.0 + mod_dmg) * (1.0 + mod_ms) * (1.0 + mod_elem)

            if left_stats.get('crit_chance') and left_stats['crit_chance'] > 0:
                final_cc = float(left_stats['crit_chance'])
                if riven_stats and r_cc > 0:
                    final_cc += float(w_meta.get('crit_chance', 0.1)) * r_cc
            else:
                final_cc = float(w_meta.get('crit_chance', 0.1)) * (1.0 + mod_cc)

            if left_stats.get('crit_mult') and left_stats['crit_mult'] > 0:
                final_cd = float(left_stats['crit_mult'])
                if riven_stats and r_cd > 0:
                    final_cd += float(w_meta.get('crit_mult', 1.5)) * r_cd
            else:
                final_cd = float(w_meta.get('crit_mult', 1.5)) * (1.0 + mod_cd)

            if left_stats.get('fire_rate') and left_stats['fire_rate'] > 0:
                final_fr = float(left_stats['fire_rate'])
                if riven_stats and r_fr > 0:
                    final_fr = final_fr * (1.0 + r_fr)
            else:
                final_fr = float(w_meta.get('fire_rate', 1.0)) * (1.0 + mod_fr)

            # Ensure final stats are within valid ranges
            final_cc = max(0.0, final_cc)
            final_ms = max(0.1, final_ms)
            final_fr = max(0.1, final_fr)

            import math
            per_pellet_dmg = final_dmg / final_ms if final_ms > 0 else final_dmg
            is_melee = w_meta.get('category') == 'Melee'

            if not is_melee and final_ms > 1.0:
                ms_min_pellets = max(1, math.floor(final_ms))
                ms_max_pellets = max(1, math.ceil(final_ms))
                ms_extra_pct = round((final_ms - math.floor(final_ms)) * 100.0, 1)

                # Guaranteed minimum non-crit hit when minimum pellets connect
                min_hit = per_pellet_dmg * ms_min_pellets
                # Maximum non-crit hit when maximum pellets connect
                max_non_crit = per_pellet_dmg * ms_max_pellets
                # Max crit hit when maximum pellets all crit
                max_crit_hit = max_non_crit * final_cd
            else:
                ms_min_pellets = 1
                ms_max_pellets = 1
                ms_extra_pct = 0.0
                min_hit = final_dmg
                max_non_crit = final_dmg
                max_crit_hit = final_dmg * final_cd

            # Average non-crit trigger pull (Total damage on mod screen)
            avg_trigger_dmg = final_dmg
            expected_hit = avg_trigger_dmg * (1.0 + final_cc * (final_cd - 1.0))
            burst_dps = expected_hit * final_fr

            # Adjust for faction damage
            if r_faction_dmg > 0:
                final_dmg *= (1.0 + r_faction_dmg)
                expected_hit *= (1.0 + r_faction_dmg)
                burst_dps *= (1.0 + r_faction_dmg)

            # Adjust for physical damage types
            if r_slash > 0:
                final_dmg += r_slash * (1.0 + mod_dmg)
            if r_impact > 0:
                final_dmg += r_impact * (1.0 + mod_dmg)
            if r_puncture > 0:
                final_dmg += r_puncture * (1.0 + mod_dmg)

            # Adjust for magazine and reload speed
            if r_mag_capacity > 0 and r_reload_speed > 0:
                final_mag = r_mag_capacity
                final_reload = r_reload_speed
                duty_cycle = final_mag / (final_mag + final_reload)
                sustained_dps = burst_dps * duty_cycle
            else:
                sustained_dps = burst_dps * 0.78

            # Adjust for initial combo
            if r_initial_combo >= 20:
                # Boost melee combo multiplier
                combo_multiplier = 1.6 if is_melee else 1.0
                expected_hit *= combo_multiplier
                burst_dps *= combo_multiplier

            result = {
                'full_stack': {
                    'burst_dps': burst_dps,
                    'full_stack_hit': expected_hit
                }
            }

            # Populate radial and heavy/energy_disk logic from w_meta
            if 'slam_damage' in left_stats:
                result['radial'] = {'base_damage': left_stats['slam_damage']}
            elif 'radial_attack' in w_meta:
                rad_atk = w_meta['radial_attack']
                rad_base = sum(rad_atk.get('damage', {}).values()) if isinstance(rad_atk.get('damage'), dict) else float(rad_atk.get('damage', 0))
                if w_meta.get('category') == 'Melee' and 'total_damage' in w_meta and float(w_meta['total_damage']) > 0:
                    scale = final_dmg / float(w_meta['total_damage'])
                    rad_base = rad_base * scale
                result['radial'] = {'base_damage': rad_base}

            if 'heavy_damage' in left_stats:
                result['heavy'] = {'heavy_hit': left_stats['heavy_damage']}
            elif w_meta.get('category') == 'Melee':
                result['heavy'] = {'heavy_hit': final_dmg * 1.5}
                for atk in w_meta.get('attacks', []):
                    if atk.get('name') == 'Energy Disk':
                        d_base = sum(atk.get('damage', {}).values()) if isinstance(atk.get('damage'), dict) else float(atk.get('damage', 0))
                        scale = (final_dmg / float(w_meta['total_damage'])) if ('total_damage' in w_meta and float(w_meta['total_damage']) > 0) else 1.0
                        result['energy_disk'] = {'damage': d_base * scale}

            # Populate 'incarnon' dict if applicable
            incarnon_desc = self.get_incarnon_trait_description(w_meta.get('name', ''))
            inc_atk = w_meta.get('incarnon_attack')
            if incarnon_desc or inc_atk:
                if inc_atk:
                    inc_b_dmg = sum(inc_atk.get('damage', {}).values()) if isinstance(inc_atk.get('damage'), dict) else float(inc_atk.get('damage', base_dmg * 2.2))
                    inc_cc_b = float(inc_atk.get('crit_chance', 0))
                    inc_cc_b = (inc_cc_b / 100.0) if inc_cc_b > 1.0 else (inc_cc_b or float(w_meta.get('crit_chance', 0.2)))
                    inc_cd_b = float(inc_atk.get('crit_mult', w_meta.get('crit_mult', 2.0)))
                    inc_fr_b = float(inc_atk.get('speed', w_meta.get('fire_rate', 5.0)))
                    inc_f_dmg = inc_b_dmg * (1.0 + mod_dmg) * (1.0 + mod_ms) * (1.0 + mod_elem)
                    inc_f_cc = inc_cc_b * (1.0 + mod_cc)
                    inc_f_cd = inc_cd_b * (1.0 + mod_cd)
                    inc_f_fr = inc_fr_b * (1.0 + mod_fr)
                    inc_exp = inc_f_dmg * (1.0 + inc_f_cc * (inc_f_cd - 1.0))
                    inc_burst = inc_exp * inc_f_fr
                else:
                    inc_exp = expected_hit * 2.4
                    inc_burst = burst_dps * 2.4
                result['incarnon'] = {
                    'burst_dps': inc_burst,
                    'expected_hit': inc_exp,
                    'attack_meta': inc_atk,
                    'description': incarnon_desc
                }

            # Populate 'hunter_munitions' dict if applicable
            if any('Hunter Munitions' in m.get('name', '') or 'Internal Bleeding' in m.get('name', '') for m in mod_objs):
                bleed_tick = 0.35 * base_dmg * (1.0 + mod_dmg) * (1.0 + mod_ms) * (1.0 + final_cc * (final_cd - 1.0))
                if r_faction_dmg > 0:
                    bleed_tick *= (1.0 + r_faction_dmg)**2
                result['hunter_munitions'] = {
                    'equipped': True,
                    'bleed_tick': bleed_tick
                }

            return {
                'final_dmg': final_dmg,
                'final_cc': final_cc,
                'final_cd': final_cd,
                'final_fr': final_fr,
                'final_ms': final_ms,
                'per_pellet_dmg': per_pellet_dmg,
                'ms_min_pellets': ms_min_pellets,
                'ms_max_pellets': ms_max_pellets,
                'ms_extra_pct': ms_extra_pct,
                'min_hit': min_hit,
                'max_non_crit': max_non_crit,
                'max_crit_hit': max_crit_hit,
                'expected_hit': expected_hit,
                'burst_dps': burst_dps,
                'sustained_dps': sustained_dps,
                **result
            }

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

            gain = ((r_s_dps - base_s_dps) / max(1, base_s_dps)) * 100.0

            return (
                f"🎯 **[세팔론 오디스 - 리벤 모드 정밀 분석 리포트]**\n"
                f"오퍼레이터님! **{weapon_display}** 전용 **리벤 모드**의 세부 수치를 완벽히 해독하여 화력 시뮬레이터에 반영했습니다!\n\n"
                f"📊 **측정된 리벤 고유 옵션**:\n{stats_formatted}\n\n"
                f"⚔️ **실전 화력 비교 (리벤 미적용 ➔ 리벤 장착)**:\n"
                f"- **지속 DPS**: {base_s_dps:,.0f} ➔ **{r_s_dps:,.0f}** ({gain:+.1f}%)\n"
                f"- **순간 DPS**: {base_b_dps:,.0f} ➔ **{r_b_dps:,.0f}**\n"
                f"- **치명타 최고점(Peak)**: {base_max:,.0f} ➔ **{r_max:,.0f}**\n"
                f"- **최저 데미지(Trough)**: {base_min:,.0f} ➔ **{r_min:,.0f}**\n\n"
                f"💡 **세팔론 오디스의 평가**: 리벤 모드의 스탯이 무기 기본 스펙과 증폭 연쇄를 일으켜 실전 기대 화력이 {gain:+.1f}% 강화되었습니다!"
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
                    riven_stats['elemental_damage'] = val
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

        with_riven_metrics = self.calculate_comprehensive_metrics(w_meta_ctx, left_stats=left_stats_ctx, mod_objs=mod_objs_ctx, riven_stats=riven_stats)
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
                f"피해 +{riven_stats.get('damage', 0.0)*100:.1f}%" if riven_stats.get('damage', 0.0) != 0 else "",
                f"멀티샷 +{riven_stats.get('multishot', 0.0)*100:.1f}%" if riven_stats.get('multishot', 0.0) != 0 else "",
                f"원소 피해 +{riven_stats.get('elemental_damage', 0.0)*100:.1f}%" if riven_stats.get('elemental_damage', 0.0) != 0 else "",
                f"치명타 확률 +{riven_stats.get('crit_chance', 0.0)*100:.1f}%" if riven_stats.get('crit_chance', 0.0) != 0 else "",
                f"치명타 피해 +{riven_stats.get('crit_damage', 0.0)*100:.1f}%" if riven_stats.get('crit_damage', 0.0) != 0 else "",
                f"연사력 +{riven_stats.get('fire_rate', 0.0)*100:.1f}%" if riven_stats.get('fire_rate', 0.0) != 0 else ""
            ]
            r_stats = [s for s in r_stats if s]
            riven_stats_str = ', '.join(r_stats) if r_stats else '[옵션 미입력]'
            mod_details.append(f"  - 🔮 리벤 모드 (Riven Mod): {riven_stats_str}")

            mod_dmg += riven_stats.get('damage', 0.0)
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
            f"  ⑤ 순간 폭딜 = {exp_hit:,.1f} × {final_fr:.2f} = {b_dps:,.0f} DPS, 지속 DPS = {b_dps:,.0f} × 0.78 = {s_dps:,.0f} DPS;"
        ]

        if not is_melee and bleed_tick > 0:
            breakdown.append(f"  ⑥ 베기 상태이상 틱딜(헌터 뮤니션즈 트루 데미지) = 0.35 × 발사체 피해({per_pellet:.1f}) × 치명타평균배율({crit_avg_mult:.2f}) = 틱당 약 {bleed_tick:,.1f};")

        if inc_dps > 0 or fs_dps > b_dps:
            breakdown.append(f"  ⑦ 인카논 변신 폼 및 풀스택(아케인+갈바나이즈드) 폭딜 = {fs_dps:,.0f} DPS, 인카논 폭딜 = {inc_dps:,.0f} DPS.")

        return "\n".join(breakdown)

    def _match_single_slot(self, s_text: str, candidates: List[Any], return_all: bool = False) -> Any:
        from scripts.jamo_matcher import decompose_hangul
        from rapidfuzz import fuzz

        variants = [re.sub(r'[^가-힣a-zA-Z0-9\s]', ' ', v).strip() for v in s_text.split('|||') if v.strip()]
        q_jamos = [decompose_hangul(v.lower().replace(' ', '')) for v in variants if v]

        if not q_jamos:
            return [] if return_all else (None, 0.0)

        prefixes = ('갈바나이즈드 ', '프라임드 ', '프라이머리 ', '세컨더리 ', '아말감 ', '새크리피셜 ', '움브랄 ', 'galvanized ', 'primed ', 'primary ', 'secondary ', 'amalgam ', 'sacrificial ', 'umbral ')
        best_mod = None
        best_score = 0.0
        matches = []

        s_low = s_text.lower()
        has_primed = any(k in s_low for k in ['프라임', '라임드', '임드', '표라임', '프래임', 'primed'])
        has_galv = any(k in s_low for k in ['갈바', '바나', '이즈드', '길바', 'galv'])
        has_amalgam = ('아말' in s_low or 'amalgam' in s_low)

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

            for q_j in q_jamos:
                if len(q_j) < 6:
                    r = fuzz.ratio(q_j, cand_jamo)
                    cand_score = max(cand_score, r)
                    continue
                r = fuzz.ratio(q_j, cand_jamo)
                pr = fuzz.partial_ratio(q_j, cand_jamo)

                if suffix_jamo:
                    suf_pr = fuzz.partial_ratio(q_j, suffix_jamo)
                    suf_r = fuzz.ratio(q_j, suffix_jamo)
                    s_val = max(r, pr * 0.90) * 0.40 + max(suf_r, suf_pr) * 0.60
                else:
                    s_val = max(r, pr * 0.90)

                cand_score = max(cand_score, s_val)

            if is_prefixed:
                if not prefix_ok:
                    cand_score -= 22.0
                elif prefix_ok and cand_score > 0:
                    cand_score += 8.0

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

# Compatibility Aliases
RivenOCRAnalyzer = ScreenModAnalyzer
ScreenModDiagnoser = ScreenModAnalyzer
