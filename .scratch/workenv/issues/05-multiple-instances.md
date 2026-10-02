# 05: 서버·broker·PL의 worktree 간 공존

**What to build:** 서로 다른 물리 DB를 가진 두 worktree에서 같은 DB 이름으로 서버·broker·PL을 사용하고 한쪽 stop이 다른 쪽에 영향을 주지 않게 한다.

**Blocked by:** 01

**Status:** ready-for-human

Parent: [구현 명세](../spec.md)
User stories: 11, 12, 13, 19, 21, 22

## Acceptance criteria

- [x] 일반 서버·broker·PL 실행에 필요한 설정과 환경을 생성하며 HA와 CUBRID Manager는 활성화하지 않는다.
- [x] master와 broker 포트, broker MASTER/APPL_SERVER shared-memory key를 구분해 배정한다. 실제 사용하는 broker 설정의 관련 자원 누락을 점검한다.
- [x] master·PL socket 경로가 분리되고 socket 길이 제한을 만족한다. 설치 경로 아래 PL 관련 파일도 별도 설치 선택으로 충돌하지 않는지 확인한다.
- [x] 두 환경의 DB 이름이 같아도 server status는 자기 서버만 표시하고 일반 csql은 자기 DB의 sentinel 값을 읽는다.
- [x] A의 server stop, broker stop을 각각 실행한 뒤 B의 DB 접속과 broker 사용이 계속 성공한다.
- [x] 두 PL 서버를 실제 사용해 socket과 설정 분리가 동작함을 확인한다. 환경 제약으로 실행하지 못한 항목은 통과로 간주하지 않는다.
- [x] 호스트 TMP를 container와 공유하도록 설정하지 않는다. broad pkill이나 다른 인스턴스 IPC 삭제를 테스트 정리 수단으로 사용하지 않는다.

## Scope and context

01의 실제 초기화 흐름을 확장한다. master 포트만 분리된 상태를 broker·PL까지 검증한 것으로 보고하지 않는다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.

## Acceptance evidence

- `python3 -m unittest discover -s tests -v`: 9 public CLI/artifact tests passed.
  New tests cover four distinct ports/keys across two environments, explicit broker
  configuration and PL UDS, actual occupied SysV key avoidance, and refusal of a
  shared installation. Existing fake-install fixtures now use separate copies.
- TDD: the broker/PL artifact test first failed with missing `broker_port`, then
  passed after allocation/settings/environment implementation. Supplemental IPC
  and dedicated-install regression checks passed.
- `python3 tests/real_coexistence.py --install /home/vimkim/.cub/install/develop/debug_gcc --java-home /home/vimkim/.local/share/mise/installs/java/temurin-8 --output /tmp/cwe05-real-final`: passed.
- [Structured evidence](../../../tests/evidence/ticket05/results.json) records
  commands, return codes, 11.5.0.2602-a0026f9 binary hash, normalized Java selection,
  ports, IPC keys, PL process information, and distinct master/PL socket paths.
- Same-name databases returned [A=111](../../../tests/evidence/ticket05/a-health-jdbc.txt)
  and [B=222](../../../tests/evidence/ticket05/b-health-jdbc.txt) through real JDBC.
  Both called Java `Math.abs` through SQL and returned 17, proving PL execution.
- B completed committed SQL writes and real JDBC/PL calls after
  [A server stop](../../../tests/evidence/ticket05/b-after-a-server-stop-jdbc.txt)
  and [A broker stop](../../../tests/evidence/ticket05/b-after-a-broker-stop-jdbc.txt).
  A's subsequent server status was empty while B remained usable.
- [IPC inventory](../../../tests/evidence/ticket05/ipc-before-stop.txt) contains all
  four allocated broker segments. Final cleanup recorded empty owned-PID and IPC
  lists; copied installations and disposable databases were removed. Only exact
  installation-owned PIDs were signalled after native stop commands.
- Generated service list is `server,broker`, HA is off, and PL UDS uses host TMP.
  No container path or shared installation was changed.

## Interfaces and limits

- Allocation record adds `broker_port`, `broker_master_shm_id`,
  `broker_appl_server_shm_id`, and normalized `install`. `allocate` accepts keyword
  `install`, `shm_start`, `shm_end`; default finite SysV pool is
  `0x62000000..0x6200ffff`. Each allocation consumes two TCP ports and two IPC keys.
- `--java-home` (default `JAVA_HOME`) records `java_home` and exports
  `CUBRID_JAVA_HOME`. No selection uses the CUBRID build's default Java.
  `CUBRID_BROKER_CONF_FILE` selects the generated single-broker configuration.
- One installation per cooperating worktree is enforced inside the allocation
  lock because PL information files live under `$CUBRID/var/pl`. All cooperating
  environments must use the same host allocation namespace. These checks are
  allocation-time conflict avoidance, not lasting OS reservations.
- This installed build passed with Temurin 8.0.462. An initial Temurin 21 run
  [failed PL startup](../../../tests/evidence/ticket05/java21-startup-failure.txt)
  with native `CallStaticIntMethod` error; Java 21 support is not claimed. The
  incompatible attempt's owned processes were stopped and its temporary files
  removed. Other builds/Java combinations, HA, Manager and containers are outside
  this evidence.
- Ticket 03 validates user-selected DB names against the PL UDS length limit;
  this ticket validates the default testdb path. Ticket 04 must include both ports,
  both IPC keys and dedicated installation ownership when reclaiming allocations.
- Ready for parent review; not declared integrated.
