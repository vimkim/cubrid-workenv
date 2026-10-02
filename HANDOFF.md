# cubrid-workenv 인계

## 시작 순서

1. `/home/vimkim/my-cubrid/CUBRID.md`와 적용되는 `AGENTS.md`를 읽고 branch, worktree, 상태를 확인한다.
2. [구현 명세](.scratch/workenv/spec.md)와 [용어집](GLOSSARY.md)을 읽는다. 명세는 계약이며 과거 인터뷰 제안보다 우선한다.
3. 현재 구현·통합 상태는 [구현 기록](.scratch/workenv/implementation.md), 명세별 증거는 [최종 검증](docs/evidence/ticket09-workflow.md)을 따른다. 설계 ledger 249와 구현 ledger 256을 구분한다.
4. 실행·복구·삭제 작업에는 [사용자 흐름](docs/workflow.md), agent 실행에는 [실행 지침](docs/agents/test-execution.md)을 사용한다. 자원 배정 변경 전에는 [소스 조사](docs/handoff-instance-isolation.md)를 읽되 runtime 증거와 구분한다.

## 현재 동작

CLI `cub-workenv`는 명시적 `init`, `init --no-db`, `create-db`, 가벼운 `env`, 읽기 전용 `doctor`를 제공한다. 준비된 환경에서 일반 `cubrid`·`csql`을 직접 실행한다. 반복 init은 준비된 상태를 변경하지 않는다. 실패한 init은 단계·할당·DB 단서를 남기므로 범위를 바꾸어 재실행하는 것만으로 복구되지 않는다.

숫자 자원은 협력하는 host allocation namespace에서 배정한다. 정지한 worktree의 할당도 유지하며, 고갈 시 삭제된 worktree의 미사용 자원만 회수한다. 외부 도구의 사후 침범 방지나 sandbox는 제공하지 않는다. 공유 물리 DB의 검증된 정상 경로는 native 잠금을 사용하며 별도 run 강제·lease를 추가하지 않는다. 버전 호환성과 비정상 종료는 별도 판단이 필요하다.

## 두 저장소의 적용 경계

개인 tooling 후보는 `/home/vimkim/my-cubrid-workenv-07`, `impl/workenv-07`, `74a13cf2508e1da8c528b0c0f1723566ab8a853d`이다. runtime 검증은 동일 코드의 직전 `aea80789165951be4602d042476c88bd5105e049`에서 수행했고 이후 변경은 문서 정정이다. 후보의 공유 envrc/build coordinator는 자동 init·진입 full validation을 제거한다. 후보를 `MY_CUBRID`와 `CUB_WORKENV_CLI`로 선택한 별도 fixture에서 실제 CUBRID source build를 검증했다.

기존 source worktree가 tooling main의 `.envrc`·justfile을 직접 symlink하므로 그 저장소 적용은 기존 환경에 영향을 줄 수 있다. CLI 저장소 merge가 tooling의 전역 적용·restow·기존 DB 이관을 암묵적으로 승인하지 않는다. 최종 리뷰에서 두 저장소 diff와 적용 결정을 분리한다. 기존 develop의 사용자 변경과 설치는 보존한다.

container는 별도 `cubrid-box` 책임이다. host init을 container의 전제조건으로 추가하지 않는다. HA·Manager·자동 복구·DB 변환은 범위 밖이다.

## 다음 작업

부모 orchestration agent가 최종 Standards/Spec 리뷰, 지적사항 수정, 실제 통합 기록을 관리한다. 완료된 topic commit을 검토한 뒤 사용자 확인으로 main에 rebase/fast-forward한다. push와 배포는 별도 요청이 필요하다. 소스 실험 cleanup 상태는 최종 검증 문서를 따른다.
