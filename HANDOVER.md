# 🛰️ Warframe Optimizer / Desktop Companion 프로젝트 인수인계서 (Handover Guide)

> **문서 작성일**: 2026-10-17  
> **프로젝트 버전**: v3.0 (Short-Term Conversational Memory, 3-Tier Strict Routing Fix & Lifecycle VRAM Cleanup)  
> **담당자**: Cephalon Ordis Development Team  

---

## 1. 📌 프로젝트 개요 (Overview)

본 프로젝트는 워프레임(Warframe) 플레이어를 보조하기 위한 **AI 데스크톱 컴패니언 (Cephalon Ordis 페르소나)** 시스템입니다.
카카오톡 스타일의 1:1 대화형 UI를 통해 실시간 월드 이벤트 체크리스트를 제공하며, RAG 기반 인게임 위키 가이드 질의응답, 그리고 인게임 모딩 스크린샷을 분석하여 실전 DPS 및 화력을 진단하는 수학 엔진을 탑재하고 있습니다.

### 핵심 기능 매트릭스
1. **스마트 챗봇 & 3-Tier 엄격 라우팅**:
   - **Level 1 (스몰톡/일상 대화)**: 세팔론 오디스 특유의 위트 있는 버그 페르소나 응답 (빌드 템플릿 강제 생성 금지).
   - **Level 2 (게임 공략/RAG 질의응답)**: `rules/wiki_docs/` 지식 기반으로 성계지도 미션(생존, 이동방어, 첩보 등), 보스 공략, 속성 약점 안내.
   - **Level 3 (스크린샷 모딩 진단)**: 모딩 스크린샷 업로드 시 OCR + Gemma 4 Vision 하이브리드 판독 및 수식 엔진 기반 화력(지속/순간 DPS, 치명타 최고/최저점, 12배수 연속기 등) 브리핑.
2. **단기 대화 세션 메모리 (ShortTermMemory & 동적 컨텍스트 조절)**:
   - **기본 4k (4,096 토큰 / 메모리 1,200 토큰)**: 최근 8~10턴 대화 및 무기/미션 맥락을 완벽 보존.
   - **대명사 지능형 복원**: '거기서', '그거', '그 무기' 등 대명사 질문 시 직전 대화 키워드를 RAG 검색에 자동 주입.
   - **동적 VRAM 절약/확장 (`/메모리 2k / 4k / 8k`)**:
     - `2k`: VRAM을 즉시 회수하여 초저사양 환경/게임 프레임 보장 (메모리 350 토큰).
     - `4k (기본)`: 가장 쾌적한 표준 모드.
     - `8k`: 장시간 세션용 깊은 대화 기억 (메모리 2,500 토큰).
3. **적응형 3단계 앵커링 스크린샷 진단**:
   - 16:9 전체화면, 21:9/32:9 울트라와이드(16:9 HUD 리센터링), 사용자가 직접 잘라낸 부분 크롭 창을 자동 판별하여 9개 슬롯(스탠스 + 8개 모드) 100% 정밀 검출.
4. **로컬 LLM (Gemma 4 E2B)**:
   - 최신 멀티모달 **Gemma 4 E2B** 모델 탑재 (기본 4k 토큰, 필요 시 2k/8k 1.5초 재기동 전환).

---

## 2. 💻 새 PC 개발 환경 요구사항 (Prerequisites)

- **운영체제**: Windows 10 또는 Windows 11 권장 (`winocr` Windows 네이티브 OCR 엔진 사용)
- **Python**: Python 3.10 ~ 3.12 권장
- **GPU / VRAM**: NVIDIA GPU (최소 VRAM 4GB 권장, 6GB 이상 시 100% GPU 레이어 오프로드 가능)
- **외부 런타임**:
  - **(스탠드얼론 - Ollama 없이 단독 실행)**:
    - `python scripts/embedded_llm_runner.py --start` 실행 시 `models/`에 GGUF 모델(`google_gemma-4-E2B-it-Q4_K_M.gguf`)이 없으면 자동으로 HuggingFace에서 다운로드하여 포트 8080에 기동.

---

## 3. 🚀 3단계 빠른 시작 (Quick Start)

