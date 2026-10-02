# 04: 고갈된 자원 pool에서 삭제된 worktree 할당 회수

**What to build:** pool이 꽉 찼을 때 삭제된 worktree의 실제 미사용 자원만 회수하고, 그렇지 않으면 소유 정보와 부족 이유를 보고한다.

**Blocked by:** 02

**Status:** ready-for-human

Parent: [구현 명세](../spec.md)
User stories: 14, 16, 17, 18

## Acceptance criteria

- [x] 정지했지만 존재하는 worktree의 할당은 유지한다. 다른 환경이 그 숫자를 재사용하지 않는다.
- [x] 일반 배정은 순차적으로 진행하고 고갈 시에만 삭제된 등록 worktree의 회수 후보를 조사한다. 매번 source 루트를 재귀 탐색하지 않는다.
- [x] 등록된 source worktree 경로가 실제로 삭제되었고 프로세스·포트·socket·shared memory가 사용되지 않는 경우에만 할당을 회수한다.
- [x] 접근 불가, 살아 있는 owner, 점유된 포트, 남은 IPC의 소유 불확실성은 회수하지 않는 이유로 보고한다. 경로 없음만으로 살아 있는 자원을 해제하지 않는다.
- [x] 회수는 registry 기록 갱신뿐이며 프로세스 종료·DB 삭제·불명확한 IPC 제거를 하지 않는다. 다른 동시 init과 회수가 원자적 할당을 유지한다.
- [x] 회수 후에도 pool이 부족하면 실패와 할당 보고서를 내고 사용자가 구성 범위를 조정하는 방법을 안내한다. 자동 확장은 하지 않는다.
- [x] 작은 임시 pool에서 정지한 worktree, 삭제되고 미사용인 worktree, 삭제됐지만 점유된 자원, 접근 불확실성, 완전 고갈을 각각 검증한다.

## Scope and context

현재 구현이 배정하는 master·broker 포트 및 shared-memory key 전부에 동일 규칙이 적용되어야 한다. IPC 검사의 CUBRID broker 실동작 검증은 05 및 최종 검증과 연결한다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.

## Implementation evidence

- [Behavior and limitations](../../../docs/allocation-reclamation.md)
- [Recorded checks](../../../tests/evidence/ticket04/README.md): 17 discovery tests
  passed, including nine public-CLI reclamation cases in an isolated PID namespace.
- `git diff --check` passed. No schema change to allocation records; the latest
  exhaustion pass is recorded in `allocations-reclamation.json` and stderr.
- Strict uncertainty may retain stale records on hosts with inaccessible process
  evidence. No process, IPC, TMP or database deletion is implemented.
- Ready for parent review and integration; this ticket does not claim integration.
