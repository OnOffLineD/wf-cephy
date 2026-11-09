import time
from scripts.screen_mod_analyzer import ScreenModAnalyzer

import os
import sys
import time
from scripts.screen_mod_analyzer import ScreenModAnalyzer

# Benchmark against sample test images in ocrTestImg/ or custom args
sample_dir = os.path.join(os.path.dirname(__file__), "ocrTestImg")
images = []
if os.path.isdir(sample_dir):
    for f in os.listdir(sample_dir):
        if f.lower().endswith((".jpg", ".png", ".jpeg")):
            images.append((f, os.path.join(sample_dir, f)))

if not images and len(sys.argv) > 1:
    images = [(os.path.basename(p), p) for p in sys.argv[1:]]

if not images:
    print("[NOTICE] No test images found in ocrTestImg/ or passed via arguments.")
    print("Usage: python test_5_user_images.py <image_path_1> <image_path_2> ...")
    sys.exit(0)

analyzer = ScreenModAnalyzer()

print("==================== BENCHMARK ON 5 NEW USER IMAGES ====================\n", flush=True)
total_t0 = time.time()

for expected_name, img_path in images:
    t0 = time.time()
    res = analyzer.diagnose_screenshot(img_path)
    dt = time.time() - t0
    
    weapon = res.get("weapon", "Unknown")
    mods = res.get("detected_mods", [])
    stats = res.get("stats", {})
    metrics = res.get("metrics", {})
    
    print(f"[{expected_name}] ({dt:.2f}s)")
    print(f"  • 인식된 무기: {weapon}")
    print(f"  • 추출 스탯: Slam={stats.get('slam_damage', '-')} | Heavy={stats.get('heavy_damage', '-')} | Slide={stats.get('slide_damage', '-')}")
    print(f"  • 검출 모드 ({len(mods)}개): {', '.join(mods)}")
    print(f"  • 화력 지표: 예상 DPS={metrics.get('sustained_dps', 0):,.0f} | 버스트 DPS={metrics.get('burst_dps', 0):,.0f} | 최고 치명타={metrics.get('max_crit_hit', 0):,.0f}")
    print("-" * 75, flush=True)

total_dt = time.time() - total_t0
print(f"\n총 5개 이미지 완료: {total_dt:.2f}초 (평균 {total_dt/len(images):.2f}초/장)")
