"""
Backward-compatibility wrapper for scripts.screen_mod_analyzer.
Deprecated: Use `scripts.screen_mod_analyzer` and `ScreenModAnalyzer` instead.
"""
from scripts.screen_mod_analyzer import ScreenModAnalyzer, RivenOCRAnalyzer, ScreenModDiagnoser

__all__ = ["ScreenModAnalyzer", "RivenOCRAnalyzer", "ScreenModDiagnoser"]
