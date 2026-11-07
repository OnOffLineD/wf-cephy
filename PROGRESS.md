# Project Progress & Verification Board (Warframe Companion)

> **Last Updated**: 2026-11-07  
> **Overall Status**: Phase 5 COMPLETED (T-UI-5: Frameless Dialog Drag & Click Fix Merged)  
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
| **Phase 5** | Unified Settings, Frameless Dialog Architecture & Full Refactoring | `AGENT_UI`, `AGENT_CORE`, `AGENT_QA` | **COMPLETED** | Full Suite & `scripts/probe.py` 3-Gate PASS |

---

## 2. Active Inter-Agent Packets
```yaml
@[AGENT_PACKET]
from: AGENT_UI
to: AGENT_SCRIBE
phase: PHASE_5
status: PASSED
graphify_nodes: ["FramelessDialog", "OrdisPersonaDialog", ".bind_drag_events()", ".mouseReleaseEvent()"]
touched_files: ["scripts/frameless_dialog.py", "scripts/persona_dialog.py", "tests/test_settings_and_frameless_dialogs.py", "EXPERIENCE.md", "PROGRESS.md"]
git_commit_ref: "master"
payload:
  task: "Fixed dialog unclickable bug after dragging by synchronizing WindowStaysOnTopHint, robust release event acceptance, and activateWindow/raise_ calls"
  verification: "pytest tests/test_settings_and_frameless_dialogs.py (7 passed) and probe.py 3-gate verification passed"
  issue: "none"
@[/AGENT_PACKET]
```
