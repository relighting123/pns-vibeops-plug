# 저장소 작업 지침

이 저장소의 루트가 플러그인 패키지다. 작업을 시작하면 `git status --short`를 확인하고 사용자 변경을 보존한다. [기능별 개발 실습과 릴리스 절차](docs/HARNESS_GUIDE.md)에서 해당 작업의 파일과 완료 기준을 확인한다.

| 작업 | 먼저 확인할 곳 | 변경 뒤 확인할 것 |
|---|---|---|
| 스킬 추가 또는 수정 | `skills/<이름>/SKILL.md` | 이름과 폴더 일치, 호출 조건, 입출력, 실패 동작 |
| 역할 또는 배정 변경 | `config/role-skills.json`, 오케스트레이터 스킬 | 두 호스트 정의 재생성, 배정·회신 경로 |
| API 또는 DB 연동 | 해당 스킬의 assets, shared/python, [데이터 접근 가이드](docs/DATA_ACCESS.md) | 허용·거절·실패, 쓰기 결과 불명 처리 |
| 프로젝트 또는 공용 위키 | [지식 운영 가이드](docs/KNOWLEDGE_GUIDE.md) | 원본 근거, 발행 커밋, 대표 질문 |
| 훅 또는 패키지 배포 | hooks, 호스트별 매니페스트, CI | 깨끗한 환경 설치, 대표 호출, 복구 버전 |

스킬 이름은 `vibeops-<동사>-<대상>` 형태의 소문자 kebab-case로 짓는다. 예를 들어 `vibeops-inspect-release-notes`는 `skills/vibeops-inspect-release-notes/SKILL.md`의 front matter에도 같은 이름을 쓴다. 호출 시점은 description에, 절차와 완료 기준은 본문에 둔다. 긴 설명은 references, 예시는 assets, 실행 코드는 scripts에 둔다.

팀 검토안의 일반 변경 흐름은 `feat/<주제>` 또는 `fix/<주제>` → PR → `main`이다. 검증한 플러그인 소스에 `vX.Y.Z` 태그를 붙이고 패키지 ID `pns-vibeops-plug`와 마켓플레이스 ID `pns-vibeops-plug`를 유지한다. 버전 변경은 두 매니페스트에 함께 반영한다. 발행은 승인된 대상과 버전만 사용한다.

역할 변경 후 `python scripts/sync_agent_roles.py --write`를 실행한다. 작업 종료 전 `python -m unittest discover -s tests -v`, `python scripts/sync_agent_roles.py`, `git diff --check`를 확인한다. 검증한 명령과 결과, 호스트·사내 연동 등 미실행 항목을 PR에 남긴다.
