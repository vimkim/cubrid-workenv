# cubrid-workenv 구현 명세

Status: ready-for-agent
Work item: 249
Scope: 호스트 worktree 환경 초기화·자원 배정·DB 준비·환경 로딩·진단

## Problem Statement

개발자는 여러 CUBRID source worktree에서 빌드와 DB 테스트를 수행한다. 서로 다른 worktree의 master·broker·PL 서버가 같은 포트, socket 경로 또는 shared-memory key를 사용하면 잘못된 DB에 접속하거나 다른 인스턴스를 종료할 수 있다. 디렉터리 진입 때 DB 생성과 전체 runtime 검증을 반복하는 방식은 작업을 지연시키며 준비와 실행의 경계를 흐린다.

한편 큰 DB는 생성·적재 비용 때문에 서로 다른 worktree에서 순차적으로 재사용할 필요가 있다. DB 이름이 같다는 이유만으로 충돌이라고 판단하거나, 모든 실행을 별도 래퍼로 강제할 필요는 없다. 저장 위치에 따른 데이터 수명과 실제로 충돌하는 자원을 구분해야 한다.

## Solution

사용자가 빌드·설치를 완료한 뒤 명시적으로 `cub-workenv init`을 실행한다. 명령은 해당 worktree의 실행 설정과 자원을 준비하고 기본 `testdb`를 생성하거나 호환되는 기존 DB를 재사용한다. `--no-db`이면 환경만 준비하며, DB는 이후 `create-db`로 생성할 수 있다.

이후 direnv는 준비된 환경변수와 설치 바이너리 PATH만 불러온다. 사용자는 일반 `cubrid`·`csql`을 그대로 실행한다. `doctor`는 상태를 바꾸지 않고 문제와 조치 방법을 설명한다.

유한한 숫자 자원은 호스트의 알려진 worktree 할당 기록과 실제 사용 현황을 고려해 배정한다. 임시 디렉터리와 socket 경로는 worktree별로 분리한다. 같은 물리 DB의 중복 열기는 검증된 정상 경로에서 CUBRID의 native 잠금에 맡긴다. workenv는 외부 도구가 나중에 자원을 침범하는 것을 지속적으로 차단하는 서비스가 아니다.

## User Stories

1. As a developer, I want explicit initialization after build and installation, so that entering a directory does not unexpectedly prepare or run a database.
2. As a developer, I want initialization to prepare a default testdb, so that I can run a small experiment immediately.
3. As a developer, I want an environment-only initialization option, so that I can defer database creation.
4. As a developer, I want a separate create-db command, so that I can add databases after initialization.
5. As a developer, I want compatible existing testdb storage preserved, so that initialization does not destroy my data.
6. As a developer, I want initialization to fail clearly when an existing database cannot safely be reused, so that partial readiness is not presented as success.
7. As a developer, I want repeated initialization to warn without changing an initialized environment, so that my settings and databases remain stable.
8. As a developer, I want interrupted initialization distinguished from completed initialization, so that I know when diagnosis and manual recovery are required.
9. As a developer, I want doctor to inspect without repairing, so that I remain in control of changes.
10. As a developer, I want diagnosis to report the affected resource and known owner, so that I can identify conflicts without guessing.
11. As a developer, I want distinct master and broker ports, so that commands address the intended work environment.
12. As a developer, I want distinct broker shared-memory keys, so that stopping my broker does not stop another worktree's broker.
13. As a developer, I want separate temporary and socket paths, so that master and PL sockets do not collide.
14. As a developer, I want stopped worktrees' assignments retained, so that restarting them does not introduce a conflict.
15. As a developer, I want concurrent initializations to allocate distinct resources, so that two cooperating users of the tool do not claim the same slot.
16. As a developer, I want unused assignments of deleted worktrees reclaimed when the pool is exhausted, so that short-lived worktrees do not permanently consume the pool.
17. As a developer, I want uncertain or live allocations skipped during reclamation, so that reclamation does not disturb running processes.
18. As a developer, I want clear failure when no safe pool slot remains, so that I can deliberately adjust the pool.
19. As a developer, I want database names reused across environments, so that familiar names such as testdb remain convenient.
20. As a developer, I want additional database registry entries preserved, so that manually added databases are not treated as corruption.
21. As a developer, I want ordinary cubrid and csql commands to use the prepared environment directly, so that routine work does not require a wrapper.
22. As a developer, I want ordinary client connections to a running database allowed, so that normal multi-client usage continues to work.
23. As a developer, I want sequential reuse of an external physical database, so that expensive loading need not be repeated for every worktree.
24. As a developer, I want concurrent independent opening of that shared database rejected, so that the existing database user is protected.
25. As a developer, I want native busy-database errors and available owner information preserved, so that a second opener can understand the failure.
26. As a developer, I want worktree-managed databases removed with the worktree and external databases preserved, so that data lifetime follows its location.
27. As a developer, I want one selected build preset per work environment, so that the active installation is explicit.
28. As a developer, I want fast environment loading without full validation, so that directory changes remain inexpensive.
29. As an agent, I want execution guidance to distinguish initialization from runtime protection, so that I do not impose unnecessary run wrappers or overstate isolation.
30. As a developer, I want host and container workflows to remain independent, so that cubrid-box does not depend on host initialization.

