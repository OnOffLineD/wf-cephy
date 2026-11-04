"""Reads the riven reroll screen: two cards, the previous roll on the left and the new roll on the right."""
import asyncio
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageOps
from rapidfuzz import fuzz

try:
    import winocr
except ImportError:
    winocr = None

ELEMENTS = {"화염": "heat", "냉기": "cold", "전기": "electric", "독성": "toxin"}
STAT_LABELS = {
    "피해": "base_damage", "근접 피해": "base_damage",
    "멀티샷": "multishot",
    "치명타 확률": "crit_chance",
    "치명타 피해": "crit_damage",
    "연사력": "fire_rate", "공격 속도": "fire_rate",
    "상태 이상 확률": "status_chance",
    "탄창 용량": "magazine_capacity",
    "재장전 속도": "reload_speed", "장전 속도": "reload_speed",
    "충격": "impact", "관통": "puncture", "베기": "slash",
    **ELEMENTS,
}
# Chat and edit-box shorthand. Status chance is parsed but no DPS formula uses it.
INPUT_ALIASES = {
    "치확": "crit_chance", "크확": "crit_chance", "치피": "crit_damage", "크피": "crit_damage",
    "멀샷": "multishot", "데미지": "base_damage", "대미지": "base_damage", "연사": "fire_rate", "공속": "fire_rate",
    "상확": "status_chance", "상태이상": "status_chance", "탄창": "magazine_capacity", "재장전": "reload_speed", "장전": "reload_speed",
    "불": "heat", "얼음": "cold", "독": "toxin",
}
STAT_DISPLAY = {
    "base_damage": "피해", "multishot": "멀티샷", "crit_chance": "치명타 확률", "crit_damage": "치명타 피해",
    "fire_rate": "연사력", "status_chance": "상태 이상 확률", "magazine_capacity": "탄창 용량", "reload_speed": "재장전 속도",
    "impact": "충격", "puncture": "관통", "slash": "베기", "heat": "화염", "cold": "냉기", "electric": "전기", "toxin": "독성",
}
MATCH_RATIO = 80

_compact = re.compile(r"\s+")
_stat_line = re.compile(r"^\W*([+-])\s*(\d+(?:\.\d+)?)\s*(%|0/0|o/o)?\s*(.+)$", re.I)


def _match_label(label: str) -> Optional[str]:
    compact = _compact.sub("", label)
    best_key, best_score = None, 0.0
    for name, key in STAT_LABELS.items():
        score = fuzz.ratio(compact, _compact.sub("", name))
        if score > best_score:
            best_key, best_score = key, score
    return best_key if best_score >= MATCH_RATIO else None


def parse_stat_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse one card line. key is None for stats that exist in game but don't change the DPS math."""
    match = _stat_line.match(line.strip())
    if not match:
        return None
    sign, number, _, label = match.groups()
    # The element icon gets read as a digit or symbol in front of the label.
    label = re.sub(r"^[^가-힣a-zA-Z]+", "", label)
    label = re.sub(r"\s*\(.*$", "", label).strip()
    if not re.search(r"[가-힣]", label):
        return None
    value = float(number) / 100.0 * (-1 if sign == "-" else 1)
    return {"key": _match_label(label), "value": value, "label": label}


def _add_stat(stats: Dict[str, float], key: str, value: float) -> None:
    stats[key] = value
    if key in ELEMENTS.values():
        stats["elemental_damage"] = sum(stats[e] for e in ELEMENTS.values() if e in stats)


def parse_riven_input(text: str) -> Dict[str, float]:
    """Parse typed options such as '치확 150 멀샷 -30' or '화염 85.2'."""
    names = sorted(set(STAT_LABELS) | set(INPUT_ALIASES), key=len, reverse=True)
    pattern = "|".join(re.escape(n).replace(r"\ ", r"\s*") for n in names)
    stats: Dict[str, float] = {}
    for label, number in re.findall(rf"({pattern})\s*[:=]?\s*([+-]?\d+(?:\.\d+)?)\s*%?", text):
        compact = _compact.sub("", label)
        key = INPUT_ALIASES.get(compact) or next(v for k, v in STAT_LABELS.items() if _compact.sub("", k) == compact)
        _add_stat(stats, key, float(number) / 100.0)
    return stats


def format_riven_stats(stats: Dict[str, float]) -> str:
    return " ".join(f"{STAT_DISPLAY[k].replace(' ', '')} {v * 100:g}" for k, v in stats.items() if k in STAT_DISPLAY)


def looks_like_reroll_screen(text: str) -> bool:
    if not re.search(r"소\s*지\s*품|최대\s*랭크", text):
        return False
    return len(re.findall(r"[+-]\s*\d+(?:\.\d+)?\s*(?:%|0/0)", text)) >= 4


