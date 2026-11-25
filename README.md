# PNS VibeOps Plug

저장소 루트가 Codex·Claude Code 플러그인입니다. skills/ 한 곳에서 지침을 관리하며 배포용 복사본이나 동기화 과정이 없습니다. 별도 모델 실행 엔진은 없습니다.

## 구조

| 경로 | 역할 |
|---|---|
| skills/ | SDLC 단계·워크트리·위키·데이터 연동 스킬 18개 |
| agents/ | Claude 서브에이전트 정의 12개 |
| .codex/agents/ | Codex 프로젝트 역할 설정 12개 |
| hooks/ | 공통 SessionStart 안내와 이벤트 설정 |
| .claude-plugin/ | Claude 매니페스트와 마켓플레이스 |
| .codex-plugin/ | Codex 호환 매니페스트 |
| .agents/plugins/ | Codex 마켓플레이스: 저장소 루트를 가리킴 |
| docs/ | 구조·개발·확장 가이드 |
| tests/ | 플러그인 구조와 훅 검사 |

## 사용

Claude Code 로컬 설치: 저장소 루트에서 `claude --plugin-dir .`.
마켓플레이스 등록: `/plugin marketplace add relighting123/pns-vibeops-plug` 후 `/plugin install pns-vibeops-plug@pns-vibeops-plug`.
Codex는 지원되는 플러그인 설치 UI에서 이 저장소의 루트 패키지를 설치합니다. 명명된 Codex 역할은 대상 프로젝트의 `.codex/agents/`에 제공 파일을 복사해야 하며 기존 파일을 덮어쓰지 않습니다. 플러그인 설치가 프로젝트 설정을 자동 설치하지는 않습니다.
훅에는 sh와 호스트의 훅 신뢰 설정이 필요합니다. 호스트별 실제 설치 및 모델 작업 수행은 별도 확인이 필요합니다.

요청 예: “vibeops-orchestrate-sdlc로 검색 기능을 구현하고 테스트·리뷰까지 진행해줘. 설계 근거가 부족하면 wiki를 검색하고 병렬 수정은 worktree로 격리해줘.”

기존 설치에서 3.0으로 옮길 때는 기존 플러그인을 비활성화하고 새 ID로 설치합니다. 대상 프로젝트에 복사한 기존 역할은 새 정의로 교체하고 프롬프트와 스크립트의 스킬 이름을 갱신합니다. [이름과 호환 범위](docs/NAMING.md)

## 개발

skills/ 원본을 직접 수정합니다. 역할 정의는 `config/role-skills.json`에서 관리하고 `python scripts/sync_agent_roles.py --write`로 두 호스트 파일을 생성합니다.
`python3 -m unittest discover -s tests -v`로 구조를 검사합니다. Python은 개발 검증에만 사용됩니다.

[개발가이드](docs/DEVELOPER_GUIDE.md) · [소스 구조](docs/SOURCE_STRUCTURE.md) · [추가 개발 체크리스트](docs/EXTENSION_CHECKLIST.md) · [위키·워크트리](docs/WIKI_WORKTREES.md)

Oracle 조회 공용 스킬 `vibeops-read-oracle-data`을 추가했습니다. [설치·공통 지식·검증 범위](docs/ORACLE_SKILL.md)를 확인하세요. 접속 프로필과 인증값은 플러그인 밖에서 관리합니다.

공용 데이터 연동: Oracle·iFlow·Cube의 읽기/변경 스킬을 분리하고 shared/python 클라이언트를 공유합니다. [설정과 예제](docs/DATA_ACCESS.md) · [용어·이름 규칙](docs/NAMING.md). iFlow/Cube 실제 API 명세는 사내 설정으로 등록해야 합니다.

DB 계정과 API 인증 프로필은 [자격증명 위키](wiki/Credentials.md)에서 확인한다.

**PNS VibeOps Wiki**의 공용 지식 검색에는 `vibeops-search-shared-knowledge` 스킬을 사용합니다. `config/shared-knowledge.json`에서 Git 주소, 브랜치, 로컬 저장소 경로를 설정할 수 있습니다. `SDLC_WIKI_URL`, `SDLC_WIKI_BRANCH`, `SDLC_WIKI_LOCAL`로 각각 덮어쓸 수 있습니다. 매 검색 시 원격 브랜치의 최신 커밋을 조회합니다. 같은 저장소의 로컬 커밋이 일치하고 위키에 변경이 없으면 재사용하고, 다르면 해당 커밋의 캐시를 사용하거나 내려받습니다. 최신 확인에 실패한 경우 기존 캐시 결과에 `stale-unverified`가 표시됩니다.
