# VibeOps 로컬 환경 설정

대상 코드 저장소에서 아래 명령을 실행한다. PLUGIN_ROOT는 설치본 또는 플러그인 소스의 절대경로다. Python 환경에는 httpx와 Oracle용 oracledb를 준비한다.

```bash
python3 "$PLUGIN_ROOT/skills/vibeops-orchestrate-sdlc/scripts/setup_environment.py"
python3 "$PLUGIN_ROOT/skills/vibeops-orchestrate-sdlc/scripts/setup_environment.py" --check
```

마법사는 Git 최상위 경로와 origin의 서버 및 그룹/저장소를 제안한다. 운영자는 ITSM 시스템 코드와 필요시 구성요소를 입력하고 GitLab 목적지를 확인한다. 토큰은 터미널에 숨김 입력한다. GitLab에서 프로젝트 ID와 이슈 읽기 권한을 확인한다. 토큰은 사용자 전용 권한의 로컬 파일에 저장된다. 기본 CONFIG는 ~/.config/pns-vibeops/batch.json이다. 동일 CONFIG로 마법사를 다시 실행하면 시스템을 추가하거나 해당 매핑을 수정할 수 있다.

| 설정 | 점검 |
|---|---|
| ITSM Oracle | requirements 역할에 조회 권한을 부여하고 등록 SELECT에 REQUEST_ID, REVISION, TITLE, SUMMARY, TARGET_SYSTEM과 CREATED_AT을 포함한다. 시스템별 구성요소가 필요하면 COMPONENT도 포함한다. |
| 오래된 요청 우선 | Oracle에서 페이지를 자르기 전에 접수 시각 오름차순과 REQUEST_ID 오름차순을 적용한다. CREATED_AT은 오프셋을 포함한 ISO 8601 문자열이다. Python은 시차를 반영해 후보를 재정렬한다. 운영 조회나 페이지 기준은 같은 오래된 행만 계속 반환하지 않도록 진행 상태에 맞게 구성한다. |
| GitLab | 토큰에 운영 프로젝트 이슈 읽기와 쓰기 권한을 부여한다. 점검은 읽기 API만 사용한다. 최초 발행은 테스트 프로젝트에서 확인한다. |
| 디스패치 | CONFIG의 dispatch에 worktrees, base_ref, workers, 단계별 approvers 및 verify_command를 지정한다. GitLab 승인과 워커 여유가 있는 후보부터 배정된다. 배포는 필요한 경우에 승인 및 명령을 설정한다. |
| 워커 호스트 | 에이전트 역할이 설치된 세션에서 대표 티켓 1건을 승인하고 워커가 실제 배정되는지 확인한다. 자동 반복은 호스트 예약 실행에서 구성한다. |
| 공용 위키 | config/shared-knowledge.json 또는 SDLC_WIKI_URL과 SDLC_WIKI_BRANCH를 설정한다. 새 오케스트레이션에서 원격 SHA 확인과 로컬 사본 사용을 점검한다. |
| 상태 | 같은 자동화 계정으로 이슈의 작업 상태 댓글을 읽고 쓴다. 재실행 시 이슈 IID 유지와 워커 한도를 확인한다. |

[배치와 승인 설정](itsm-gitlab.md)
