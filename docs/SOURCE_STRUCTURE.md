# 소스 구조

저장소 루트 자체를 하나의 설치 가능한 플러그인으로 구성한다. Superpowers처럼 skills/, agents/, hooks/와 호스트별 매니페스트를 함께 둔다. Superpowers 코드나 기능 전체를 가져온 변경은 아니다.

| 폴더 | 읽는 주체와 용도 |
|---|---|
| skills/ | 호스트가 작업 절차를 읽는다. 공통 원본이자 설치 파일이다. |
| agents/ | Claude가 역할과 도구 목록을 읽는다. |
| .codex/agents/ | Codex 프로젝트 역할 설정. 대상 프로젝트에 별도 설치한다. |
| hooks/ | 호스트가 시작 이벤트에서 sh 스크립트를 실행한다. |
| .claude-plugin/ | Claude 매니페스트·마켓플레이스 등록 |
| .codex-plugin/ | Codex 매니페스트 |
| docs/ | 개발·확장·검증 설명 |
| tests/ | 구조와 훅 실행 검사 |

실행 흐름: 사용자 요청 → vibeops-orchestrate-sdlc → 현재 단계 스킬 → 호스트 도구/서브에이전트 → 실제 변경·검사 → 상위 에이전트 검토.
필요하면 vibeops-search-wiki로 제한된 근거를 읽고 vibeops-manage-worktrees로 격리·통합·정리한다.

읽기·변경 스킬과 공통 import 구조는 [공용 데이터 접근](DATA_ACCESS.md), 용어와 이름은 [명명 규칙](NAMING.md)를 따른다.