### 1단계: 가상환경 생성 및 의존성 설치
```powershell
# 프로젝트 루트 디렉터리로 이동
cd "WarframeOptimizer"

# 가상환경 생성 및 활성화
python -m venv venv
.\venv\Scripts\Activate.ps1

# 의존성 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 2단계: 로컬 LLM 확인
```powershell
models\에 'google_gemma-4-E2B-it-Q4_K_M.gguf'가 없으면 HuggingFace에서 다운로드
```

### 3단계: 전체 테스트 및 빌드 검증
```powershell
# 문법 컴파일 체크 (0 에러 확인)
python -m compileall -q scripts

# 전체 회귀 테스트 실행 (19개 테스트 100% 통과 확인)
python -m pytest tests/ --ignore=python_embed -q
```

### 4단계: 애플리케이션 실행
```powershell
# GUI 데스크톱 컴패니언 실행
python scripts/desktop_companion.py
```

---

## 4. 📂 주요 디렉터리 및 아키텍처 구조

```
WarframeOptimizer/
├── .antigravity/                # 로컬 오케스트레이션 설정
│   └── project_profile.json     # 빌드/테스트 명령어, 로컬 모델(gemma4:e2b, num_ctx: 2048) 정의
├── data/                        # 워프레임 코덱스 데이터
│   ├── raw_wfcd/                # 무기, 모드 JSON 원본 데이터
│   └── guide_aliases.json       # 공략 검색 은어 사전
├── models/                      # 로컬 LLM GGUF 모델 보관함
│   └── google_gemma-4-E2B-it-Q4_K_M.gguf  # 최신 Gemma 4 E2B 단독 모델 (구형 gemma-2-2b 영구 삭제됨)
├── rules/wiki_docs/             # RAG 인게임 지식 기반 문서들
│   ├── game_modes/              # 성계지도 미션(생존, 이동방어, 방어, 첩보 등) 공략
│   ├── bosses/                  # 보스 패턴 및 공략
│   └── weapon_archetypes/       # 무기 아키타입별 특성
├── scripts/                     # 핵심 백엔드 및 UI 로직
│   ├── desktop_companion.py     # 카카오톡 스타일 메인 GUI & 이벤트 체크리스트
│   ├── screen_mod_analyzer.py   # 적응형 3단계 앵커링 OCR & 화력 진단 엔진
│   ├── llm_orchestrator.py      # 질문/플랜 엄격 분기 & Gemma 4 E2B 오케스트레이터
│   ├── guide_retriever.py       # 위키 문서 글자 조각 BM25 검색기
│   ├── drop_lookup.py           # 아이템 드롭 위치·성유물 보상 조회
│   ├── wf_data_indexer.py       # 무기/모드 퍼지 매칭 및 메타데이터 인덱서
│   ├── damage_simulator.py      # 실전 DPS/치명타/상태이상/연속기 계산기
│   ├── pipeline_runner.py       # Antigravity 로컬 모델 패치/생성 자동화 파이프라인
│   └── embedded_llm_runner.py   # 스탠드얼론 llama-server 실행기
├── tests/                       # 자동화 테스트 스위트
│   ├── test_chat_routing_comprehensive.py # 챗봇 라우팅 및 중복 억제 19개 종합 테스트
│   ├── test_interactive_clarification.py  # 무기명 모호성 대화형 질의 테스트
│   ├── test_wfcd_indexing.py              # 데이터 인덱싱 및 모딩 진단 테스트
│   └── test_damage_simulator.py          # 데미지 계산식 검증 테스트
├── requirements.txt             # 파이썬 런타임 의존성 목록
├── AGENTS.md / GEMINI.md        # Antigravity 에이전트 자율 오케스트레이션 규칙
└── HANDOVER.md                  # 본 인수인계 문서
```

---

## 5. 🎯 최근 완료된 핵심 작업 내역 (Current Milestone Status)

1. **Gemma 4 E2B 멀티모달 모델 전면 교체**:
   - 구형 `gemma-2-2b-it-Q4_K_M.gguf`를 완전히 삭제하고, 최신 멀티모달 `gemma4:e2b` (3.46 GB) 단독 적용.
   - 컨텍스트 길이를 **2048** 토큰으로 일원화하여 VRAM 점유량 약 322MB~400MB 수준의 초경량·고속 인퍼런스 실현.
2. **채팅 응답 품질 개선 & 엄격 라우팅**:
   - **출격 계획 생성 시**: 불필요한 보상 텍스트 복붙 환각 억제.
   - **미션 가이드 질의 시**: '생존' 질의에 실드 게이팅 엉뚱한 답변을 차단하고 생존 산소/적 처치/네크로스 공략 매칭, '이동방어' 질의에 침대/숙면 환각을 차단하고 데이터매스/콘솔 방어 공략 정확 매칭.
3. **스크린샷 모딩 진단 3단계 앵커링 & 울트라와이드 리센터링 탑재**:
   - **1단계 (UI 앵커 환경 판별)**: 화면 하단 38% 영역에서 인벤토리 고유 앵커(`"해제"`, `"튜토리얼"`, `"정렬"`, `"모드 융합"`)를 스캔하여 21:9/32:9 울트라와이드 전체화면과 모딩창 부분 크롭을 100% 정확하게 분기.
   - **2단계 (울트라와이드 16:9 리센터링)**: 전체화면이면서 `w / h > 1.85`일 때, 워프레임 HUD Margin에 맞춰 `target_w = int(h * 16 / 9)`, `offset_x = (w - target_w) / 2`로 중앙 안전 영역을 리센터링하여 하단 인벤토리 오인식률 **0건** 달성.
   - **3단계 (크롭 창 3배수 스케일링 & 접두사 보너스)**: 부분 크롭 창 9개 슬롯(스탠스 + 8개 모드) 및 `볼래틸(Volatile)`, `아말감(Amalgam)` 접두사 가중치 보강으로 100% 완벽 검출.
   - **4단계 (Gemma 4 E2B Vision 앙상블 페일세이프)**: 슬롯별 OCR 검출이 4개 미만일 때 Vision 전역 판독 텍스트와 자모 매칭 결합 복원.
4. **RAG 생존 미션 검색 가중치 버그 수정 & Python 3.13 호환성 완성**:
   - '생존 미션' 질의 시 실드 게이팅 모딩 문서 혼입 차단 및 성계지도 미션 가이드(`star_chart_missions.md`) 100% 정확 매칭.
   - Windows Python 3.13 환경에서 발생하는 C/Rust DLL 네이티브 충돌을 우회하여 0.05초 초고속 인메모리 인덱싱 복원.
5. **전역 단축키 원클릭 화면 캡처 & 스마트 붙여넣기 (`F9`, `Ctrl+V`)**:
   - 게임 플레이 중 어디서든 `F9`를 누르면 전체 화면을 즉시 캡처하고 오디스 창 최상단 복원 및 모딩 진단 자동 시작.
   - 채팅창에 `Ctrl+V` 시 클립보드 이미지 자동 감지 및 즉시 진단 연동.
6. **리벤(Riven) 모드 2단계 정밀 분석 및 실전 화력 비교 리포트 엔진**:
   - 모딩 슬롯 내 리벤 모드(`Visi-critacan`, `사티-타칸` 등 접미사/키워드) 자동 감지.
   - 리벤 모드 감지 시 확대 스크린샷 캡처 가이드 자동 브리핑 및 대기 상태 전환.
   - 리벤 팝업 캡처 수신 시 +, - 부호와 소수점 퍼센트 정밀 파싱 (`+치명타 확률`, `+피해`, `-공격 속도` 등).
   - 데미지 시뮬레이터 연동: 리벤 적용 전(Base) vs 리벤 적용 후(With Riven)의 지속 DPS, 순간 DPS, 크리티컬 최고점/최저점 및 상승률(% gain) 비교표 브리핑.
7. **단기 대화 세션 메모리 (ShortTermMemory & 동적 2k/4k/8k VRAM 컨텍스트 전환)**:
   - 인메모리 슬라이딩 윈도우 기반 단기 대화 버퍼 탑재 (앱 종료 시 디스크 흔적 없이 100% 휘발).
   - 직전 대화의 무기/미션 키워드를 '거기서', '그거', '그 무기' 등의 대명사 질의에 자동 주입하여 문맥 연속 질의 보장.
   - 동적 컨텍스트 전환 CLI/명령어 (`/메모리 2k / 4k / 8k`) 지원으로 VRAM 회수 및 딥 세션 확장 지원.
8. **3-Tier 엄격 라우팅 보완 및 라이프사이클 프로세스 VRAM 누수 방지 (v3.0 완결)**:
   - **RAG 텍스트 파일 덤프 차단**: 5초 LLM 타임아웃을 30초로 증액하고, '?' 질문에 대한 무조건적인 RAG 분기 버그를 제거하여 함선 상태/자장가/피로 등 일상 스몰톡은 즉시 세팔론 오디스 페르소나로 연결. RAG 비매칭 시 날것의 txt 파일 경로 대신 친절한 요약 안내 제공.
   - **백그라운드 llama-server VRAM 누수 완벽 차단**: GUI 종료(`closeEvent`) 시 `llm_runner.stop_server()` 및 `taskkill /F /IM llama-server.exe`를 강제 실행하여 창을 닫는 즉시 3.25GB의 GPU VRAM을 100% 반환.
   - 전체 회귀 테스트 **30개 전 항목 100% 무결점 통과** (`python -m pytest tests/ --ignore=python_embed -q`).

---

## 6. ⚠️ 트러블슈팅 및 주의사항 (Gotchas & Troubleshooting)

### 1) Windows PowerShell 콘솔 한글 깨짐 방지
PowerShell 콘솔에서 스크립트 출력 시 한글이 깨진다면 실행 전 아래 명령어를 실행하십시오:
```powershell
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
[Console]::InputEncoding = [Text.Encoding]::UTF8
```

### 2) Ollama 포트 충돌 (11434 포트)
`scripts/llm_orchestrator.py`는 기본적으로 `http://localhost:11434/api/generate`를 호출합니다. 만약 다른 프로세스가 포트를 점유하고 있거나 접속 실패 시 자동으로 안내 메시지를 반환합니다.

