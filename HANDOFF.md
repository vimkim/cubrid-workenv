# cubrid-workenv 인계

## 시작 순서

1. `/home/vimkim/my-cubrid/CUBRID.md`와 적용되는 `AGENTS.md`를 읽고 현재 branch, worktree, working-tree 상태를 확인한다. 기존 사용자 변경을 보존한다.
2. [구현 명세](.scratch/workenv/spec.md)를 현재 동작 계약으로 읽는다. [용어집](GLOSSARY.md)과 [요구사항](docs/requirements.md)은 용어와 배경을 제공한다. 시간순 [인터뷰](.scratch/workenv/design-interview.md)에 남아 있는 과거 제안보다 최종 명세를 우선한다.
3. 포트·UDS·shared memory 배정 전에 [인스턴스 격리 소스 인계](docs/handoff-instance-isolation.md)를 읽는다. 공유 물리 DB 관련 결정에는 [native 실험 결과](experiments/native-db-exclusion/README.md)를 사용하되 검증 범위를 넓혀 주장하지 않는다.
4. 구현을 요청받으면 local Markdown tracker에 명세로부터 작은 구현 티켓을 만들거나 주어진 티켓을 수행한다. tracker 규칙은 [issue-tracker](docs/agents/issue-tracker.md)에 있다. 명세 작성 자체는 CLI 구현 요청이 아니다.

## 현재 완료된 것

프로젝트 이름은 `cubrid-workenv`, CLI 이름은 `cub-workenv`다. 초기화·진단·환경 로딩·자원 배정·DB 수명에 대한 사용자 합의를 명세로 정리했다. CLI는 아직 구현하지 않았다.

설치된 Linux debug 빌드 `11.5.0.2602-a0026f9`에서 동일 물리 DB의 두 번째 서버와 `csql -S`가 native 잠금으로 거부되는 것을 검증했다. 기존 서버의 쓰기·조회와 정상 종료 뒤 순차 재사용도 확인했다. 사용자·호스트·PID·DB 경로가 native 오류에 포함된다. 다른 버전, 비정상 종료, 특수 유틸리티 경로는 이 실험의 증명 범위가 아니다.

일반 `cubrid`·`csql` 사용에는 `cub-workenv run`을 강제하지 않는다. workenv는 명시적 초기화와 설정 충돌 회피에 집중한다. 전체 도구의 다중 인스턴스 격리나 빠른 환경 로딩이 구현·검증 완료된 것은 아니다.

## 기존 도구와 연동

`/home/vimkim/my-cubrid`의 기존 runtime 도구, build coordinator와 공유 envrc를 조사했다. 기존 흐름에는 설치 후 자동 runtime 초기화와 진입 시 전체 validation이 있으므로 새 흐름과의 연동 작업이 필요하다. 기존 설정을 일괄 덮어쓰거나 기존 DB를 자동 이관하지 않는다.

`/home/vimkim/gh/cb/my-cubrid-runtime-testdir`는 이전 조사 시작점이다. 이름만으로 초기화된 실험 환경이라고 가정하지 않고 현재 파일을 확인한다. direnv 지연의 이전 개선은 별도 도구의 측정 결과이며 새 CLI 성능 검증이 아니다.

컨테이너는 별도 `/home/vimkim/gh/cubrid-box` 프로젝트의 책임이다. 호스트 초기화를 container의 전제조건으로 추가하거나 상대 프로젝트 파일을 직접 변경하지 않는다.

## 작업 상태와 검토

관련 work-tracker 항목은 249다. 현재 상태와 다음 작업은 ledger 및 Git 상태로 확인한다. 저장소 변경은 sibling topic worktree에서 수행하고 의미 있는 변경을 검증·커밋한다. 로컬 rebase와 fast-forward merge는 사용자 확인 후 수행하며 push는 별도 요청이 필요하다.

구현 티켓은 [티켓 목록](.scratch/workenv/tickets.md)에 있으며, 다음 시작점은 선행 조건이 없는 01번이다. 일반 소스 worktree의 agent guidance 연결, 기존 도구 연동, 수동 복구 절차와 최종 사용자 흐름은 실제 구현에서 완료해야 한다.