def _ocr_lines(image: Image.Image, scale: float, offset: Tuple[int, int]) -> List[Dict[str, Any]]:
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(winocr.recognize_pil(image, lang="ko"))
    except Exception:
        return []
    finally:
        loop.close()
    lines = []
    for line in result.lines:
        words = list(line.words)
        first, last = words[0].bounding_rect, words[len(words) - 1].bounding_rect
        lines.append({
            "x0": first.x / scale + offset[0],
            "x1": (last.x + last.width) / scale + offset[0],
            "y": first.y / scale + offset[1],
            "text": " ".join(w.text for w in words),
        })
    return lines


def _gray(crop: Image.Image, scale: int) -> Image.Image:
    enlarged = crop.convert("L").resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    return ImageOps.autocontrast(enlarged).convert("RGB")


def _bright_inverted(crop: Image.Image, scale: int) -> Image.Image:
    r, g, b = crop.split()
    bright = ImageChops.lighter(ImageChops.lighter(r, g), b).resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
    inverted = ImageOps.invert(ImageOps.autocontrast(bright, cutoff=1))
    return ImageOps.expand(inverted, border=20, fill=255).convert("RGB")


def _read_card(image: Image.Image, box: Tuple[int, int, int, int]) -> Dict[str, Any]:
    crop = image.crop(box)
    passes = [
        _ocr_lines(_gray(crop, 3), 3.0, box[:2]),
        _ocr_lines(_gray(crop, 4), 4.0, box[:2]),
        _ocr_lines(_bright_inverted(crop, 4), 4.0, box[:2]),
    ]
    # One pass often misreads a digit or drops a line, so values are decided by vote.
    votes: Dict[str, Counter] = {}
    best_lines: List[Dict[str, Any]] = []
    name_lines: List[str] = []
    for lines in passes:
        parsed = [(ln, parse_stat_line(ln["text"])) for ln in lines]
        stat_lines = [p for _, p in parsed if p]
        if len(stat_lines) > len(best_lines):
            best_lines = stat_lines
            first_y = min(ln["y"] for ln, p in parsed if p)
            name_lines = [ln["text"] for ln, p in parsed if not p and ln["y"] < first_y and re.search(r"[가-힣a-zA-Z]{2,}", ln["text"])]
        for stat in stat_lines:
            if stat["key"]:
                votes.setdefault(stat["key"], Counter())[stat["value"]] += 1

    stats: Dict[str, float] = {}
    unapplied = []
    for line in best_lines:
        if line["key"]:
            _add_stat(stats, line["key"], votes[line["key"]].most_common(1)[0][0])
        else:
            unapplied.append({"label": line["label"], "value": line["value"]})
    return {"name": " ".join(name_lines), "stats": stats, "unapplied": unapplied}


def read_reroll_screen(image: Image.Image) -> Optional[Dict[str, Any]]:
    if winocr is None:
        return None
    image = image.convert("RGB")
    width, height = image.size
    area = (int(width * 0.15), int(height * 0.55), int(width * 0.9), int(height * 0.85))
    lines = _ocr_lines(_gray(image.crop(area), 3), 3.0, area[:2])
    stat_lines = [ln for ln in lines if parse_stat_line(ln["text"])]
    if len(stat_lines) < 4:
        return None

    # Two cards means two columns of stat lines. Selecting a card slides both, but left stays the previous roll.
    centers = sorted(((ln["x0"] + ln["x1"]) / 2, i) for i, ln in enumerate(stat_lines))
    gaps = [(centers[i + 1][0] - centers[i][0], i) for i in range(len(centers) - 1)]
    gap, split = max(gaps)
    if gap < width * 0.06:
        return None
    columns = [[stat_lines[i] for _, i in centers[:split + 1]], [stat_lines[i] for _, i in centers[split + 1:]]]
    if min(len(c) for c in columns) < 2:
        return None

    cards = []
    for column in columns:
        x0 = min(ln["x0"] for ln in column) - width * 0.02
        x1 = max(ln["x1"] for ln in column) + width * 0.02
        y0 = min(ln["y"] for ln in column) - height * 0.08
        y1 = max(ln["y"] for ln in column) + height * 0.035
        cards.append(_read_card(image, (max(0, int(x0)), max(0, int(y0)), min(width, int(x1)), min(height, int(y1)))))

    # The compatible weapon is also named under the 호환 가능 label at the lower right.
    label_box = (int(width * 0.8), int(height * 0.82), width, int(height * 0.9))
    label_lines = _ocr_lines(_gray(image.crop(label_box), 3), 3.0, label_box[:2])
    names = [cards[0]["name"], cards[1]["name"]] + [ln["text"] for ln in label_lines]
    weapon_text = next((re.search(r"[가-힣][가-힣\s]*[가-힣]", n).group(0) for n in names if re.search(r"[가-힣][가-힣\s]*[가-힣]", n)), "")
    return {"weapon_text": weapon_text.strip(), "old": cards[0], "new": cards[1]}