## Implementation Decisions

### 도구의 책임과 범위

- 하나의 work environment는 하나의 source worktree와 하나의 선택된 설치·preset에 대응한다. worktree 이동·이름 변경 지원은 제외한다.
- 구현 모듈은 CLI, 초기화 상태와 자원 할당, CUBRID 설정·DB 유틸리티 연동, 환경 로딩, 진단으로 나눈다. 테스트를 위해 내부 함수 구조를 고정하지 않는다.
- 유일한 일반 실행 경로를 workenv가 소유하지 않는다. 준비된 환경에서는 기존 CUBRID 명령을 직접 사용한다.
- 자원 충돌 회피는 초기화 시점의 검사와 배정이다. 외부 도구의 후속 침범을 막는 상시 daemon, per-command 검증, 전역 sandbox를 만들지 않는다.
- 일반 서버·broker·PL 설정을 다룬다. HA와 CUBRID Manager는 첫 버전에 포함하지 않는다.

### CLI의 외부 계약

| 명령 | 성공 동작 | 실패·반복 동작 |
| --- | --- | --- |
| `init` | 설치를 확인하고 환경과 기본 testdb를 준비 | 기존 DB를 안전하게 재사용할 수 없으면 실패; 데이터 보존 |
| `init --no-db` | DB 생성 없이 환경과 자원 설정만 준비 | 기존 DB나 registry 항목을 삭제하지 않음 |
| `create-db` | 초기화한 환경에 요청한 DB 생성 | 동명 기존 DB를 덮어쓰거나 재생성하지 않음 |
| `doctor` | 환경·할당·설치·DB 등록 상태를 읽고 결과 설명 | 문제를 보고하되 설정·DB·프로세스·할당을 변경하지 않음 |

- 초기화된 worktree에서 `init`을 다시 실행하면 이미 초기화되었다는 경고를 표시한다. 다른 옵션을 주더라도 환경을 재설정하거나 뒤늦게 DB를 만들지 않는다.
- 반복 호출의 가벼운 상태 확인에서 이상이 드러나면 `doctor`를 안내한다. 이를 디렉터리 진입 시 전체 검증으로 확장하지 않는다.
- 처음부터 설치가 없으면 DB 생성 전에 실패하고 빌드·설치를 안내한다. workenv가 자동으로 빌드하지 않는다.
- `create-db`의 이름·저장 위치 인자는 명시적으로 제공할 수 있어야 한다. 기본 환경 준비 후 추가 DB 생성에 기존 명령의 동작을 재사용하며, 구체적 옵션 철자는 CLI 구현 단계의 일관성 있는 선택으로 남긴다.
- 성공과 이미 준비된 정상 환경의 무변경 반복 호출은 성공 종료한다. 준비 실패·불완전 상태·실제 진단 오류는 실패 종료한다. 세부 오류 번호나 JSON 출력은 필수 요구사항이 아니다.
- `run`과 `adopt`는 첫 버전 필수 명령에 포함하지 않는다. 기존 DB 재사용이 가능한 경우는 초기화에서 보존하며, 별도 이관이 필요한 상태는 실패와 설명으로 처리한다.

