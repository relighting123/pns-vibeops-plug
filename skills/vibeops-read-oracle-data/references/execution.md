# 실행 절차·설정·도구 계약

## 설치

사내망 접근이 가능한 실행 PC/서버에서 Python 3.11 이상과 shared/python/requirements.txt의 고정 드라이버를 설치한다. 사내 패키지 저장소나 승인된 오프라인 wheel을 사용할 수 있다. requirements.txt는 DB 도구의 의존성만 선언한다.

1. assets/profiles.example.json과 queries.example.json을 플러그인 외부의 운영자 관리 디렉터리로 복사한다.
2. 실제 DB마다 연결 ID와 mode를 설정한다. queries_file은 외부 쿼리 파일의 절대 경로다. 등록 SQL은 코드와 동일하게 검토·관리한다.
3. dsn_env, user_env, password_env가 가리키는 환경변수를 사내 자격증명 관리 절차로 주입한다. 값 자체를 커맨드라인·Git·MD에 기록하지 않는다.
4. ORACLE_ACCESS_CONFIG를 프로필 파일 경로로 설정한다. 호스트가 해당 환경을 상속하는지 확인한다.
5. --help 확인 뒤 check를 실행한다. check도 실제 연결하며 SELECT 1 FROM dual을 실행한다.

```bash
python /plugin/skills/vibeops-read-oracle-data/scripts/oracle_client.py --database development --request /protected/request.json
```

환경에 따라 python3 명령을 사용한다. --request -는 표준 입력으로 JSON을 받는다. 스크립트는 설정이나 SQL을 자동 생성·수정하지 않는다.

## 입력

한 호출에는 같은 DB의 요청 배열 1~20개를 넣는다.

| action | 필드 | 동작 |
|---|---|---|
| check | 없음 | 접속·기본 조회 확인 |
| describe | owner, table | 허용 owner의 일반 테이블/뷰 컬럼 조회; quoted 이름은 미지원 |
| query | query, binds | 해당 프로필 allowed_queries에 포함된 등록 쿼리 실행 |

max_rows는 요청별로 프로필 한도 이하로 줄일 수 있다. 바인드 키는 등록 쿼리의 binds 목록과 정확히 일치해야 한다. 값은 JSON에서 전달 가능한 문자열·숫자·null 등을 사용한다. 날짜 문자열의 변환은 등록 SQL에서 포맷을 명시한다. 현재 복합 객체 바인드·자동 날짜 타입 변환은 제공하지 않는다.

## 출력·종료 코드

성공: ok, database, database_version, mode, connect_ms, total_ms, results.
각 결과: query, columns, rows, returned_rows, truncated, execute_ms, fetch_ms.
행은 컬럼명 순서의 배열이다. 숫자 Decimal은 정밀도 보존을 위해 문자열, 날짜는 ISO 문자열, bytes는 base64, LOB/미지원 객체는 omitted_type으로 반환한다. 세션 시간대가 없는 DATE에 시간대를 추정해 붙이지 않는다.

종료 코드 0은 요청 실행 성공, 1은 검증·접속·실행 실패다. 원본 Oracle 오류에는 호스트·SQL·데이터가 포함될 수 있어 공통 오류와 가능한 ORA/DPY/DPI 코드만 반환한다. 실패 시 부분 결과를 성공으로 반환하지 않는다.

## 한도와 제약

max_rows는 반환 행 수, max_result_bytes는 배치 전체의 컬럼명·행 JSON 데이터 예산이다. 최종 응답의 부가 필드까지 포함한 하드 바이트 제한은 아니다. DB 서버의 전체 스캔량도 제한하지 않는다. 승인된 SQL에서 조건·집계·필요 컬럼으로 DB 작업량을 줄인다.
call_timeout_ms는 단일 DB 왕복의 제한이다. 연결 시간이나 호출 전체의 기한이 아니다. 외부 DSN/Oracle Net 접속 시간 제한 및 호스트의 프로세스 실행 기한을 추가로 설정한다. CLI 종료가 서버 쿼리 중단을 즉시 보장한다고 가정하지 않는다.

한 배치의 조회는 SET TRANSACTION READ ONLY 이후 같은 연결에서 실행하고 마지막에 rollback/close한다. 배치 사이 연결 풀이나 결과 캐시는 없다. 하나의 요청을 위해 전체 스키마 덤프를 하지 않는다.
