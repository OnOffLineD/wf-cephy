import time
from scripts.screen_mod_analyzer import ScreenModAnalyzer

t0 = time.time()
analyzer = ScreenModAnalyzer()
res = analyzer.diagnose_screenshot("ocrTestImg/1792128102.jpg")
t1 = time.time()

print(f"Elapsed: {t1 - t0:.2f}s")
print(f"Weapon: {res.get('weapon')}")
print(f"Detected mods ({len(res.get('detected_mods', []))}): {res.get('detected_mods')}")
print(f"Stats: {res.get('stats')}")
