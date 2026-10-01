# 06: 상태를 바꾸지 않는 환경·DB·소유자 진단

**What to build:** doctor가 준비 상태, 선택된 설치, 자원 충돌과 DB 등록 문제를 읽어 설명하고 사용자가 수동 조치를 결정할 수 있게 한다.

**Blocked by:** 02, 03, 05

**Status:** ready-for-agent

Parent: [구현 명세](../spec.md)
User stories: 9, 10, 25, 27

## Acceptance criteria

- [ ] 미초기화·불완전·준비 완료 상태와 선택된 설치/preset 불일치를 구분한다. 알려진 설정 누락·registry 이상·할당 충돌을 문제별로 설명한다.
- [ ] 추가된 정상 DB 항목과 다른 환경의 동일 이름은 오류로 취급하지 않는다. 정상 external DB 등록과 물리 경로 이상을 구분한다.
- [ ] 호스트 할당 기록과 실제 자원 점유를 함께 읽어 확인 가능한 소유 worktree·PID를 표시한다. 확인 불가한 owner는 추정하지 않고 불확실성을 알린다.
- [ ] native DB 사용 중 오류가 제공하는 PID·사용자·호스트 정보를 보존한다. PID 환경과 등록 경로로 확실히 대응될 때만 worktree 이름을 보완한다.
- [ ] native 잠금 비활성화 등 이미 알려진 보호 전제 위반은 진단에서 설명한다. 모든 CUBRID 특수 경로를 감사하거나 수정하는 기능으로 확대하지 않는다.
- [ ] 진단 전후 설정·registry·DB·할당 내용을 비교하고 테스트 프로세스의 지속 동작을 확인한다. doctor는 DB를 새로 열거나 프로세스를 종료하지 않는다.
- [ ] 문제가 없으면 성공, 실제 진단 오류가 있으면 실패 종료한다. 상태별로 구체적인 수동 복구 지침을 제공하며 자동 takeover·repair는 하지 않는다.

## Scope and context

02에서 제공한 최소 상태 진단을 확장한다. resource pool 회수는 init의 기능이며 doctor가 회수를 실행해서는 안 된다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.
