import json
import os
import re
import pytest
from pathlib import Path
from typing import Any, Dict, List, Tuple
from rapidfuzz import fuzz
from scripts.screen_mod_analyzer import ScreenModAnalyzer

# Constants
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GT_PATH = os.path.join(ROOT, 'tests', 'fixtures', 'ocr_ground_truth.json')
IMG_DIR = os.path.join(ROOT, 'ocrTestImg')
STAT_KEYS = ("total_damage", "fire_rate", "multishot", "crit_chance", "crit_mult")
STAT_TOLERANCE = 0.015
MOD_MATCH_RATIO = 85
MIN_WEAPON_ACCURACY = 0.90
MIN_STAT_CORRECT_RATE = 0.35
MAX_STAT_WRONG_RATE = 0.02
MIN_MOD_RECALL = 0.88

# Functions
def normalize_mod(name: str) -> str:
    return re.sub(r'\s+', '', name.lower())

def stat_matches(expected: float, actual: float) -> bool:
    return abs(expected - actual) <= STAT_TOLERANCE * abs(expected)

def mod_matched(expected: str, detected_list: List[str]) -> bool:
    expected_normalized = normalize_mod(expected)
    for detected in detected_list:
        detected_name = detected.split(' (')[0]
        if fuzz.ratio(expected_normalized, normalize_mod(detected_name)) >= MOD_MATCH_RATIO:
            return True
    return False

# Module-scoped fixture
@pytest.fixture(scope="module")
def results() -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    with open(GT_PATH, 'r', encoding='utf-8') as f:
        gt_data = json.load(f)
    samples = gt_data.get('samples', {})
    analyzer = ScreenModAnalyzer()
    test_results = []

    for filename, truth in samples.items():
        path = os.path.join(IMG_DIR, filename)
        if not os.path.exists(path):
            continue

        try:
            analyzer.clear_pending_riven()
            analyzer.clear_pending_diagnosis()
            res = analyzer.diagnose_screenshot(path)
        except Exception as e:
            res = {'crash': str(e)}

        test_results.append((filename, truth, res))

    if not test_results:
        pytest.skip("No test results to evaluate.")

    return test_results

# Tests
def test_no_crashes(results):
    crashes = [filename for filename, _, res in results if 'crash' in res]
    assert not crashes, f"Crashes detected in the following files: {', '.join(crashes)}"
    print(f"No crashes detected. ({len(results)} samples)")

def test_weapon_accuracy(results):
    correct = 0
    total = 0
    misses = []

    for filename, truth, res in results:
        if truth.get('weapon') is not None:
            total += 1
            if res.get('weapon') == truth['weapon']:
                correct += 1
            else:
                misses.append((filename, truth['weapon'], res.get('weapon')))

    print(f"Weapon accuracy: {correct}/{total} ({correct/total:.2%}), misses: {misses}")
    assert correct/total >= MIN_WEAPON_ACCURACY, f"Weapon accuracy below threshold: {correct/total:.2%}"

def test_unnameable_weapon_is_not_guessed(results):
    for filename, truth, res in results:
        if truth.get('weapon') is None:
            if not res.get('needs_clarification', False) and 'crash' not in res:
                w_meta = res.get('w_meta', {})
                if not w_meta.get('is_inferred', False):
                    pytest.fail(f"Unnameable weapon guessed: {filename}, {res.get('weapon')}")

    print("Unnameable weapons are not guessed correctly.")

def test_panel_stats(results):
    correct = 0
    wrong = 0
    total = 0

    for filename, truth, res in results:
        for key in STAT_KEYS:
            if truth.get(key) is not None:
                total += 1
                expected = truth[key]
                actual = res.get('stats', {}).get(key)
                if actual is None:
                    print(f"Missing {key} in {filename}: expected {expected}, got None")
                elif stat_matches(expected, actual):
                    correct += 1
                else:
                    wrong += 1
                    print(f"Wrong {key} in {filename}: expected {expected}, got {actual}")

    print(f"Panel stats: correct {correct}/{total} ({correct/total:.2%}), wrong {wrong}/{total} ({wrong/total:.2%})")
    assert correct/total >= MIN_STAT_CORRECT_RATE, f"Panel stats correct rate below threshold: {correct/total:.2%}"
    assert wrong/total <= MAX_STAT_WRONG_RATE, f"Panel stats wrong rate above threshold: {wrong/total:.2%}"

def test_high_res_panel_stats(results):
    from PIL import Image

    failures = []
    checked = 0

    for filename, truth, res in results:
        if res.get('needs_clarification') or 'crash' in res:
            continue

        with Image.open(os.path.join(IMG_DIR, filename)) as im:
            width = im.width
            if width < 1280:
                continue

        for key in STAT_KEYS:
            if truth.get(key) is not None:
                checked += 1
                actual = (res.get('stats') or dict()).get(key)
                if actual is None or not stat_matches(truth[key], actual):
                    failures.append((filename, key, truth[key], actual))

    print(f"Checked {checked} stats. Failures: {failures}")
    assert checked > 0, "No stats were checked."
    assert not failures, f"Failed to read stats correctly: {failures}"

def test_mod_recall(results):
    matched = 0
    total = 0

    for filename, truth, res in results:
        expected_mods = truth.get('mods', [])
        detected_mods = res.get('detected_mods', [])
        total += len(expected_mods)
        for expected in expected_mods:
            if mod_matched(expected, detected_mods):
                matched += 1

    print(f"Mod recall: {matched}/{total} ({matched/total:.2%})")
    assert matched/total >= MIN_MOD_RECALL, f"Mod recall below threshold: {matched/total:.2%}"