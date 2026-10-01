# cubrid-workenv

호스트에서 CUBRID worktree별 DB와 실행 설정을 명시적으로 초기화하는 도구.

CLI 이름: `cub-workenv` (구현 예정).

프로젝트 홈: `/home/vimkim/gh/cubrid-workenv`

[구현 명세](.scratch/workenv/spec.md)에 최종 동작 계약과 검증 기준을 정리했다. [요구사항](docs/requirements.md)은 목표와 책임 범위의 요약이며, [native DB 중복 실행 실험](experiments/native-db-exclusion/README.md)에 검증 결과와 제한을 기록했다. CLI 구현은 아직 포함하지 않는다.

컨테이너 실행 도구의 프로젝트 홈은 `/home/vimkim/gh/cubrid-box`이다. 컨테이너 내부에서는 `cubrid-workenv` 초기화를 요구하지 않는다.

새 주 에이전트는 [인계 문서](HANDOFF.md)부터 읽는다.
