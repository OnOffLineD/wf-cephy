# Project Progress & Verification Board (Warframe Companion)

> **Last Updated**: 2026-11-07  
> **Overall Status**: Phase 5 COMPLETED (T-UI-10: Native startSystemMove Drag & Click Root Fix Merged)  
> **Managed By**: `AGENT_SCRIBE`

---

## 1. Phase Status Overview

| Phase | Description | Assigned Agent | Status | Test / Verification |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 0** | Bootstrap, Git, Rules & Harness Scaffolding | `AGENT_SCRIBE`, `AGENT_ARCH` | **COMPLETED** | `scripts/probe.py` 3-Gate PASS |
| **Phase 1** | Warframe Damage Engine & Math Core | `AGENT_CORE`, `AGENT_QA` | **COMPLETED** | Formula tests pinned to in-game panel values PASS |
| **Phase 2** | Screen OCR Mod Analyzer & Diagnostic Workflow | `AGENT_CORE`, `AGENT_QA` | **COMPLETED** | OCR & Riven Diagnosis Tests PASS |
| **Phase 3** | Desktop Companion UI (PyQt6) & World State Tracker | `AGENT_UI`, `AGENT_QA` | **COMPLETED** | UI Tab & Tracker Tests PASS |
| **Phase 4** | 3-Tier Chat Routing & Ordis LLM Orchestration (1-Token GBNF + Dynamic Tool Grammar) | `AGENT_CORE`, `AGENT_QA` | **COMPLETED** | Chat Intent, GBNF Grammar & Memory Tests PASS |
| **Phase 5** | Unified Settings, Frameless Dialog Architecture & Native Window Drag | `AGENT_UI`, `AGENT_CORE`, `AGENT_QA` | **COMPLETED** | Full Suite (516 passed) & `scripts/probe.py` 3-Gate PASS |

---

## 2. Active Inter-Agent Packets
```yaml
@[AGENT_PACKET]
from: AGENT_UI
to: AGENT_SCRIBE
phase: PHASE_5
status: PASSED
graphify_nodes: ["FramelessDialog", "OrdisPersonaDialog", ".startSystemMove()", "mainCard"]
touched_files: ["scripts/frameless_dialog.py", "scripts/persona_dialog.py", "tests/test_settings_and_frameless_dialogs.py", "EXPERIENCE.md", "PROGRESS.md"]
git_commit_ref: "master"
payload:
  task: "Permanently fixed unclickable buttons by adopting Qt6 native startSystemMove and eliminating main_card drag event hijacking"
  verification: "pytest (516 tests passed 100%) and probe.py 3-gate verification passed"
  issue: "none"
@[/AGENT_PACKET]
```
