"""
Universal Harness Probe Runner (Warframe Companion)
Executes rapid 3-gate verification:
Gate 1: Unit & Integration Tests (pytest)
Gate 2: Core Domain & Static Sanity Check
Gate 3: Graphify & Workspace Integrity Check
"""
import sys
import os
import subprocess

# Ensure project root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

def run_tests():
    print("[PROBE 1/3] Running Test Suite...")
    try:
        import pytest
        # Run pytest targeting tests directory
        res = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-v", "--tb=short"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True
        )
        passed = res.returncode == 0
    except ImportError:
        res = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
            cwd=ROOT_DIR,
            capture_output=True,
            text=True
        )
        passed = res.returncode == 0

    print(f" -> Test Suite: {'PASSED' if passed else 'FAILED'}")
    if not passed:
        print("\n--- OUTPUT ---\n", res.stdout[-1200:])
        print("\n--- ERRORS ---\n", res.stderr[-800:])
    return passed

def run_domain_sanity():
    print("[PROBE 2/3] Running Domain Sanity & Rule Verification...")
    try:
        # Check required directories
        assert os.path.exists(os.path.join(ROOT_DIR, ".agents")), "Missing .agents directory"
        assert os.path.exists(os.path.join(ROOT_DIR, ".agents", "guardrails")), "Missing .agents/guardrails"
        assert os.path.exists(os.path.join(ROOT_DIR, ".agents", "memory")), "Missing .agents/memory"
        
        # Check core scripts existence
        required_scripts = [
            "warframe_damage_engine.py",
            "screen_mod_analyzer.py",
            "llm_orchestrator.py",
            "desktop_companion.py"
        ]
        for script_name in required_scripts:
            script_path = os.path.join(ROOT_DIR, "scripts", script_name)
            assert os.path.exists(script_path), f"Missing core script: {script_name}"
            
        print(" -> Domain Sanity: PASSED")
        return True
    except Exception as e:
        print(f" -> Domain Sanity: FAILED ({e})")
        return False

def run_graph_check():
    print("[PROBE 3/3] Checking Graphify / AST Integrity...")
    graph_path = os.path.join(ROOT_DIR, "graphify-out", "graph.json")
    if os.path.exists(graph_path):
        size_kb = os.path.getsize(graph_path) / 1024
        print(f" -> Graphify Graph: PRESENT ({size_kb:.1f} KB)")
        return True
    else:
        print(" -> Graphify Graph: SKIPPED (graph.json not generated yet)")
        return True

def main():
    print("=" * 60)
    print(" [Universal Harness Probe] Starting Verification Cycle")
    print("=" * 60)
    
    g1 = run_tests()
    g2 = run_domain_sanity()
    g3 = run_graph_check()
    
    print("=" * 60)
    if g1 and g2 and g3:
        print(" [Harness Probe Result] ALL GATES PASSED (COMPOSE READY)")
        print("=" * 60)
        sys.exit(0)
    else:
        print(" [Harness Probe Result] GATES FAILED - REVISION REQUIRED")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