### 초기화 상태와 보존

- 미초기화, 준비 중 또는 불완전, 준비 완료를 구분한다. 준비 완료 표시는 필수 단계가 모두 끝난 뒤에만 게시한다.
- 준비 중 프로세스가 종료되더라도 이미 기록한 할당과 작업 단서를 보존한다. 다음 `init`은 불완전 상태를 보고하고 `doctor`를 안내한다. 자동 rollback이나 무조건 재시도는 하지 않는다.
- 두 초기화가 같은 worktree에 동시에 쓰지 않도록 직렬화한다. 전체 시스템의 빌드나 장시간 테스트를 이 잠금으로 직렬화하지 않는다.
- 사용자 설정, 기존 DB 파일, 추가 DB registry 항목을 보존한다. 소유가 불명확한 파일을 초기화 산출물로 간주해 덮어쓰지 않는다.
- 설정 변경이나 preset 전환을 반복 `init`에 숨기지 않는다. 선택된 설치와 맞지 않으면 조치가 필요한 상태로 설명한다. 자동 preset 전환과 DB 형식 변환은 제공하지 않는다.
- 생성한 환경 설정은 완료 상태와 연결되어야 하며, 부분적으로 생성된 환경을 완성된 runtime으로 노출하지 않는다.

### 숫자 자원 배정과 회수

- master·broker TCP 포트와 broker의 SysV shared-memory key는 유한 자원으로 관리한다. shared memory를 파일 경로로 취급하지 않는다.
- host-local 할당 기록에 정규화된 worktree 위치와 배정 자원을 저장한다. 현재 실행 중이지 않은 알려진 초기화 worktree의 할당도 예약된 것으로 취급한다.
- 구성된 pool 안에서 순차 배정한다. 등록된 할당과 실제 사용 중인 자원을 모두 피한다. pool의 정확한 기본 범위·크기와 저장 형식은 구현 단계에서 문서화하는 구성값이며 외부 API 불변식이 아니다.
- 할당 기록의 확인·선점·게시에는 짧은 상호 배제와 원자적 갱신을 사용한다. 서로 다른 초기화가 같은 자원을 골라 둘 다 성공해서는 안 된다.
- 기록은 협력하는 workenv 초기화를 조율하는 수단이다. 다른 도구가 free-port 검사와 bind 사이에 끼어드는 것까지 OS 예약으로 방지한다고 주장하지 않는다.
- pool이 고갈되면 등록된 worktree 위치를 확인해 삭제된 worktree의 할당을 회수 후보로 삼는다. 사용자의 source worktree 루트 아래에 등록된 경로를 검사하며, 매번 모든 디렉터리를 재귀 탐색하지 않는다.
- 경로가 없다는 사실만으로 회수하지 않는다. 프로세스·포트·socket·shared memory가 여전히 사용 중이거나 확인이 불확실하면 건너뛴다. 접근 불가를 삭제로 오인하지 않는다.
- 회수는 사용하지 않는 할당 기록의 해제다. 프로세스 종료, DB 삭제, 소유가 불명확한 IPC 제거가 아니다.
- 회수 후에도 안전한 할당이 없으면 pool 상태와 소유 정보를 보고하고 명시적 범위 조정을 안내한다. 자동으로 pool을 확장하지 않는다.

### 경로 자원과 연결 설정

