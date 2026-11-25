# ITSM 대상 시스템과 GitLab 저장소 연결표

ITSM 요청의 대상 시스템으로 이슈를 발행할 GitLab 프로젝트를 찾을 때 사용하는 플러그인 내부 지식이다. 운영 연결표는 [itsm-gitlab-routes.json](itsm-gitlab-routes.json)이다. 배치 CONFIG에서 기존 최상위 project_id를 제거하면 플러그인이 이 파일을 읽는다. 사내에서 별도로 관리하려면 CONFIG에 routing_file 경로를 지정한다. 상대 경로의 기준은 CONFIG 파일의 디렉터리다. routing_file이 있으면 항상 자동 배정을 사용한다.

운영 파일은 처음에 빈 배열이다. 아래 예시의 서버, ID, 토큰 환경변수, 작업 저장소를 실제 값으로 교체한 뒤 등록한다. repository는 디스패치할 때 필요하다.

```json
[
  {"target_system":"RTD","gitlab_url":"https://gitlab.example.invalid","project_id":101,"token_env":"RTD_TOKEN","repository":"/work/rtd"},
  {"target_system":"SCHED","gitlab_url":"https://gitlab.example.invalid","project_id":202,"token_env":"SCHED_TOKEN","repository":"/work/scheduler"}
]
```

## 대상 시스템별 등록 양식

아래 두 행은 작성 예시다. 운영에 사용할 행은 ITSM 시스템 코드 담당자와 GitLab 프로젝트 담당자가 실제 값을 대조한 뒤 등록한다.

| 구분 | ITSM 대상 시스템 | 구성요소 | GitLab 서버 | 프로젝트 ID | 저장소 경로 | 확인 근거 |
|---|---|---|---|---:|---|---|
| 예시 | RTD | 전체 | gitlab.example.invalid | 101 | fab/rtd | 예시 값 |
| 예시 | SCHED | 전체 | gitlab.example.invalid | 202 | fab/scheduler | 예시 값 |

운영 행에는 확인 근거로 ITSM 시스템 목록과 GitLab 프로젝트 위치, 확인일, 담당 팀을 기록한다. 같은 시스템이 API와 UI 저장소로 나뉘면 구성요소별로 한 행씩 등록한다. 개인 PC마다 달라지는 체크아웃 경로는 해당 PC의 CONFIG에서 dispatch.repository로 관리한다.

## 요청 한 건을 처리하는 순서

1. 접수할 때 ITSM 원본에서 대상 시스템과 필요한 구성요소를 확인한다. 확인된 운영 행이 정확히 하나일 때 해당 서버와 프로젝트 ID를 선택한다. 일치하는 행이 없거나 여러 개이면 발행을 보류하고 요청 담당자에게 확인한다.
2. 자동 배정용 Oracle 조회에 TARGET_SYSTEM 문자열 컬럼을 포함한다. 같은 시스템이 여러 저장소를 쓰면 COMPONENT도 반환하고 운영 파일의 각 행에 component를 지정한다. 시스템과 구성요소는 대소문자까지 일치해야 한다. 일치하는 행이 하나일 때만 발행한다. 동일 source 내 request_id는 시스템 전체에서 고유해야 한다.
3. 코드 작업을 배정하기 전에 대상 체크아웃에서 `git remote get-url origin`을 확인한다. SSH와 HTTPS 주소의 서버와 그룹/저장소 경로를 연결표와 대조한다. 예를 들어 `git@gitlab.example.invalid:fab/rtd.git`와 `https://gitlab.example.invalid/fab/rtd.git`는 위 RTD 예시의 같은 저장소를 가리킨다.
4. 발행된 이슈는 GitLab 서버, 프로젝트 ID, 이슈 IID를 함께 기록한다. 서로 다른 프로젝트에서 같은 IID가 나올 수 있다. 연결표가 바뀌었을 때 진행 중인 요청은 기존 이슈 URL을 확인한 뒤 재개한다.

실행 설정, 승인 및 재개 명령은 [ITSM과 GitLab 단계별 승인](../skills/vibeops-orchestrate-sdlc/references/itsm-gitlab.md)을 참조한다.
