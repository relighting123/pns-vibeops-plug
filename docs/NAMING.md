# 용어와 이름 규칙

| 용어 | 의미 | 현재 예 |
|---|---|---|
| Plugin | 설치·배포 단위 전체 | pns-vibeops-plug |
| Marketplace ID | 설치 카탈로그 식별자 | pns-vibeops-plug |
| Shared Wiki | 별도 공용 지식 저장소 | PNS VibeOps Wiki (`pns-vibeops-wiki`) |
| Agent | 담당 역할 | vibeops-develop |
| Skill | 작업 절차 | vibeops-read-iflow-data |
| Client | 접속·통신 코드 | http_client, oracle_client |
| Executor | 등록 명령 실행 | query_executor, write_executor |
| Operation | 호출 가능한 개별 기능 | 사내에서 등록한 operation ID |
| Policy | 허용 범위·실행 제한 | effect, allow_write, allowed_operations |
| Result | 반환 데이터·상태 | ok, outcome, truncated |

스킬은 `vibeops-<동사>-<대상>` 형태로 짓는다. 1~64자의 소문자·숫자·단일 하이픈을 사용하고 디렉터리와 `SKILL.md`의 `name`을 일치시킨다. Python 모듈은 snake_case를 사용한다. plugin_http처럼 배포 단위와 통신 모듈을 혼동시키는 이름은 쓰지 않는다.

- vibeops-read-oracle-data / vibeops-modify-oracle-data
- vibeops-read-iflow-data / vibeops-modify-iflow-data
- vibeops-read-cube-data / vibeops-modify-cube-data

읽기와 변경은 실제 effect로 판단한다. POST 조회도 read일 수 있다. 작업 취소·재처리·시작 등 업무 명령은 실API가 정해지면 cancel/retry/start 같은 별도 행동 스킬로 정의하고 기존 HTTP client를 재사용한다. 현재는 임의의 업무 명령을 만들어 등록하지 않았다.

3.0부터 플러그인 설치 ID와 스킬 호출 이름이 바뀐다. 예를 들어 Oracle 조회의 Claude 역할 설정은 `pns-vibeops-plug:vibeops-read-oracle-data`를 참조한다. Codex 프로젝트에 이전 역할 파일을 복사한 경우 새 역할 파일로 교체한다. GitLab 승인자 설정의 단계 키(예: `analyze-requirements`), SQLite 진행 상태, `SDLC_WIKI_*` 환경변수는 기존 값을 계속 사용한다.

공식 스킬 형식: https://agentskills.io/specification
