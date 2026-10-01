# 03: 환경만 초기화하고 기존·외부 DB를 보존하며 사용

**What to build:** init --no-db 이후 create-db로 DB를 준비하고, 기존 testdb나 외부 DB는 안전하게 재사용하며 관련 없는 registry 항목을 보존한다.

**Blocked by:** 01

**Status:** ready-for-agent

Parent: [구현 명세](../spec.md)
User stories: 3, 4, 5, 6, 20, 23, 24, 25

## Acceptance criteria

- [ ] init --no-db는 DB 생성·삭제 없이 완료된 환경을 제공한다. 이후 create-db가 명시한 이름과 저장 위치에 DB를 생성하고 일반 csql로 사용 가능하다.
- [ ] 기존 testdb의 등록·물리 위치·설정이 호환되면 init은 내용을 보존해 재사용한다. 호환되지 않거나 안전한 재사용을 확인할 수 없으면 실패하며 환경만 준비됐다고 성공 처리하지 않는다.
- [ ] create-db는 동명 기존 DB를 덮어쓰거나 재생성하지 않는다. 다른 DB registry 항목과 사용자 설정을 그대로 보존한다.
- [ ] 서로 다른 환경의 동명 DB를 허용한다. 명시적인 external DB 재사용과 잘못된 master·broker 설정 공유를 구분한다.
- [ ] 기존 등록 검사를 위해 실행 중인 DB를 standalone으로 열어보지 않는다. 별도 adopt나 포괄적인 legacy migration을 요구하지 않는다.
- [ ] 기존 DB의 sentinel 데이터를 보존하는지, 추가 registry 항목이 유지되는지, 잘못된 재사용이 비파괴적으로 실패하는지 확인한다.
- [ ] 도구로 준비한 두 환경에서 동일 외부 물리 DB를 순차 사용한다. 실행 중에는 두 번째 서버와 standalone이 native 오류로 거부되고 첫 서버가 정상인지를 검증한다. 일반 client 접속은 허용한다.
- [ ] native 오류의 사용자·호스트·PID·DB 위치를 숨기지 않으며 추가 flock·lease·run 강제를 도입하지 않는다. 버전 호환성이나 물리적 read-only를 보장하지 않는다.

## Scope and context

외부 DB의 정리·worktree 제거 전체 절차는 08에서 검증한다. 기존 native 잠금 실험을 선행 근거로 사용하되 실제 새 환경 생성 경로도 확인한다.

[용어집](../../../GLOSSARY.md)과 [native 중복 실행 실험](../../../experiments/native-db-exclusion/README.md)의 용어·검증 제한을 따른다. 공유 DB의 정상 경로 중복 열기는 CUBRID에 맡기고, init의 자원 할당 직렬화와 DB runtime 잠금을 혼동하지 않는다.
