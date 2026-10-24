# Engineering Guardrails (Global Standards)

## 1. Zero Conversational Filler (무소음 원칙)
- 불필요한 인사말, 사과, 서론, 요약 브리핑을 배제하고 정형 통신 블록(`@[AGENT_PACKET]`), 실행 커맨드, 코드만 출력한다.

## 2. Graphify & AST-First Mandate (토큰 예산 방어)
- 전체 파일의 무분별한 덤프(`cat` 또는 전체 Read)를 엄격히 금지한다.
- `graphify` 쿼리 또는 AST 인덱스를 우선 활용하여 타깃 함수/클래스 시그니처와 라인 범위만 핀포인트로 조회한다.
- 코드 수정 후에는 `graphify update .`를 구동하여 지식 그래프를 상시 동기화한다.

## 3. Think Before Coding & Simplicity First
- 가정을 명시적으로 진술하며, 모호한 요구사항은 임의로 결정하지 않고 확인한다.
- 요청받지 않은 과도한 추상화, 단발성 코드에 대한 불필요한 설정 기능을 배제한다.
- 50줄로 완결될 수 있는 로직을 200줄 이상의 복잡한 레이어로 부풀리지 않는다.

## 4. Surgical Changes (정밀한 외과적 수정)
- 기존 정상 동작 중인 인접 코드, 포맷, 주석을 임의 리팩터링하거나 '개선'하지 않는다.
- 본인의 변경으로 인해 발생한 미사용 변수/함수/임포트만 정밀하게 정리한다.
- 자명한 코드에 불필요한 What 주석을 금지하며, 트랜잭션 경계, 복잡한 검증 알고리즘 등 Why 설명이 필요한 구간에만 고밀도 주석을 작성한다.

## 5. Non-Stop Propose-Probe-Compose Lifecycle
- 코드 수정 후 반드시 `python scripts/probe.py` (또는 `node scripts/probe.mjs`)를 실행하여 검증 게이트를 완벽히 통과한 것만 커밋한다.
- 검증 실패 시 중간에 멈추지 않고 자체 디버깅 루프를 수행하여 해결한다.
- 파일 입출력 시 다국어/한글 호환성을 위해 `utf-8-sig` 또는 `utf-8`을 기본으로 한다.
