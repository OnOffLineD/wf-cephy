"""Scanned weapon builds, one per weapon, kept in the user's data folder."""
import json
import os
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from scripts.path_config import get_user_data_path, write_json_atomic

GRID_SLOTS = ["R1_C1", "R1_C2", "R1_C3", "R1_C4", "R2_C1", "R2_C2", "R2_C3", "R2_C4"]
RIVEN_MOD = "Riven Mod"


def is_riven_name(name: Optional[str]) -> bool:
    """The codex lists blank entries such as 'Shotgun Riven Mod'; every roll is still just a riven."""
    return bool(name) and str(name).lower().endswith("riven mod")


def slot_order(slot: str) -> int:
    """Top-left to bottom-right. The stance has no element, and Exilus is considered after the grid."""
    if slot in GRID_SLOTS:
        return GRID_SLOTS.index(slot) + 1
    return 0 if slot == "stance" else 99


def canonical_slot(slot_name: Optional[str], mod: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if mod and "stance" in str(mod.get("type", "")).lower():
        return "stance"
    if slot_name in ("AuraStance", "Stance", "stance"):
        return "stance"
    if slot_name in ("Exilus", "exilus"):
        return "exilus"
    return slot_name if slot_name in GRID_SLOTS else None


class BuildStore:
    def __init__(self, path: Optional[str] = None):
        self.path = path or get_user_data_path("user_builds.json")

    def _load(self) -> Dict[str, Any]:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("builds"), dict):
                return data
        except FileNotFoundError:
            return {"version": 1, "builds": {}}
        except (OSError, ValueError):
            pass
        # Unreadable file: keep it for recovery instead of overwriting saved builds on the next save.
        shutil.copy2(self.path, f"{self.path}.corrupt-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        return {"version": 1, "builds": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        write_json_atomic(self.path, data)

    def save_build(self, build: Dict[str, Any]) -> None:
        data = self._load()
        build = dict(build, saved_at=datetime.now().isoformat(timespec="seconds"))
        data["builds"][build["weapon"].lower()] = build
        self._save(data)

    @staticmethod
    def _normalized(build: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # Older saves could hold a codex riven entry as an ordinary mod.
        if build:
            for slot, name in build.get("slots", {}).items():
                if is_riven_name(name) and name != RIVEN_MOD:
                    build["slots"][slot] = RIVEN_MOD
                    build["panel_has_riven"] = True
        return build

    def get_build(self, weapon: str) -> Optional[Dict[str, Any]]:
        return self._normalized(self._load()["builds"].get(weapon.lower()))

    def list_builds(self) -> List[Dict[str, Any]]:
        builds = [self._normalized(b) for b in self._load()["builds"].values()]
        return sorted(builds, key=lambda b: b.get("saved_at", ""), reverse=True)

    def latest_build(self) -> Optional[Dict[str, Any]]:
        builds = self.list_builds()
        return builds[0] if builds else None

    def delete_build(self, weapon: str) -> bool:
        data = self._load()
        if data["builds"].pop(weapon.lower(), None) is None:
            return False
        self._save(data)
        return True