- TMP와 Unix socket은 짧은 worktree별 디렉터리로 분리한다. 개별 socket 파일마다 별도 할당 기록을 만들지 않는다.
- 정규화된 worktree 경로의 짧은 digest를 식별자로 사용할 수 있지만, 7자리 같은 짧은 값만으로 유일성을 보장하지 않는다. 충돌을 확인하고 길이 확장 등으로 구분한 뒤 결과를 안정적으로 보존한다.
- master·PL socket 경로 길이 제한을 만족하도록 짧은 기반 경로를 선택한다. 데이터 저장 위치와 TMP 위치를 동일하게 만들 필요는 없다.
- 환경에는 해당 설치, 설정 파일, DB registry, master port, TMP 및 필요한 라이브러리·실행 경로가 일관되게 포함되어야 한다.
- 호스트와 container가 같은 TMP/socket 경로를 공유하는 구성은 만들지 않는다. container 내부 초기화는 별도 도구의 책임이다.
- 서로 다른 worktree가 같은 basename을 갖더라도 실제 경로와 할당을 혼동하지 않는다.

### DB 이름, 재사용과 수명

- DB 이름은 한 환경의 registry 안에서 식별되며 다른 환경과 중복될 수 있다. 이름만 같다는 이유로 충돌을 보고하지 않는다.
- 초기 기본 DB는 testdb다. 기존 등록이 있다면 물리 경로와 설정을 확인해 호환될 때 보존·재사용한다. 생성이나 load를 반복하지 않는다.
- 기존 등록을 읽는 것과 물리 DB를 다시 여는 것을 구분한다. 초기화 검사가 이미 실행 중인 DB를 standalone으로 열어보는 방식에 의존해서는 안 된다.
- 같은 물리 DB를 외부 DB로 명시적으로 사용하는 것은 허용한다. 다만 다른 인스턴스의 master·broker 자원이나 설치 설정을 공유하도록 재작성하지 않는다.
- worktree-managed DB는 worktree 내부에 data/log/LOB 등 삭제 대상 저장소가 모이도록 준비한다. worktree 제거 시 함께 제거되는 위치 관계를 사용한다.
- external DB는 worktree 외부에 두며 해당 worktree 제거와 무관하게 보존한다. registry 항목이나 symlink가 내부에 있다는 이유로 외부 대상까지 재귀 삭제하지 않는다.
- 사용자가 공유 목적으로 옮기거나 백업한 DB를 도구가 자동으로 다시 이동·백업하지 않는다. 혼합된 내부·외부 저장소를 단순히 전부 삭제 가능한 DB로 분류하지 않는다.
- Git worktree 정리 과정은 기존 사용자 지침의 비강제 제거·사용자 변경 보존 원칙을 유지한다. 생성 파일 때문에 제거가 막히면 정확한 소유 산출물 정리와 외부 DB 보존을 확인하는 절차를 제공하며, 포괄적인 강제 삭제로 우회하지 않는다.

### 물리 DB의 중복 열기

- 검증한 정상 경로에서는 CUBRID native active-log 잠금에 맡긴다. 별도의 DB 소유 lease나 `flock`을 기본 요구사항으로 추가하지 않는다.
- 기존 서버를 사용하는 일반 client 연결은 허용한다. 별도 서버 또는 standalone으로 같은 물리 DB를 다시 여는 경우와 구분한다.
- 다른 opener가 있는 경우 오류를 숨기거나 자동으로 그 프로세스를 종료하지 않는다. native 오류가 제공하는 DB 위치·사용자·호스트·PID를 전달한다.
- worktree 이름까지 알려줄 수 있으면 유용하지만, 이를 위해 모든 실행에 marker를 쓰도록 강제하지 않는다. `doctor`는 확인 가능한 PID 환경과 할당 기록으로 소유 worktree를 보완하고 확인 불가하면 추정하지 않는다.
- 버전 간 파일 형식 호환성과 read-only 실행은 보장하지 않는다. 비정상 종료 후에는 진단과 수동 복구를 허용한다.
- native 잠금 비활성화처럼 보호 전제를 깨는 알려진 설정은 진단에서 설명한다. 첫 버전이 CUBRID 엔진의 모든 비정상 잠금 경로를 수정하거나 증명할 책임은 없다.

### direnv와 기존 도구 연동

