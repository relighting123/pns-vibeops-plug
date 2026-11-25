# Oracle 공통 지식: 연결과 호환성

범위: vibeops-read-oracle-data 자체 스크립트. 사내 DB 개별 정보는 포함하지 않음.
근거: python-oracledb 3.4.x 공식 문서. 문서 확인: 2026-11-18. 실DB 검증 상태: 미검증.

## 버전 선택

| 환경 | 구성 후보 | 확인할 사항 |
|---|---|---|
| Oracle 19c | Thin 또는 Thick | 인증·암호화·네트워크 요구 조건 |
| Oracle 11.2 | Thick + 적합한 Client, 우선 Client 19 조합 검토 | 정확한 서버/Client 패치·OS·인증 |
| Oracle 11.1 및 기타 버전 | 개별 검증 후 지원 결정 | 11g라는 이름만으로 지원 선언 금지 |

이 스킬의 의존성 기준은 python-oracledb 3.4.2다. 최신 드라이버의 테스트/지원 범위가 같다고 가정하지 않는다. 3.4 계열 Thin은 12.1 이상, Thick의 Client19 연결은 11.2 이상이라는 공식 상호운용 설명을 기준으로 한다. 현재 코드가 실제 11.2·19c 서버에서 검증되었다는 뜻은 아니다.

Thin/Thick은 프로세스 단위로 고정되므로 프로필마다 별도 CLI 호출한다. 실행 도중 Thin 실패 후 자동 Thick 재시도는 하지 않는다. 잘못된 대상 접속·중복 작업·애매한 오류를 줄이기 위해 시작 전에 mode를 정한다.

Thick에서는 첫 연결 전에 init_oracle_client를 호출한다. Linux는 Client 라이브러리를 프로세스 시작 전 시스템 라이브러리 검색 경로에 설정하며 lib_dir은 설정하지 않는다. Windows 등 lib_dir 지원 환경은 외부 프로필에 설정할 수 있다. config_dir은 Oracle Net 구성 위치다.

DSN은 환경변수로 받는다. service_name, SID, TNS alias, 전체 connect descriptor의 차이는 운영자가 정확한 DSN으로 설정한다. 스크립트가 서비스명과 SID를 추정하지 않는다. 현재 인증은 환경변수 사용자/비밀번호 방식이며 Wallet·외부 인증을 구현했다고 가정하지 않는다.

## 장애 분류

- 의존성/Client 로딩 실패: Python·드라이버·아키텍처·Client 검색 경로를 점검.
- 리스너/접속 실패: 실행 PC의 사내망 접근·DNS·포트·서비스/SID·Oracle Net 설정 점검.
- 인증 실패: 자격증명·계정 상태·암호 verifier/프로토콜 호환성을 운영자에게 확인. 자동 보안 설정 하향 금지.
- 객체 없음/권한 부족: 소유자·뷰·동의어·계정 권한 확인. DBA 권한 추가 요청으로 우회하지 않음.

출처:
- https://python-oracledb.readthedocs.io/en/v3.4.0/user_guide/installation.html
- https://python-oracledb.readthedocs.io/en/v3.4.0/user_guide/initialization.html
- https://python-oracledb.readthedocs.io/en/v3.4.0/api_manual/connection.html
