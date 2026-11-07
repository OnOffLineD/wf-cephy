# Project Progress & Verification Board (Warframe Companion)

> **Last Updated**: 2026-11-07  
> **Overall Status**: Phase 5 COMPLETED (T-PET-3: In-Game Key Motion Zero-Trace Hard Blocking & Settings Toggle Merged)  
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
| **Phase 5** | Unified Settings, Frameless Dialog Architecture & Pet Motion Safety Hard-Lock | `AGENT_UI`, `AGENT_CORE`, `AGENT_QA` | **COMPLETED** | T-PET-3 Full Suite (518 tests passed) & `probe.py` 3-Gate PASS |
| **Phase 6** | Official Game Settings/Lore RAG & Saved Build Vault (2x4 Grid) UI | `AGENT_CORE`, `AGENT_UI`, `AGENT_QA` | **COMPLETED** | T-RAG-1 & T-BUILD-TAB-1 Full Suite (534 tests passed) & `probe.py` 3-Gate PASS |

---

## 2. Active Inter-Agent Packets
```yaml
@[AGENT_PACKET]
from: AGENT_UI
to: AGENT_SCRIBE
phase: PHASE_6
status: PASSED
graphify_nodes: ["OrdisCompanionApp", "MorphingTabBar", "BuildStore", "GuideRetriever"]
touched_files: ["scripts/desktop_companion.py", "rules/wiki_docs/game_settings/official_game_settings.md", "rules/wiki_docs/quests_and_story/official_lore_and_factions.md", "rules/wiki_docs/game_modes/endgame_progression_guide.md", "data/guide_aliases.json", "tests/test_companion_ui_tabs.py", "tests/test_guide_search.py"]
git_commit_ref: "master"
payload:
  task: "Implemented official Korean game settings/lore/endgame guide RAG docs and added 4th '빌드' vault tab with 2x4 visual grid and action buttons"
  verification: "pytest (534 tests passed 100%) and probe.py 3-gate verification passed"
  issue: "none"
@[/AGENT_PACKET]
```

---

## 3. Future Roadmap Backlog (Phase 6 Candidates - User Approved for Memo)

| ID | Item | Scope | Description |
| :--- | :--- | :--- | :--- |
| **F-01** | **스마트 실시간 알림 (펫 말풍선 + 균열 필터)** | UI / WorldState | Focus Assist 우회 Always-on-top 펫 말풍선 큐 알림, 성유물 균열(강철의 길/생존 등) 커스텀 필터 알림 |
| **F-02** | **리벤 롤 등급(S/A/B/F) & DPS 기반 유효옵 판정** | Core / UI | `omegaAttenuation` 기반 순수 롤 백분율 판정 + 기존 엔진 역산(해당 옵션 제거 시 DPS 감소율) 기반 유효옵/무해한 마옵 평가 |
| **F-03** | **PyTorch 의존성 제거 (ONNX) 및 포터블 경량화** | Core / Build | YOLO `slot_detector.pt` -> ONNX 변환으로 수 GB PyTorch 제거, onedir 및 모델 분리 다운로드 파이프라인 |
| **F-04** | **공통 스택 버프 모델 (인카논/아케인 램프업)** | Core | 메타 10~15개 인카논/아케인의 시간축 스택 누적 및 실전 DPS 램프업/감쇄 커브 시뮬레이션 |
| **F-05** | **워프레임 전용 봉고캣 파쿠르/CPS 카운터** | UI / Pet | `Ctrl+Space` 불릿점프/파쿠르 횟수 집계, 단발무기 광클(CPS) vs 연사력 진단, 오디스 실시간 글리치 반응 |

