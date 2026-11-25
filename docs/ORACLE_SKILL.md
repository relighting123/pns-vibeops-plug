# Oracle 공용 조회 스킬

## 이름과 패키지

공식 Agent Skills 규격은 name을 1~64자 소문자·숫자·하이픈으로 작성하고, 앞뒤/연속 하이픈 없이 디렉터리명과 일치하도록 요구한다. 특정 동사나 Oracle 이름을 공식 예약 명칭으로 제공하지는 않는다. 프로젝트에서는 기존 동사-대상 관례에 맞춰 vibeops-read-oracle-data를 선택했다.

위치: skills/vibeops-read-oracle-data/. SKILL.md는 절차, references/는 공통 지식, scripts/oracle_client.py는 공통 실행 코드의 진입점, assets/는 외부 설정 파일의 예시다. 단일 플러그인 구조와 기존 역할 6개를 유지한다.

## MD와 위키

MD는 파일 형식이다. 위키는 문서를 색인·링크·출처·적용 범위·검증일로 연결해 검색 가능한 지식으로 관리하는 방식이다. 검색 엔진이 필수는 아니다.
이번 공통 지식은 작은 규모라 references/의 실행·연결·조회 규칙 세 문서와 SKILL.md의 조건부 링크로 구성했다. 모든 문서를 한 번에 주입하지 않는다. 일반 접속/쿼리 규칙은 코드와 함께 배포해야 버전이 맞으므로 플러그인에 둔다. references 문서에는 출처·확인일·실DB 미검증 상태를 적었다.
사내 DB별 테이블 의미·조인·업무 규칙은 별도 지식 저장소에 두고 연결 ID로 범위를 정해 읽는다. vibeops-read-oracle-data가 전체 DB 지식을 가져오거나 자동 동기화하지 않는다. 현 vibeops-search-wiki는 호스트 검색 지침이며 별도 DB 매핑 검색 엔진은 아직 구현하지 않았다.
OpenWiki라는 이름의 특정 라이브러리를 이번 변경에 사용하지 않았다. 문서량·검색 요구·실제 제품이 정해지면 검색 계층에 연결할 수 있다. 작은 공통 참고 문서를 위해 별도 인덱스 서버·임베딩 의존성을 우선 추가하지 않는다.

## 실행 기능

외부 JSON 프로필과 환경변수의 사용자/비밀번호·DSN으로 자체 접속한다. check·describe·허용된 등록 SELECT query를 지원한다. 배치 내 연결과 읽기 전용 트랜잭션을 재사용한다. 임의 SQL 인자는 제공하지 않는다. 등록 SQL catalog는 운영자 신뢰 영역이다.
11.2 연결 후보는 python-oracledb 3.4.2 Thick + Client19, 19c는 Thin/Thick이다. 11.1·Wallet·외부 인증은 현재 지원 대상으로 선언하지 않는다. profile별 mode 선택 후 별도 CLI 프로세스에서 실행한다.
자세한 설치와 응답 계약은 [실행 절차](../skills/vibeops-read-oracle-data/references/execution.md), 호환성은 [연결 지식](../skills/vibeops-read-oracle-data/references/connections.md), 성능·보안은 [조회 규칙](../skills/vibeops-read-oracle-data/references/query-rules.md)를 따른다.

## 에이전트 연결

Claude의 기존 실행 역할에 Skill 도구와 vibeops-read-oracle-data 검색 지침을 추가했다. 모든 역할에서 Oracle 스킬을 강제로 미리 로드하지 않아 시작 토큰을 늘리지 않는다. 리뷰 역할은 읽기 전용이므로 근거 문서를 읽고 구체적인 조회 요청을 부모에게 넘긴다.
Codex 역할 TOML에는 vibeops-read-oracle-data 읽기 지침을 넣고 부모 호스트의 도구·승인 정책을 따른다. 이름이 적혔다는 이유로 권한을 새로 부여하지 않는다. 별도 DB 에이전트·MCP 서버는 추가하지 않았다.

## 검증 범위

단위 테스트는 mock 연결을 사용해 SQL 바인드 전달, 조회 전 검증, 행·데이터 예산, LOB 생략, 실패 시 rollback/close, 프로필 검증과 문서 연결을 확인한다. 실제 Oracle 11.2·19c, Client 로딩, 사내 인증·네트워크, 호스트 스킬 호출은 접속 환경이 없어 미검증이다. 이 제약을 해소하기 전에는 전체 버전 지원이나 실제 속도 개선 수치를 선언하지 않는다.

공식 규격: https://agentskills.io/specification

읽기·변경 스킬과 공통 import 구조는 [공용 데이터 접근](DATA_ACCESS.md), 용어와 이름은 [명명 규칙](NAMING.md)를 따른다.
