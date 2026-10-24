# Global Engineering Experience Library (Harness² Cross-Project Knowledge)

> 모든 프로젝트에서 상속되어 공통으로 적용되는 전역 트러블슈팅 및 엔지니어링 패턴 라이브러리입니다.

---

### G-EXP-001: Windows 환경 파일 입출력 시 한글 인코딩 깨짐 방지
- **현상**: Python `open(path, 'w')` 또는 CSV 출력 시 기본 인코딩이 Windows `CP949`로 설정되어 한글/특수문자가 깨지거나 타 플랫폼에서 파싱 실패.
- **해결책**:
  - CSV 및 일반 텍스트 파일 저장 시 반드시 `encoding='utf-8-sig'` 또는 `encoding='utf-8'`을 명시적으로 선언.
  - CLI 인라인 실행 대신 `.py` 파일 기반 실행으로 인코딩 컨텍스트 보호.
- **교훈**: Windows 환경에서 다국어/한글 데이터 파이프라인 구축 시 인코딩 매개변수는 생략 불가한 필수 파라미터임.

---

### G-EXP-002: SQLite 동시성 락 및 Foreign Keys PRAGMA 누락 방지
- **현상**: SQLite 연결 시 기본적으로 외래키 제약조건(`PRAGMA foreign_keys = ON`)이 꺼져 있어 무결성 검증이 무력화되거나, 다중 스레드 환경에서 `database is locked` 발생.
- **해결책**:
  - SQLAlchemy `engine` 생성 시 `connect_args={"check_same_thread": False}` 설정.
  - `engine.connect` 이벤트 리스너에서 `PRAGMA foreign_keys=ON;`을 강제 활성화.
  - 트랜잭션은 단기 세션(`get_session` 컨텍스트 매니저)으로 감싸 즉시 커밋/롤백.
- **교훈**: SQLite를 사용할 때는 초기화 단계에서 외래키 강제와 스레드 격리를 기본 탑재해야 데이터 오염을 방지할 수 있음.

---

### G-EXP-003: Subprocess 실행 컨텍스트와 sys.path 의존성
- **현상**: `scripts/` 하위 유틸리티나 테스트 실행 시 프로젝트 루트 디렉토리가 `sys.path`에 포함되지 않아 `No module named 'core'` 등의 임포트 에러 발생.
- **해결책**:
  - 모든 독립 실행 스크립트 상단에 `sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))` 표준 삽입.
- **교훈**: 도구 스크립트는 작업 디렉토리 위치에 영향받지 않도록 자체 절대경로 기반 sys.path 보정 로직을 포함해야 함.

---

### G-EXP-004: DOM/XML 기반 문서 조작 시 정규식 파괴 방지
- **현상**: HWPX, DOCX, XLSX 등 XML 기반 컨테이너 조작 시 정규식이나 단순 문자열 치환을 사용하면 태그 트리 구조가 깨져 오피스 프로그램에서 열리지 않음.
- **해결책**:
  - `xml.etree.ElementTree` 또는 DOM 파서를 사용하여 텍스트 노드(`<hp:t>`, `<w:t>`) 단위로 외과적 교체 수행.
- **교훈**: 복합 바이너리/압축 포맷은 파서 기반의 구조적 조작을 원칙으로 함.
