# 같은 물리 DB의 native 중복 실행 방지 실험

## 결과

2026-10-01, 설치된 CUBRID `11.5.0.2602-a0026f9` Linux debug 빌드에서 **두 번째 서버 기동과 서버 실행 중 `csql -S`가 모두 거부됐다**. 추가 `flock`, workenv 래퍼, PATH 명령 대체 없이 실행했다. 첫 번째 서버는 두 번의 거부 이후에도 쓰기·commit·조회가 성공했으며, 종료 후 두 번째 환경에서 서버와 standalone 접근이 순차적으로 성공했다.

| 시나리오 | 반환 코드 | 확인 결과 |
| --- | --- | --- |
| A 서버가 실행 중일 때 B 서버 기동 | 1 | active log가 기존 PID에서 사용 중이라는 오류 |
| A 서버가 실행 중일 때 B의 `csql -S` | 1 | 같은 active-log 사용 중 오류 |
| 각 거부 직후 A에서 INSERT / COMMIT / SELECT | 0 | 행 수가 1 → 2 → 3으로 증가 |
| A 정상 종료 후 B 서버 기동·조회 | 0 | 기존 3개 행 조회 |
| B 정상 종료 후 B의 `csql -S` | 0 | 기존 3개 행 조회 |

두 번째 서버 명령은 2.068초, standalone 명령은 0.032초에 반환했다. 이는 이번 한 번의 명령 소요 시간이며 성능 측정이나 무대기 시간 보장이 아니다.

## 실험 구성과 증거

동일 설치를 임시 prefix A/B에 각각 복사했다. 실제 Git worktree 두 개를 새로 빌드한 실험이 아니라, 서로 다른 worktree의 실행 환경을 두 개의 설치 경로·설정·registry·TMP로 재현했다. 두 환경의 `databases.txt`는 같은 물리 data/log/LOB 경로를 가리켰다.

- A master 포트: `41059`, B master 포트: `55011`. socket 경로도 분리했다.
- 같은 DB 이름 `lockprobe`를 사용했으며, 이름이나 master 포트 충돌이 아니라 공유 active-log 잠금으로 거부됐다.
- broker와 PL은 실행하지 않았다. PL은 설정에서 껐다.
- 기존 설치·설정·DB에는 쓰지 않았다. 생성한 프로세스는 실험 전용 CUBRID prefix로 식별해 정리했고, 잔여 프로세스가 없는 것을 확인한 뒤 임시 DB와 설치 복사본을 삭제했다.

[최종 구조화 결과](evidence-final/results.json)에 명령, 반환 코드, 소요 시간, 바이너리 SHA-256, owner PID와 active-log inode를 기록했다. [플랫폼 정보](evidence-final/platform.json)와 [버전 출력](evidence-final/version.txt)도 보존했다. 현재 source checkout의 HEAD와 설치된 바이너리 버전은 다르므로 설치 바이너리의 버전·해시를 실험 식별자로 사용한다.

핵심 원본 증거:

- [두 번째 서버 거부](evidence-final/b-server-rejected.txt)
- [standalone 거부](evidence-final/b-standalone-rejected.txt)
- [소유 서버와 master PID](evidence-final/owner-before-processes.json)
- [실제 POSIX WRITE 잠금](evidence-final/owner-before-locks.txt): active-log inode와 소유 서버 PID 일치
- [거부 이후 프로세스](evidence-final/owner-after-processes.json): 같은 A 서버 PID 유지, 두 번째 서버 없음
- [거부 이후 쓰기·조회](evidence-final/a-health-after-standalone.txt)
- [B로 전환 후 조회](evidence-final/b-read-after-handoff.txt)
- [서버 종료 후 standalone 조회](evidence-final/b-standalone-after-release.txt)

`evidence/`는 최초 탐색 실행 결과다. 그 실행에는 불필요한 B master 직접 기동 단계가 있었으며, 이를 제거하고 PID·inode·정확한 행 수 검증을 보강한 최종 스크립트로 다시 실행한 결과가 `evidence-final/`이다. 두 실행 모두 통과했고 임시 프로세스·파일은 정리했다.

## 설계에 주는 의미

이번 정상 경로에서는 DB 중복 열기를 막으려고 workenv가 별도 잠금을 추가할 필요가 입증되지 않았다. 모든 테스트에 `cub-workenv run`을 강제할 근거도 없다. 일반 실행은 초기화한 환경에서 기존 `cubrid`·`csql`을 사용한다는 방향을 뒷받침한다.

CUBRID 오류가 이미 물리 DB 경로, 사용자, 호스트, 소유 PID를 알려준다. 따라서 소유자 설명을 위해 반드시 workenv가 선점 표시를 남겨야 하는 것도 아니다. 오류에 worktree 이름은 직접 나오지 않으므로, 필요하다면 PID의 실행 환경과 workenv의 초기화 기록을 연결하는 진단 기능을 별도로 검토할 수 있다. 이 매핑 기능은 구현하지 않았다.

## 확인 범위와 제한

- 동일 빌드 두 복사본, Linux 로컬 파일시스템, 정상 active-log 잠금 경로와 정상 종료를 확인했다.
- 서로 다른 버전의 파일 형식 호환성, 동시 최초 기동 경쟁, 강제 종료, stale `.lockby`, 잠금 비활성화 설정, 네트워크 파일시스템, restore 등 특수 유틸리티는 검증하지 않았다.
- 기존 서버가 계속 동작하며 데이터가 순차 전환 후 보존되는 것을 확인했다. 거부된 프로세스가 어떤 파일도 열거나 쓰지 않았다는 시스템콜 수준의 증명은 아니다.
- 수동 복구 절차와 이 범위 밖의 추가 보호 필요성은 별도 설계 대상이다.

## 재현

기존 설치는 읽기 전용 원본으로 사용한다. 출력 디렉터리는 새 경로여야 한다.

```sh
python3 experiments/native-db-exclusion/run.py \
  --install /path/to/cubrid/install \
  --output /tmp/cwe-exclusion-evidence-new
```

스크립트는 고유한 `/tmp/cwe-lock-*` 디렉터리를 만들고 실험 전용 프로세스만 정리한다. 조사할 수 있도록 임시 파일은 남기며 경로를 출력한다. `results.json`의 `cleanup_remaining`이 비어 있고 해당 prefix의 프로세스가 없음을 확인한 뒤 그 실행의 임시 디렉터리만 삭제한다. 저장소에는 재현 스크립트와 판정 근거만 보존하고 DB 볼륨이나 바이너리 복사본은 넣지 않는다.
