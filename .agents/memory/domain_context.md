# Domain Context & Architecture Memory (Warframe Companion)

> 이 문서는 Warframe Companion 프로젝트의 핵심 도메인 모델, 인터페이스, 모듈 구성을 기록하는 하네스 메모리입니다.

## 1. Core Architecture Overview
- **System Purpose**: Warframe 게임 플레이어를 위한 온디바이스 AI 컴패니언 (세팔론 오르디스 페르소나, OCR 모딩 진단, 데미지 시뮬레이터, 실시간 월드 이벤트 트래커, 위키 RAG 가이드).
- **Key Modules**:
  - `scripts/screen_mod_analyzer.py`: 화면 캡처 및 OCR 기반 장착 모드/무기 자동 분석.
  - `scripts/warframe_damage_engine.py`: Expected DPS, Burst DPS, 치명타 티어별 Roll 연산 코어 엔진.
  - `scripts/damage_simulator.py`: 적 방어력/속성별 TTK 시뮬레이터 및 리벤 수치 비교.
  - `scripts/desktop_companion.py`: PyQt6 기반의 세팔론 오르디스 데스크톱 펫 및 카카오톡 스타일 UI.
  - `scripts/llm_orchestrator.py`: 3-Tier 엄격 대화 라우팅 및 LLM 추론 오케스트레이션.
  - `scripts/world_state_tracker.py`: Cetus 주기, Duviri 기분, 출격(Sortie) 등 실시간 월드 상태 추적.
  - `scripts/guide_retriever.py`: Warframe 위키 및 공략 문서 글자 조각 BM25 검색 엔진.
  - `scripts/drop_lookup.py`: 아이템 드롭 위치와 성유물 보상 조회.
  - `tests/`: 40개 이상의 단위 및 통합 테스트 스위트.

## 2. Key Entities & Data Models
- **WeaponStats**: 무기 기본 스탯 (Base Damage, Attack Speed/Fire Rate, Crit Chance, Crit Mult, Status Chance 등).
- **EquippedMod**: 장착된 모드명, 등급(Rank), 속성 배분.
- **DamageEngineMetrics**: Expected DPS, Burst DPS, Max Crit Roll, Min Roll.
- **WorldStateEvent**: 활성 월드 이벤트, 남은 시간, 미션 세부사항.

## 3. Communication & Integration
- OCR Engine: Windows Media OCR (WinRT) / PaddleOCR 폴백.
- Local LLM: Ollama 로컬 LLM 인터페이스 (`embedded_llm_runner.py`).
- Desktop UI: PyQt6 QSystemTrayIcon + 오버레이 윈도우.
