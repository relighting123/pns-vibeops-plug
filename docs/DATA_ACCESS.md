# Oracle·iFlow·Cube 공용 데이터 접근

## 구조와 실행

```text
skills/
  vibeops-read-oracle-data/scripts/oracle_client.py
  vibeops-modify-oracle-data/scripts/oracle_client.py
  vibeops-read-iflow-data/scripts/iflow_client.py
  vibeops-modify-iflow-data/scripts/iflow_client.py
  vibeops-read-cube-data/scripts/cube_client.py
  vibeops-modify-cube-data/scripts/cube_client.py
shared/python/
  http_client/          # HTTPS client·catalog·검증·retry·응답 한도
  oracle_client/        # 연결·조회·DML·CLI
  execution_policy/     # read/write 일치와 쓰기 실행 조건
  execution_result/     # 공통 오류·JSON 출력
  requirements.txt
```

각 스킬 진입 스크립트는 자신의 파일 위치에서 플러그인 루트를 계산해 shared/python을 import 경로에 넣고 해당 client의 main을 호출한다. 현재 작업 디렉터리에 의존하지 않는다. 플러그인 전체를 배포해야 하며 개별 스킬만 복사하면 공유 모듈이 빠진다. 에이전트 런타임·MCP 서버·상시 데몬은 없다.

Python 3.11+ 환경에 shared/python/requirements.txt를 설치한다. 사내 패키지 저장소 또는 승인된 오프라인 wheel을 사용할 수 있다. CI는 HTTP 검증에 필요한 HTTPX/jsonschema 고정 버전만 설치한다. Oracle 드라이버는 실제 연결 시에만 import한다. 의존성 버전은 DB·Client 호환성 검증 후 갱신한다.

## 공통 설정

접속 프로필과 operation/SQL catalog는 플러그인 외부 운영자 관리 디렉터리에 둔다. 예시는 각 스킬 assets/에 있으며 실제 데이터나 주소가 아니다. example/EXAMPLE-ONLY로 된 엔드포인트와 SQL은 교체 전 실사용할 수 없다. 실제 iFlow/Cube 엔드포인트·파라미터·권한은 제공되지 않았으므로 추정 구현하지 않았다.

API 명세가 OpenAPI로 이미 있다면 등록 catalog를 검토해 변환하고 이중 관리하지 않는 절차를 추가할 수 있다. 현재 OpenAPI 자동 importer는 없다.

## HTTP 호출

1. 대상 스킬 assets/profiles.example.json과 operations.example.json을 외부로 복사한다.
2. profile.service를 iflow 또는 cube로 지정한다. operations_file은 catalog의 절대 경로다.
3. base_url_env가 가리키는 환경변수에 HTTPS 기본 주소를, auth.token_env에는 토큰을 주입한다.
4. HTTP_ACCESS_CONFIG에 profiles JSON 경로를 설정한다. 사용자 요청은 profile과 operation ID만 선택하고 URL·인증 헤더를 직접 바꿀 수 없다.
5. 실제 API에 맞게 method/path/request_schema/effect/response_fields를 등록한다. JSON Schema 2020-12로 path/query/body 전체를 검사한다. examples는 추가 파라미터를 금지한다. optional 값의 default는 schema에서 자동 주입하지 않으며 명시적으로 전달한다.

```bash
python /plugin/skills/vibeops-read-iflow-data/scripts/iflow_client.py --profile iflow-development --request /protected/read.json
python /plugin/skills/vibeops-modify-iflow-data/scripts/iflow_client.py --profile iflow-write --request /protected/change.json --apply
```

Cube는 대응하는 cube_client.py와 Cube profile을 사용한다. --request -는 stdin을 사용한다. 읽기는 동일 profile 요청 1~10개를 배열로 묶어 같은 HTTP Client/TCP 연결을 재사용한다. 변경은 한 번에 1개만 허용한다. 스크립트 종료 후 연결이 유지되지는 않는다.

### 인증·네트워크

현재 auth.type은 none/bearer/header를 지원한다. OAuth 토큰 자동 발급·갱신, 쿠키 로그인, 파일 multipart, 임의 헤더 입력은 구현하지 않았다. mTLS는 client_cert/client_key, 사내 CA는 ca_file을 외부 profile에서 지정한다. 비밀키 암호 처리 등 추가 인증은 별도 구현이 필요하다.
TLS 검증을 끄는 옵션은 없다. 자동 redirect를 막는다. HTTPX의 자동 환경 proxy 사용은 끄고 명시적 profile.proxy를 지원한다. base URL과 catalog는 신뢰 설정이며 실제 네트워크 접근 통제는 방화벽·호스트 권한·서버 인증으로 한다. 토큰·프로필·catalog를 수정할 수 있는 에이전트에게 독립된 보안 경계를 제공하지는 않는다.

### 안정성과 결과

