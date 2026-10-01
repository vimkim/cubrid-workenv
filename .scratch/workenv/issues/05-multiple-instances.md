# 05: 서버·broker·PL의 worktree 간 공존

**What to build:** 서로 다른 물리 DB를 가진 두 worktree에서 같은 DB 이름으로 서버·broker·PL을 사용하고 한쪽 stop이 다른 쪽에 영향을 주지 않게 한다.

**Blocked by:** 01

**Status:** ready-for-agent

Parent: [구현 명세](../spec.md)
User stories: 11, 12, 13, 19, 21, 22

## Acceptance criteria

- [ ] 일반 서버·broker·PL 실행에 필요한 설정과 환경을 생성하며 HA와 CUBRID Manager는 활성화하지 않는다.
- [ ] master와 broker 포트, broker MASTER/APPL_SERVER shared-memory key를 구분해 배정한다. 실제 사용하는 broker 설정의 관련 자원 누락을 점검한다.
- [ ] master·PL socket 경로가 분리되고 socket 길이 제한을 만족한다. 설치 경로 아래 PL 관련 파일도 별도 설치 선택으로 충돌하지 않는지 확인한다.
- [ ] 두 환경의 DB 이름이 같아도 server status는 자기 서버만 표시하고 일반 csql은 자기 DB의 sentinel 값을 읽는다.
- [ ] A의 server stop, broker stop을 각각 실행한 뒤 B의 DB 접속과 broker 사용이 계속 성공한다.
- [ ] 두 PL 서버를 실제 사용해 socket과 설정 분리가 동작함을 확인한다. 환경 제약으로 실행하지 못한 항목은 통과로 간주하지 않는다.
- [ ] 호스트 TMP를 container와 공유하도록 설정하지 않는다. broad pkill이나 다른 인스턴스 IPC 삭제를 테스트 정리 수단으로 사용하지 않는다.

## Scope and context

01의 실제 초기화 흐름을 확장한다. master 포트만 분리된 상태를 broker·PL까지 검증한 것으로 보고하지 않는다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.
