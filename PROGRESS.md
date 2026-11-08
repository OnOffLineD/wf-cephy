# Project Progress & Verification Board (Warframe Companion)

> **Last Updated**: 2026-11-08  
> **Overall Status**: Phase 7 COMPLETED (T-ONNX-1, T-NOTIF-1, T-DMG-UI-1 All Merged & 563 Tests Passed 100%)  
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
| **Phase 7** | ONNX Slot Detection, Reusable Speech Bubble Queue & 2안+3안 Hybrid Damage Dashboard | `AGENT_CORE`, `AGENT_UI`, `AGENT_QA` | **COMPLETED** | T-ONNX-1, T-NOTIF-1, T-DMG-UI-1 Full Suite (563 tests passed 100%) & `probe.py` 3-Gate PASS |

---

## 2. Active Inter-Agent Packets
```yaml
@[AGENT_PACKET]
from: AGENT_UI
to: AGENT_SCRIBE
phase: PHASE_7
status: PASSED
graphify_nodes: ["YOLOSlotDetector", "PetSpeechBubbleWidget", "NotificationCoordinator", "DamageBreakdownDialog", "RadarChart", "simulate_combat"]
touched_files: ["scripts/yolo_slot_detector.py", "scripts/pet_speech_bubble.py", "scripts/notification_coordinator.py", "scripts/desktop_pet.py", "scripts/damage_breakdown_dialog.py", "tests/test_yolo_slot_detector.py", "tests/test_speech_bubble.py", "tests/test_damage_dashboard_tabs.py"]
git_commit_ref: "master"
payload:
  task: "Decoupled PyTorch into onnxruntime with dynamic axes (T-ONNX-1), created reusable speech bubble priority queue (T-NOTIF-1), and implemented Hybrid Damage Dashboard combining Option 2 Combat Simulator and Option 3 Visual 2x4 Slot Radar (T-DMG-UI-1)"
  verification: "pytest (563 tests passed 100%) and probe.py 3-gate verification passed"
  issue: "none"
@[/AGENT_PACKET]
```

---

## 3. Future Roadmap Backlog

| ID | Item | Scope | Description |
| :--- | :--- | :--- | :--- |
| **F-01-B** | **성유물 균열 커스텀 필터 연동 알림** | UI / WorldState | 기구축된 `NotificationCoordinator`를 활용하여 성유물 균열(강철의 길/생존/발굴 등) 매칭 시 펫 말풍선 큐 실시간 팝업 |
| **F-02** | **리벤 롤 등급(S/A/B/F) & DPS 기반 유효옵 판정** | Core / UI | `omegaAttenuation` 기반 순수 롤 백분율 판정 + 기존 엔진 역산(해당 옵션 제거 시 DPS 감소율) 기반 유효옵/무해한 마옵 평가 |
| **F-04** | **공통 스택 버프 모델 (인카논/아케인 램프업)** | Core | 메타 10~15개 인카논/아케인의 시간축 스택 누적 및 실전 DPS 램프업/감쇄 커브 시뮬레이션 |
| **F-05** | **워프레임 전용 봉고캣 파쿠르/CPS 카운터** | UI / Pet | `Ctrl+Space` 불릿점프/파쿠르 횟수 집계, 단발무기 광클(CPS) vs 연사력 진단, 오디스 실시간 글리치 반응 |
| **F-06** | **Single-Swap Advisor (모드 1칸 교체 최적화 조언)** | Core / UI | 8모드 강제 완성 없이, 현재 장착된 슬롯 중 1개만 다른 모드로 교체 시 DPS 기여도 최대 1~3순위 추천 |
| **F-07** | **보이드 균열 보상 화면 OCR (Relic Reward Picker)** | OCR / Market | 균열 보상 4개 선택 화면 캡처 시 warframe.market 플래티넘 시세 및 듀캇 가치 오버레이 추천 |
