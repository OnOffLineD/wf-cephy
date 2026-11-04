# Project Accumulated Experience Library (Harness² Recursion)

> 이 문서는 본 프로젝트의 개발, 디버깅, 검증 과정에서 도출된 에러와 검증된 해결책(Pattern & Lessons)을 누적하는 로컬 하네스 메모리입니다.  
> 기술 스택 공통 교훈은 `~/.gemini/config/skills/harness/GLOBAL_EXPERIENCE.md`를 상속합니다.

---

### EXP-001: Embedded Python과 시스템 Python 간 패키지 격리 및 Pytest 탐색 충돌 방지
- **기록일자**: 2026-10-22
- **현상**: 시스템 환경에서 pytest 구동 시 `python_embed/site-packages` 하위의 컴파일 바이너리(C-extension)를 재귀 탐색하여 `ImportError: cannot import name 'ArgsKwargs' from 'pydantic_core._pydantic_core'` 발생.
- **해결책**:
  - `pytest.ini`에 `testpaths = tests` 및 `norecursedirs = python_embed harness .git runs crops labeling weights debug_crops` 명시.
  - `scripts/probe.py`의 테스트 러너 인자에 `tests` 디렉토리를 명시적으로 바인딩하여 안전한 스모크/회귀 테스트 환경 구축.
- **교훈**: 휴대용(Embedded) 파이썬 런타임과 호스트 파이썬 환경이 공존하는 프로젝트에서는 테스트 도구의 재귀 경로 격리 설정이 필수적임.

---

### EXP-002: Windows 환경 한글 인코딩 및 파일 입출력 안전성
- **기록일자**: 2026-10-22
- **현상**: 모드 데이터 JSON 입출력 및 사용자 체크리스트 저장 시 CP949 인코딩으로 인한 문자 깨짐 발생 가능성.
- **해결책**:
  - 모든 파일 읽기/쓰기에 `encoding="utf-8"` 명시 선언.
  - JSON 덤프 시 `ensure_ascii=False` 설정.
- **교훈**: 다국어/한국어 지원 데스크톱 앱에서는 모든 파일 I/O 계층에 UTF-8을 일관되게 강제해야 함.

---

### EXP-003: Harness 초기 구축 및 3대 게이트 검증 연동
- **기록일자**: 2026-10-22
- **현상**: 새 프로젝트 환경에서 하네스 스캐폴딩 부재
- **해결책**:
  - 8대 하네스 컴포넌트 배포 및 probe.py 3대 게이트 러너 구성
- **교훈**: 자가 치유 및 지식 누적 시스템을 초기 단계에 정착시켜 회귀 결함 원천 차단

---

### EXP-004: 패널 총계와 위키 수식 대조
- **기록일자**: 2026-11-03
- **현상**: 모드 데이터가 상태이상·지면 강타 피해를 직접 피해로 합산하고 적 방어력에 Tenno 공식을 사용
- **해결책**:
  - 모드 스탯 정확 분류, 위키 수식 모듈 추가, 게임 패널 대조 테스트 고정
- **교훈**: 수식 검증은 단위 예제만이 아니라 실제 인게임 패널 값과 대조해야 한다

---

### EXP-005: 테스트가 실제 사용자 환경을 건드림
- **기록일자**: 2026-11-04
- **현상**: 테스트가 체크리스트 메타를 바꾸고, 실제 창을 띄우고, llama-server를 시작·강제 종료함
- **해결책**:
  - WF_USER_DATA_DIR와 offscreen을 conftest에서 고정하고, 앱 생성 시 서버를 자동 시작하지 않으며 이름 기반 강제 종료를 제거
- **교훈**: 앱 부작용은 생성자가 아니라 진입점에 두어야 테스트가 격리된다