- direnv는 이미 준비된 환경변수·PATH만 불러온다. DB 생성, 빌드, resource 재배정, 호스트 전체 탐색, 설치 전체 해시 계산, full runtime validation을 진입 경로에 넣지 않는다.
- 미초기화 상태에서는 빌드에 필요한 환경을 제공하고, 빌드·설치 뒤 초기화를 실행하라는 안내를 한다. 다른 worktree에서 상속된 DB 연결 환경을 이 worktree의 환경으로 사용하지 않는다.
- 인접 worktree 간 이동 후 같은 DB 이름으로 연결하더라도 선택된 master·registry·TMP가 일치해야 한다.
- 기존 빌드 coordinator의 자동 runtime 초기화와 진입 시 전체 validation은 새 명시적 초기화 흐름에 맞춰 연동을 변경해야 한다. 단지 새 CLI를 추가하고 구 동작을 계속 호출하는 것으로 완료 처리하지 않는다.
- 다른 repository의 연동 변경은 해당 repository의 topic worktree에서 수행하고, 기존 사용자 환경을 일괄 이관하거나 전역 교체하지 않는다.
- 필요한 테스트 도구·testcase 접근은 기존 경로를 유지한다. 테스트 suite의 실행기를 workenv가 새로 통일하지 않는다.
- AI 지침은 준비된 환경에서 기존 명령을 사용하도록 설명한다. 모든 테스트에 `run`을 강제하지 않으며, 초기화가 임의의 테스트 script를 sandbox로 만든다고 주장하지 않는다.

## Testing Decisions

검증 경계는 공개 CLI와 생성 산출물, 그리고 실제 CUBRID 명령에서 관찰되는 동작이다. 내부 함수 호출 순서나 자료구조를 그대로 복사한 테스트는 만들지 않는다. 구현 전 선행 근거는 기존 native 중복 실행 실험이었다. 현재 구현·검증 상태와 새 source build 근거는 [최종 검증](../../docs/evidence/ticket09-workflow.md)을 따른다.

| 검증 영역 | 관찰할 완료 조건 |
| --- | --- |
| 첫 초기화 | 설치 확인 후 testdb 생성·접속, 설정과 할당 일치 |
| 환경만 초기화 | DB 생성·삭제 없음, 이후 create-db로 DB 준비 가능 |
| 기존 testdb | 호환 DB 내용 보존; 안전한 재사용 불가 시 실패 |
| 재초기화 | 경고와 무변경; 설정·DB·할당 내용이 바뀌지 않음 |
| 중단된 초기화 | 성공 표시 없음; 다음 호출은 불완전 상태와 doctor 안내 |
| doctor | 관련 문제와 조치 제시; 설정·DB·할당·프로세스 변경 없음 |
| 동시 초기화 | 같은 worktree 중복 쓰기 방지, 서로 다른 worktree 할당 중복 없음 |
| 숫자 자원 | 실행 중 자원 및 정지한 알려진 worktree의 할당 회피 |
| pool 고갈 | 삭제되고 미사용인 기록만 회수; 부족하면 보고 후 실패 |
| 회수 제한 | 살아 있는 프로세스·IPC 또는 접근 불확실성이 있으면 회수하지 않음 |
| 짧은 경로 식별자 | 의도적으로 만든 digest 충돌을 구분, socket 길이 제한 준수 |
| 다중 인스턴스 | 각 master가 자기 서버만 표시하고 A의 서버·broker stop 후 B는 정상 |
| PL socket | 같은 DB 이름을 쓰는 별도 DB의 PL socket 경로가 분리됨 |
| DB 수명 | 내부 DB 산출물 정리와 외부 data/log/LOB 보존을 확인 |
| 환경 로딩 | 반복 진입에 초기화·DB 생성·full validation 없음; A→B 전환 시 연결 대상 일치 |
| 공유 물리 DB | 두 번째 서버 및 standalone 거부, 원래 서버 건강, 종료 후 순차 재사용 |
| 진단 정보 | native 소유 PID를 보존하고 worktree를 확실히 식별할 수 있는 경우만 표시 |
| 기존 연동 | 빌드 후 자동 init·디렉터리 진입 full validation이 남지 않음 |
| Agent 지침 | 일반 명령 허용, run 강제 없음, 기존 container 경계 유지 |