- connect/read/write/pool 타임아웃을 별도 지정. 이는 전체 응답의 절대 기한이 아니므로 호스트의 실행 기한도 설정한다.
- operation effect=read이고 retry_safe=true인 기능만 429/502/503/504 또는 transport 실패에 제한된 재시도. 지수 대기·jitter를 적용하며 Retry-After 정수 초가 5초를 초과하면 실패 반환한다. HTTP-date 형식은 별도 해석하지 않고 기본 대기를 사용한다.
- write는 method에 관계없이 1회 호출한다. timeout·연결 단절·비정상 응답은 outcome=unknown으로 보고 사후 상태를 조회한다. 서버가 제공하는 멱등키/작업 ID는 실제 API 스키마에 등록해 전달해야 한다. 로컬 중복 실행 저장소는 없다.
- HTTP 2xx는 outcome=accepted일 뿐 비동기 업무 완료의 증거가 아니다. 결과가 202이면 작업 ID로 후속 조회하는 업무 스킬을 실제 API에 맞게 추가한다.
- raw 오류·URL·인증값은 출력하지 않는다. 성공 JSON은 response_fields의 최상위 필드를 선택해 줄일 수 있다. 민감 정보 제거는 서버 응답 계약과 catalog의 필드 선택도 함께 검토한다.
- max_request_bytes와 max_response_bytes를 적용한다. 큰 응답은 body=null/truncated=true로 반환한다. 응답 해제 크기 기준이며 JSON 메타데이터까지 포함한 최종 stdout 하드 제한은 아니다. 출력만 잘린다고 서버 작업이 취소되지는 않는다.
- 타임아웃 외 별도 전역 rate limiter나 여러 프로세스 간 요청 할당량 조정은 없다. 각 API의 실제 quota에 맞춰 추가할 수 있다.

## Oracle 읽기·변경

ORACLE_ACCESS_CONFIG에 외부 databases 프로필 경로를 지정한다. 기존 ORACLE_QUERY_CONFIG도 호환 입력으로 받는다. 자격증명은 프로필의 dsn_env/user_env/password_env로 주입한다. 읽기 계정과 변경 계정/profile을 분리하는 것이 권장된다.

읽기는 기존 check/describe/등록 query를 유지한다. 등록 SELECT catalog에는 effect=read가 필요하다. shared/python/oracle_client/query_executor.py가 기존 실행 코드를 제공하며 connections.py로 접속 구현을 분리했다. 조회 규칙·버전별 접속은 vibeops-read-oracle-data/references를 따른다.

변경은 vibeops-modify-oracle-data/assets의 예시로 writes catalog를 등록한다. profile에 allow_write=true, allowed_writes, writes_file 절대 경로를 지정한다. 요청은 operation/binds/expected_rows다.

```bash
python /plugin/skills/vibeops-modify-oracle-data/scripts/oracle_client.py --database write-development --request /protected/change.json --apply
```

등록된 단일 INSERT/UPDATE/DELETE만 실행한다. DDL/PLSQL/MERGE는 현재 범위에 없다. 바인드 키를 검증하고 실제 rowcount가 expected_rows와 정확히 같을 때 commit한다. 불일치·실행 실패는 rollback한다. rowcount 확인은 실행 뒤 이루어지므로 서버에서 처리한 행 수·스캔량을 미리 제한하지 않는다. 등록 SQL에 키·현재값 조건을 넣어 변경 범위를 한정한다. commit 응답을 잃으면 성공/실패를 추정하지 않고 unknown으로 반환하며 재실행 전에 현재 상태를 확인한다.
--apply가 없으면 실행 전 차단한다. 변경을 시험 실행하고 rollback하는 dry-run 기능은 없다. 사용자 권한이나 승인 자체를 자동 증명하지는 않으므로 호스트가 요청 범위·대상을 확인한 후 실행해야 한다.
SQL syntax guard와 rowcount는 완전한 보안/업무 검증이 아니다. 트리거·함수·자율 트랜잭션 등은 catalog와 계정 권한에서 검토한다. 데이터 변경 후 별도 읽기로 업무 후조건을 검증한다. 불일치 시 이미 commit한 변경을 rollback할 수 없으며 승인된 보상 변경이 필요하다.

## 역할 연결과 검증

기존 에이전트가 필요한 스킬을 검색해 사용한다. 시작 시 여섯 스킬 전부를 preload하지 않는다. 읽기 전용 리뷰어는 구체적인 실행 요청을 부모에게 반환한다. Codex는 부모의 도구·권한을 상속한다. 별도 DB/API 담당 에이전트는 추가하지 않는다.
단위 검증은 HTTPX MockTransport와 Oracle 가짜 연결을 사용한다. 실제 사내 API, Oracle DB, mTLS/CA/proxy, 호스트 설치·모델 스킬 수행은 미검증이다. 성능·토큰 절감 수치는 선언하지 않는다.

공식 참고:
- https://www.python-httpx.org/advanced/clients/
- https://www.python-httpx.org/advanced/timeouts/
- https://python-oracledb.readthedocs.io/en/v3.4.0/user_guide/txn_management.html

## 로컬 역할 설정

각 외부 Oracle database 또는 HTTP profile 안에 아래처럼 role_access를 추가합니다. requirements는 iFlow·Cube 조회, develop은 Oracle 조회에 배정합니다. 스킬을 실행하는 한 명령에 SDLC_DATA_ROLE을 해당 역할로 설정합니다. Unix 키는 실행 계정명, Windows 키는 whoami /user에 표시되는 SID입니다.

```json
{"role_access":{"requirements":{"YOUR_OS_USER_OR_SID":["read"]}}}
```

기존 프로필도 설정을 추가해야 합니다. 역할·계정·효과 중 하나라도 일치하지 않으면 실행이 거절됩니다. 기존 작업 ID 허용 목록과 쓰기 승인도 그대로 적용됩니다. 같은 OS 계정에 두 역할을 부여하면 둘 다 선택할 수 있습니다. 이 검사는 로컬 프로필을 신뢰하며 서브에이전트 자체의 신원을 증명하지 않습니다. 실제 권한 한도는 서비스 계정과 토큰에서 관리합니다.
