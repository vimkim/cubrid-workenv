# CUBRID 인스턴스 격리 인계: 충돌 자원과 탐색 경로

## 이 문서를 읽을 때

호스트에서 여러 CUBRID 인스턴스(`cub_master`, `cub_server`, broker, PL 서버)가 서로 간섭하지 않도록 자원을 배정하는 작업을 시작하기 전에 읽는다. [요구사항](requirements.md)의 "DB 이름, 포트, UDS 경로, 설정 파일, shared memory 설정의 충돌 방지"를 구현할 때 무엇을 분리해야 하는지 정리했다.

근거는 CUBRID 소스 `/home/vimkim/gh/cb/my-cubrid-runtime-testdir` (커밋 `c63a3b993`, 11.5.x 개발 브랜치)를 읽은 결과다. 아래 표의 "근거" 열에 소스 위치가 있으면 코드로 확인한 사실이고, "미확인"으로 표시한 항목은 검증하지 않은 내용이다. 실제 프로세스를 띄워 격리를 실험한 결과는 아니다. 구현 후에는 확인 시나리오를 실제로 실행해 검증한다.

## 핵심: 인스턴스는 프로세스 탐색이 아니라 포트로 서로를 찾는다

`csql`, `cubrid server status`, `cub_server` 어느 것도 `ps`나 `/proc`로 다른 프로세스를 찾지 않는다. 모두 다음 경로로 같은 `cub_master`에 도달한다.

```
$CUBRID                     필수. 없거나 디렉터리가 아니면 즉시 exit       environment_variable.c:97
  ├ 설정 파일 = $CUBRID_CONF_FILE, 없으면 $CUBRID/conf/cubrid.conf        system_parameter.c:6353-6367
  ├ cubrid_port_id = 설정 파일 값 (기본 1523)                             system_parameter.c:1563
  │     이후 환경변수 CUBRID_CUBRID_PORT_ID 가 있으면 덮어씀              prm_check_environment, system_parameter.c:7355, :6432
  └ master UDS = ${CUBRID_TMP:-/tmp}/CUBRID<port>   예: /tmp/CUBRID1523   connection/tcp.c:139
```

- `cub_server demodb`는 기동 시 자신의 `gethostname()`과 `cubrid_port_id`로 master에 접속해 이름 `demodb`로 등록하고, 그 연결을 계속 유지한다 (`connection/connection_cl.cpp` `css_connect_to_master_server`). 같은 master에 같은 이름이 이미 있으면 `SERVER_ALREADY_EXISTS`로 실패한다.
- `csql -udba demodb`는 `$CUBRID_DATABASES/databases.txt`에서 `demodb`의 host 열을 찾고(`base/databases_file.c:1064` `cfg_find_db`, `CUBRID_DATABASES`가 없으면 현재 디렉터리의 `databases.txt`), `host:cubrid_port_id`의 master에 이름을 보낸다. master는 등록 목록에서 이름을 `strcmp`로 찾아(`executables/master.c:1522`) 클라이언트 소켓을 서버에 넘긴다(`master.c:744`). 없으면 `SERVER_NOT_FOUND`.
  - `demodb@host` 형식이면 `databases.txt`를 건너뛰고 그 host를 쓴다 (`transaction/boot_cl.c:550-610`).
- `cubrid server status`는 master 존재를 확인한 뒤 `cub_commdb -P`를 실행한다 (`executables/util_service.c:1853`). `cub_commdb`는 `"localhost"`와 자신의 `cubrid_port_id`로 master 하나에 `GET_SERVER_LIST`를 보내고(`commdb.c:1214`, `:1418`), master는 자신에게 등록된 서버만 응답한다 (`master_request.c:286`). 따라서 다른 포트의 master에 등록된 서버는 보이지 않는다.
- 대상 주소가 `127.0.0.1`이고 포트가 로컬 master 포트이면 TCP 대신 위 UDS 파일로 접속한다 (`tcp.c:376`).