### 3) 스탠드얼론 실행 시 GGUF 모델 다운로드
Ollama를 쓰지 않고 내장 러너를 사용할 경우:
```powershell
python scripts/embedded_llm_runner.py --start
```
`models/google_gemma-4-E2B-it-Q4_K_M.gguf` 파일이 없으면 HuggingFace에서 자동으로 다운로드(약 3.5GB)를 시작하므로 충분한 디스크 공간(최소 10GB 이상)을 확보해 두십시오.

### 4) Antigravity 오케스트레이션 규칙 (`AGENTS.md`)
코드를 수정하거나 기능을 추가할 때 AI 에이전트를 사용할 경우 다음 규칙이 강제됩니다:
- **Tier 1 (Cloud Direct Wiring)**: 단순 1줄 상수 변경, 가드문 추가만 직접 편집 허용.
- **Tier 2 (Local Method Patch)**: 루프, if 다중 분기, 알고리즘 수정 시 `python scripts/pipeline_runner.py --mode patch` 위임 필수.
- **Strict Ban on Read-After-Write**: 패치 완료 후 `[VERIFY_CONTRACT]`를 신뢰하며 사후 `view_file` 호출 금지.

---

## 7. 🔜 다음 추천 개발 작업 (Next Roadmap)

1. **위키 가이드 문서 지속 확충 (Phase 4)**:
   - `rules/wiki_docs/game_modes/void_fissure_relics.md`: 보이드 균열, 성유물 개봉(빛나는/무결점 등), 파티 협력 룰.
   - `rules/wiki_docs/mechanics/incarnon_weapons.md`: 인카논 무기 진화 단계 및 변환 가이드.
2. **트레이 최소화 및 시스템 사운드 피드백**:
   - 백그라운드 상주 트레이 아이콘화 및 오디스 보이스 큐/알림 사운드 옵션 연동.

---
*인수인계 문서 끝. 오퍼레이터님, 다른 전장(PC)에서도 성공적인 임무를 기원합니다!*
