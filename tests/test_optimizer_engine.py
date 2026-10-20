import pytest
import json
from scripts.optimizer_engine import OptimizerEngine

def test_pipeline_riven_compare():
    engine = OptimizerEngine()
    req = {
        "task_type": "RIVEN_COMPARE",
        "target_item": "Torid",
        "incarnon_mode": True,
        "enemy_context": {
            "faction": "Corrupted",
            "level": 200,
            "is_steel_path": True
        },
        "riven_candidates": [
            {"name": "Option A", "stats": {"crit_chance": 1.2, "crit_damage": 1.0}},
            {"name": "Option B", "stats": {"multishot": 1.0, "base_damage": 1.0}}
        ],
        "constraints": {
            "allow_helminth": True,
            "allow_archon_shards": True,
            "allow_companion_primer": True
        }
    }

    res = engine.process_request(req)
    assert res.get("status") == "SUCCESS" or "winner" in res.get("summary_metrics", {}) or "winner" in res
    assert "summary_metrics" in res or "recommended_build" in res or "winner" in res

def test_pipeline_survival_build():
    engine = OptimizerEngine()
    req = {
        "task_type": "SURVIVAL_BUILD",
        "target_item": "Nova",
        "enemy_context": {
            "level": 200,
            "is_steel_path": True
        }
    }
    res = engine.process_request(req)
    assert res.get("status") == "SUCCESS" or "ehp" in str(res).lower()

def test_pipeline_levelcap_synergy():
    engine = OptimizerEngine()
    req = {
        "task_type": "LEVELCAP_SYNERGY",
        "target_item": "MK1-Braton",
        "enemy_context": {
            "level": 9999,
            "is_steel_path": True
        }
    }
    res = engine.process_request(req)
    assert res.get("status") == "SUCCESS" or "synergy" in str(res).lower()