결론: 프로세스마다 상속한 `CUBRID`, `CUBRID_CONF_FILE`, `CUBRID_CUBRID_PORT_ID`, `CUBRID_TMP`, `CUBRID_DATABASES`가 곧 그 프로세스가 속한 인스턴스다. 서버를 띄운 셸과 `csql`을 실행한 셸의 환경이 다르면 다른 master로 가서 `SERVER_NOT_FOUND`를 받거나, 다른 인스턴스의 동명 DB에 접속한다.

## 인스턴스별로 분리해야 하는 자원

| 자원 | 설정 위치 | 기본값 | 충돌 조건과 결과 | 근거 |
|---|---|---|---|---|
| master TCP 포트 | `cubrid.conf` `cubrid_port_id` 또는 `CUBRID_CUBRID_PORT_ID` | 1523 | 같은 포트면 두 번째 master는 bind 실패(`EADDRINUSE` 재시도 후 `ERR_CSS_TCP_BIND_ABORT`). 이미 떠 있는 master에 다른 인스턴스 서버가 등록되어 `server status`에 섞여 보이고, 동명 DB는 `SERVER_ALREADY_EXISTS` | `tcp.c:651-725`, `master.c` |
| master UDS 파일 | `CUBRID_TMP` + 포트 | `/tmp/CUBRID<port>` | 포트가 다르면 파일명도 달라 충돌하지 않는다. 아래 "주의할 함정" 참고 | `tcp.c:139`, `:740-760` |
| `CUBRID_TMP` 경로 | 환경변수 | 미설정 시 `/tmp` | 절대경로가 아니거나 96자(108 − `"CUBRID65384"`+1)를 넘으면 시작 시 exit | `environment_variable.c:62-80` |
| DB 디렉터리 파일 | `CUBRID_DATABASES/databases.txt` | — | 두 인스턴스가 같은 `databases.txt`를 쓰면 이름·경로가 섞인다 | `databases_file.c:222` |
| DB 볼륨 | `databases.txt`의 경로 | — | 같은 볼륨을 두 서버가 열면 파일 잠금으로 두 번째가 거부된다(`ER_IO_MOUNT_LOCKED`로 추정, 오류 경로는 미추적) | `storage/file_io.c:541` `fileio_lock` |
| PL 서버 소켓 | `stored_procedure_uds` (기본 `true`) | `${CUBRID_TMP}/sp_<db>.sock`, `CUBRID_TMP`가 없으면 `$CUBRID/var/CUBRID_SOCK/sp_<db>.sock` | 같은 `CUBRID_TMP`를 공유하면서 같은 DB 이름을 쓰면 충돌. `$CUBRID`가 달라도 `CUBRID_TMP`가 같으면 충돌한다 | `executables/pl.cpp:424-426`, `sp/pl_comm.c:228-247` |
| PL 서버 TCP 포트 | `stored_procedure_port` (UDS를 끈 경우만 사용) | 0 | `[common]` 섹션에는 지정할 수 없고 `[@db]` 섹션에만 지정 가능. 0의 의미(임의 포트 여부)는 미확인 | `system_parameter.c:5052`, `:6814` |
| PL 정보 파일 | `$CUBRID/var/pl/pl_<db>.info` | — | `$CUBRID`를 공유할 때만 충돌 | `sp/pl_file.c:104-106` |
| broker 포트 | `cubrid_broker.conf` `BROKER_PORT` | 30000, 33000 | 같은 포트면 bind 충돌(미추적) | `conf/cubrid_broker.conf` |
| broker shared memory | `cubrid_broker.conf` `MASTER_SHM_ID`, 브로커별 `APPL_SERVER_SHM_ID` | 30001 / 30000, 33000 | SysV `shmget(key)`로 연다. `cubrid broker stop`은 `MASTER_SHM_ID` 키의 세그먼트를 열고 파괴하므로, 키가 같으면 한 인스턴스의 stop이 다른 인스턴스의 broker를 내린다 | `broker/broker_shm.c:143-153`, `broker/broker_admin_pub.c:515-574` |
| HA 포트 | `cubrid_ha.conf` `ha_port_id` | 59901 | HA를 쓸 때만 해당 | `connection/heartbeat.h:32` |
| CUBRID Manager 포트 | cm 설정 | 8001 (미확인) | manager를 띄울 때만 해당 | 미확인 |

## 주의할 함정

