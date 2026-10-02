# 07: direnv와 빌드를 명시적 초기화 흐름으로 연결

**What to build:** 빌드·설치 후 사용자가 직접 init하고, 이후 디렉터리 진입은 준비된 환경만 빠르게 불러오는 실제 개발 흐름을 만든다.

**Blocked by:** 02

**Status:** ready-for-human

Parent: [구현 명세](../spec.md)
User stories: 1, 21, 27, 28, 29, 30

## Acceptance criteria

- [x] direnv는 완료된 환경 산출물에서 변수와 설치 바이너리 PATH만 로딩한다. DB 생성·빌드·재배정·full validation·설치 전체 해시·호스트 전체 탐색을 호출하지 않는다.
- [x] 미초기화 상태는 빌드 환경과 빌드·설치 후 init 안내를 제공한다. 부분 상태나 다른 worktree의 상속된 DB 환경을 준비된 runtime으로 노출하지 않는다.
- [x] A에서 B로 이동한 뒤 같은 DB 이름으로 접속해도 master·registry·TMP·설치가 B와 일치한다. 명시적인 preset 선택과 환경 불일치가 조용히 덮이지 않는다.
- [x] 기존 build coordinator의 자동 runtime 초기화와 공유 envrc의 전체 validation을 새 방식에 맞게 변경한다. 새 CLI와 기존 자동 초기화가 동시에 실행되는 상태로 완료 처리하지 않는다.
- [x] 기존 테스트 도구·testcase 접근성을 유지한다. container 사용에 호스트 init을 요구하거나 cubrid/csql PATH 래퍼를 도입하지 않는다.
- [x] 초기화 전 빌드, 명시적 init, 반복 디렉터리 진입, worktree 전환을 실제로 실행하고 무거운 명령 호출이 없는지 검증한다. 같은 조건의 진입 시간을 기록하되 임의 SLA를 만들지 않는다.
- [x] CUBRID source worktree agent가 발견할 수 있는 적용 지침에서 일반 cubrid/csql 사용과 초기화·진단 경계를 설명한다. 모든 테스트에 run을 강제하지 않는다.

## Scope and context

외부 도구 repository 변경은 그 repository의 별도 topic worktree와 검토 절차를 사용한다. 원본 사용자 환경의 전역 배포·일괄 migration은 하지 않으며 검증된 연동 변경과 사용자 적용 절차를 함께 제공한다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.


## Implementation evidence

Implemented in separate `impl/workenv-07` topic worktrees for cubrid-workenv and
my-cubrid; not integrated or globally deployed by this ticket.

See [ticket07 evidence](../../../docs/evidence/ticket07-environment.md) for public
CLI/artifact tests, legacy-tooling regression checks, real shared build/install,
explicit native init and A→B selection, process cleanup, execution traces, timing
samples, and limitations. Personal tooling changes include the shared `.envrc`,
coordinator, `just build` implicit DB ensure removal, container installation lock,
helper compatibility, and source-agent discovery through CUBRID.md plus the
stowed AGENTS.override.md.

The build boundary used a disposable CMake C fixture via the live shared just
recipes. A full CUBRID source build belongs to ticket09. Native runtime evidence
uses separate copied installations; it does not claim cross-version DB compatibility.
