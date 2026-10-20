import time
from scripts.screen_mod_analyzer import ScreenModAnalyzer

images = [
    ("나미 스카일라 프라임", r"C:/Users/2doo2/.gemini/antigravity/brain/4a973225-cdb1-4064-b5f5-3904f03c0087/.user_uploaded/media_1792137178605_32d147d9.jpg"),
    ("리퍼 프라임", r"C:/Users/2doo2/.gemini/antigravity/brain/4a973225-cdb1-4064-b5f5-3904f03c0087/.user_uploaded/media_1792137178605_e8bee2af.jpg"),
    ("스트로파", r"C:/Users/2doo2/.gemini/antigravity/brain/4a973225-cdb1-4064-b5f5-3904f03c0087/.user_uploaded/media_1792137178606_65c077be.jpg"),
    ("다크 스플릿-소드", r"C:/Users/2doo2/.gemini/antigravity/brain/4a973225-cdb1-4064-b5f5-3904f03c0087/.user_uploaded/media_1792137178610_c7c8451b.jpg"),
    ("글레이브 프라임", r"C:/Users/2doo2/.gemini/antigravity/brain/4a973225-cdb1-4064-b5f5-3904f03c0087/.user_uploaded/media_1792137178652_d45ff263.jpg"),
]

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