자원 고갈·동시 초기화·부분 실패는 작은 임시 pool과 실패 유도 가능한 외부 의존 경계로 재현한다. 필요한 경우 CUBRID 유틸리티 호출을 대체할 수 있지만, 실제 DB 생성·접속·broker 정지·native 잠금 증거를 모의 호출로 대체하지 않는다.

실험용 설치와 DB만 사용하고, 프로세스는 고유한 환경과 PID로 식별해 정리한다. broad pkill은 사용하지 않는다. 재현 스크립트·버전·설정·명령·반환 코드·판정 근거를 남기고, 테스트 종료 후 기존 사용자 인스턴스에 영향을 주지 않았는지 확인한다.

환경 로딩의 절대 지연 목표는 합의되지 않았다. 같은 조건에서 개선 전후 시간을 기록하고, 무거운 작업이 진입 경로에서 빠졌는지를 확인한다. 임의의 수치 SLA를 완료 기준으로 추가하지 않는다.

## Out of Scope

- cubrid-box 구현이나 container 운영을 호스트 초기화에 종속시키는 변경.
- HA와 CUBRID Manager 설정·운영.
- worktree 이동·이름 변경 지원.
- 외부 도구의 자원 침범 방지, 상시 감시, host-wide 프로세스 통제.
- 모든 테스트에 run을 강제하거나 PATH로 cubrid/csql을 대체하는 방식.
- 추가 DB lease/잠금을 검증 근거 없이 도입하는 작업.
- 자동 repair, 자동 takeover, 손상 DB 복구, 포괄적인 기존 환경 migration/adopt.
- DB 파일 형식 변환, 버전 간 호환성 보증, 물리적 read-only 보증.
- 사용자 DB의 자동 백업·이동 및 외부 DB 자동 삭제.
- GUI, 외부 서비스 배포, 원격 저장소 push.
- 구현 티켓 생성과 실제 CLI 구현은 이 문서 작성 작업에 포함하지 않는다.

## Further Notes

### 근거와 우선순위

이 명세는 인터뷰의 최종 합의와 native 실험을 종합한다. 시간순 인터뷰에 남아 있는 과거 run 강제·전역 고유 DB 이름 제안보다 이 명세의 최종 범위를 우선한다.

- [용어집](../../GLOSSARY.md)
- [목표와 기존 요구사항](../../docs/requirements.md)
- [설계 인터뷰](design-interview.md)
- [인스턴스 격리 소스 인계](../../docs/handoff-instance-isolation.md)
- [native 중복 실행 실험과 제한](../../experiments/native-db-exclusion/README.md)
- [Agent 실행 지침](../../docs/agents/test-execution.md)

### 검증된 사실과 미검증 범위

설치된 Linux debug 빌드 11.5.0.2602-a0026f9 두 복사본에서 두 번째 서버와 csql -S가 거부됐고, 기존 서버는 계속 쓰기·조회했으며 종료 후 다른 환경에서 재사용했다. 오류는 사용자·호스트·PID·물리 DB 위치를 제공했다.

이 결과가 서로 다른 버전, 동시에 시작하는 최초 opener 경쟁, 강제 종료, stale lock metadata, 잠금 비활성화, 네트워크 파일시스템 또는 모든 유틸리티 경로를 증명하지는 않는다. 특수 경로가 실제 지원 요구사항이 될 때 별도 검증과 판단을 한다.

### 구현자가 구체화할 가역적 세부사항

정확한 pool 기본값, metadata 저장 형식, 짧은 식별자 길이, create-db 옵션 철자, DB 초기 크기·locale 기본값은 기존 도구와 호환성을 확인하여 구현 시 문서화한다. 이 선택으로 위 보존·수명·명시적 초기화·비간섭 계약을 바꾸지 않는다. 호환되지 않는 기존 설정을 조용히 덮어쓰거나, 미검증 보호를 완료된 것으로 표시하는 선택은 허용하지 않는다.

### 다음 단계

현재 티켓별 완료·통합과 후속 리뷰 상태는 [구현 기록](implementation.md)을 따른다. 이 명세의 동작 계약과 구현 당시 실제 검증 범위를 구분한다.