- **이름 기반 `pkill`**: `pkill cub_master`, `pkill cub_server`는 인스턴스와 무관하게 모두 종료한다. 요구사항에서 사용자가 수용한 위험이지만, 이 프로젝트의 도구나 지침이 이름 기반 종료를 사용해서는 안 된다. 종료는 해당 인스턴스 환경에서 `cubrid server stop <db>`, `cubrid service stop`, 또는 PID 지정으로 한다.
- **master UDS 파일 삭제**: 새 master는 TCP bind와 listen에 성공한 뒤, 같은 경로에 소켓 파일이 있으면 `unlink`하고 새로 만든다 (`tcp.c:740-760`). 같은 네트워크 네임스페이스에서는 같은 포트의 두 번째 master가 TCP bind에서 먼저 실패하므로 파일을 지우지 않는다. 그러나 **네트워크 네임스페이스가 다른 컨테이너가 호스트와 `CUBRID_TMP`(또는 `/tmp`)를 공유하고 같은 포트를 쓰면**, 컨테이너 master가 호스트 master의 소켓 파일을 지워 호스트의 로컬 접속이 끊길 수 있다. 코드에서 추론한 위험이며 실험하지 않았다. 컨테이너 쪽(`cubrid-box`)과 `CUBRID_TMP` 경로를 공유하지 않도록 경계를 정한다.
- **호스트 이름 불일치**: 서버는 `gethostname()`으로 master에 등록하고, `csql`은 `databases.txt`의 host(보통 `localhost`)로 접속한다. 둘 다 같은 머신의 같은 포트로 해석되면 문제없다.
- **다중 host 항목**: `databases.txt`의 host 열에 여러 호스트가 있으면 `csql`과 관리 도구는 `ER_NET_NO_EXPLICIT_SERVER_HOST`로 거부한다. `db@host`를 쓰거나 host를 하나만 둔다 (`boot_cl.c:556-570`).
- **환경 누락**: 위 환경변수 중 하나라도 빠진 셸에서 실행한 명령은 기본값(포트 1523, `/tmp`, 현재 디렉터리의 `databases.txt`)으로 돌아가 기본 인스턴스에 붙는다. direnv가 설정하는 환경에 이 변수들이 빠짐없이 들어가야 한다.

## 인스턴스 하나에 필요한 최소 설정

```sh
export CUBRID=/path/to/worktree-install           # 인스턴스별 설치 경로
export CUBRID_DATABASES=/path/to/instance/databases  # 인스턴스별 databases.txt
export CUBRID_TMP=/path/to/instance/tmp            # 절대경로, 96자 이하. master·PL 소켓이 분리된다
# $CUBRID/conf/cubrid.conf [common]: cubrid_port_id=<고유값>   (또는 CUBRID_CUBRID_PORT_ID)
# $CUBRID/conf/cubrid_broker.conf: 고유한 MASTER_SHM_ID, BROKER_PORT, APPL_SERVER_SHM_ID
#   broker를 띄우지 않는다면 생략 가능
# HA나 manager를 쓴다면 ha_port_id, manager 포트도 고유하게
```

포트와 `CUBRID_TMP`를 분리하면 master와 PL 소켓은 자동으로 분리된다. broker shared memory 키는 따로 배정해야 하는 자원으로 남는다. DB 이름을 worktree별로 고유하게 만들면(요구사항의 `pwddb` 예시) 환경이 섞인 셸에서 다른 인스턴스의 동명 DB에 붙는 사고도 줄어든다.

## 구현 후 확인할 것

- 두 인스턴스를 동시에 기동하고 각각 `cubrid server status`가 자기 서버만 보이는지.
- 한 인스턴스에서 `cubrid service stop` 또는 `cubrid broker stop`을 실행해도 다른 인스턴스의 master, 서버와 broker가 살아 있는지.
- `ls ${CUBRID_TMP}`에 각 인스턴스의 `CUBRID<port>`와 `sp_<db>.sock`이 따로 생기는지.
- 환경이 다른 셸에서 `csql`이 다른 인스턴스로 붙지 않고 실패하는지(DB 이름을 고유하게 한 경우).
- `ipcs -m`에서 broker shared memory 키가 인스턴스별로 다른지.
