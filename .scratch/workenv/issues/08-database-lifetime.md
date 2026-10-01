# 08: worktree 제거 시 내부 DB 정리와 외부 DB 보존

**What to build:** 정상적인 작업 종료 후 worktree를 정리할 때 내부 DB는 함께 제거하고, 외부 또는 공유 DB와 사용자 파일은 보존하는 절차를 완성한다.

**Blocked by:** 03

**Status:** ready-for-agent

Parent: [구현 명세](../spec.md)
User stories: 23, 26

## Acceptance criteria

- [ ] 새 worktree-managed DB의 data/log/LOB가 내부 수명에 포함되며 external DB 저장소는 외부에 남는 것을 실제 경로로 확인한다.
- [ ] registry와 symlink의 위치만으로 대상 저장소의 삭제 여부를 판단하지 않는다. 내부 참조가 외부 DB를 가리키면 대상 파일을 보존한다.
- [ ] 내부·외부 저장소가 혼합됐거나 소유가 불명확한 상태는 전부 삭제 가능하다고 판단하지 않고 보고한다.
- [ ] 서버를 정상 종료한 임시 worktree에서 도구가 생성한 내부 산출물만 정리하고 비강제 Git worktree 제거가 완료되는 절차를 제공한다. 관련 없는 사용자 변경과 파일을 버리거나 숨기지 않는다.
- [ ] 정리 후 외부 DB를 다른 환경에서 열어 sentinel 데이터가 유지되는지 검증한다. 이 과정에서 추가 자동 backup·move·adopt 기능을 도입하지 않는다.
- [ ] worktree 제거와 host allocation 회수의 시점을 구분한다. 삭제 직후 자동 registry 정리를 필수로 추가하지 않으며 pool 고갈 시 회수는 04의 계약을 따른다.

## Scope and context

이 티켓은 새 전역 remove 명령이나 자동 파괴 기능을 요구하지 않는다. 도구 소유 산출물의 명확한 정리 절차와 비파괴 검증으로 완료할 수 있다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.
