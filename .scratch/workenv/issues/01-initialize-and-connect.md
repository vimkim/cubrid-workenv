# 01: 첫 초기화부터 testdb 접속까지

**What to build:** 설치된 CUBRID를 선택한 worktree에서 init을 실행하고, 준비된 환경을 읽어 일반 cubrid·csql 명령으로 testdb에 접속하는 첫 동작을 완성한다.

**Blocked by:** None (can start immediately)

**Status:** ready-for-human

Parent: [구현 명세](../spec.md)
User stories: 1, 2, 11, 13, 19, 21, 22, 27

## Acceptance criteria

- [x] CLI를 실행할 수 있는 설치 방법과 도움말을 제공한다. 선택한 worktree·설치·preset이 명확하며 미설치 상태는 자동 빌드 없이 준비 방법을 안내하고 실패한다.
- [x] 기본 init은 내부 저장소에 testdb를 생성한다. data/log/LOB 위치와 선택한 DB registry가 일치하고, 별도 run 래퍼 없이 서버 기동과 SQL 실행이 성공한다.
- [x] 호스트 할당 기록에 worktree와 master 포트 및 필요한 자원 배정을 기록한다. 초기 숫자 배정은 기존 할당과 실제 사용 중 자원을 피하고, 갱신은 짧은 잠금으로 직렬화한다. 고갈 시 자동 확대 없이 실패한다.
- [x] 설치·설정·registry·TMP·master port·PATH를 일관되게 제공하는 환경 산출물을 만든다. 짧고 분리된 TMP 경로를 사용하며 다른 환경을 상속하지 않는다.
- [x] 미초기화·준비 중·완료 상태를 구분하고 필수 단계가 끝난 뒤에만 완료 상태를 게시한다. 재실행이 기존 DB나 사용자 설정을 덮어쓰지 않도록 최소 보존 경계를 갖춘다.
- [x] 동일 basename의 서로 다른 worktree를 경로로 구분한다. 짧은 경로 식별자의 충돌을 검사하고 생성된 socket 경로가 길이 제한을 만족한다.
- [x] 기존 DB와 알 수 없는 설정은 소유물로 간주해 덮어쓰지 않는다. 이 티켓에서 아직 지원하지 않는 기존 DB 재사용은 명확히 거부하고 보존하며 03에서 확장한다.
- [x] 임시 설치·DB로 초기화 → 환경 로딩 → 서버 시작 → 쓰기·조회 → 해당 서버 종료를 검증한다. 포트·경로·바이너리 버전과 종료 후 잔여 프로세스 여부를 기록한다.

## Scope and context

broker·PL의 완전한 공존 보장은 05, direnv와 기존 build coordinator 연동은 07에서 완성한다. 초기 구현이 전체 격리나 자동 연동을 이미 제공한다고 안내하지 않는다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.

## Acceptance evidence

- Public entry point: `bin/cub-workenv --help`; setup and concrete defaults documented in root README.
- `python3 -m unittest discover -s tests -v`: 6 passing public CLI/artifact checks. Missing installation, preservation, active/recorded port avoidance, finite-pool exhaustion, incomplete readiness, distinct same-basename worktrees and an intentionally occupied short-digest directory are covered.
- `python3 tests/real_smoke.py --install /home/vimkim/.cub/install/develop/debug_gcc --output /tmp/cwe-ticket01-green2`: passed using a copied disposable installation. [Recorded evidence](../../../tests/evidence/ticket01/results.json) includes selected preset, paths, master port 41000, commands and zero return codes. [Version](../../../tests/evidence/ticket01/version.txt): 11.5.0.2602-a0026f9. [SQL](../../../tests/evidence/ticket01/sql.txt) proves committed value 42; [registry](../../../tests/evidence/ticket01/databases.txt) proves matching data/log/LOB paths. Cleanup found no remaining exact-prefix processes and removed disposable runtime storage.
- TDD: missing-install test first failed because the CLI did not exist, then passed; real flow first failed because initialization was absent, then passed; local existing-registry preservation first failed (init incorrectly succeeded), then passed after the explicit refusal. Supplemental artifact regressions cover the initialized behavior.
- `git diff --check`: passed. Stored SQL transcript trims trailing spaces; SQL values and native messages are unchanged.

## Interface handoff and limits

- Python stdlib modules: `cli.py` command arguments, `state.py` lifecycle, `allocation.py` short host transactions, `runtime.py` settings/environment/native DB boundary. State schema 1 records normalized worktree/install, selected preset, state_home and allocation. Host records are a JSON list.
- `init --worktree --install --preset --state-home --port-start --port-end`; generated bash `.cub-workenv/env.sh` is the current loading boundary. Installation and preset are explicit, and preset provenance is not inferred from CMake.
- 02 extends repeated-state validation, failure handling and doctor; 03 adds environment-only initialization/create-db and compatible reuse; 04 extends allocation reclamation; 05 extends broker/shared-memory/PL settings and coexistence; 07 handles the build/direnv flow and PATH composition. Current native test is server/client only; stored procedures are disabled.
- The first real harness attempt timed out because daemon descendants inherited a captured stdout pipe; native-command logging now uses files. This was a harness issue, and the subsequent complete run passed. Full inherited environment is never persisted; evidence includes only selected connection variables and execution paths.
- This ticket is verified and committed for parent review, not declared integrated. Integration status remains the parent agent's responsibility.
