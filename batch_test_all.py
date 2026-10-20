import os
import time
from scripts.screen_mod_analyzer import ScreenModAnalyzer

analyzer = ScreenModAnalyzer()
img_dir = "ocrTestImg"
files = sorted([f for f in os.listdir(img_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))])

print(f"==================== BATCH TEST ON {len(files)} IMAGES ====================")
t_start = time.time()
results = []
for f in files:
    p = os.path.join(img_dir, f)
    t0 = time.time()
    res = analyzer.diagnose_screenshot(p)
    dt = time.time() - t0
    
    if res.get("needs_clarification"):
        status = "[CLARIFY_NEEDED]"
        info = f"무기 미특정 (OCR: {res.get('raw_ocr', '')[:25]})"
    elif res.get("success"):
        status = "[PASS]"
        w = res.get("weapon")
        m_count = len(res.get("detected_mods", []))
        slam = res.get("stats", {}).get("slam_damage", "-")
        heavy = res.get("stats", {}).get("heavy_damage", "-")
        stat_str = f"Slam={slam} | Heavy={heavy}" if slam != "-" or heavy != "-" else ""
        info = f"Weapon={w:<18} | {stat_str:<22} | Mods: {m_count}개 {res.get('detected_mods', [])[:3]}"
    else:
        status = "[FAIL]"
        info = res.get("message", "")[:30]
        
    print(f"{status} {f} ({dt:.2f}s): {info}")
    results.append((f, status, dt))

total_dt = time.time() - t_start
print(f"\n총 소요 시간: {total_dt:.2f}초 (평균: {total_dt/len(files):.2f}초/장)")
