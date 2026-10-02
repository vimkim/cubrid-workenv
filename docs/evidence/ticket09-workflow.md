# Complete workflow verification

Ticket09 joins the integrated tickets01–08 at `c610fb86c41e51c643b60647cd95a2e9c6920f0b`
and companion personal tooling `aea80789165951be4602d042476c88bd5105e049`.
This is verification of the selected candidate, not a global tooling rollout.
Implementation work is tracked by ledger256; parent orchestration owns integration
and final Standards/Spec review. Later review fixes need their own focused evidence. Companion tip `74a13cf2508e1da8c528b0c0f1723566ab8a853d` adds documentation corrections only; recorded native evidence correctly retains `aea8078`.

## Actual source build

A new sibling source worktree `/home/vimkim/gh/cb/workenv09-source`, branch
`verify/workenv09-source`, was pinned to CUBRID
`30043f492225c8350aa15455dc329c87227b5fdf`. The existing develop worktree's dirty
status was preserved byte-for-byte in [before](../../tests/evidence/ticket09-build/develop-before.txt)
and [after](../../tests/evidence/ticket09-build/develop-after.txt) inventories.

Preparation used the prescribed global `prepare-build` entry with candidate
`MY_CUBRID=/home/vimkim/my-cubrid-workenv-07`, this checkout's `CUB_WORKENV_CLI`,
a task-specific local-recipe root and `CUB_WORKENV_INSTALL=/tmp/cwe-workflow09-install`.
HOME/CODEX_HOME were unchanged. All four shared preparation links resolved into
the candidate. Preparation runs the existing `lefthook install` synchronization;
no source or personal-tooling main files were edited or globally restowed.

The live interface listed `debug_gcc`. `direnv exec . just configure` and
`direnv exec . just build` compiled and installed real CUBRID, with Temurin
`8.0.462+8`. Initial build required no `.cub-workenv` and ended with explicit-init
guidance. This is a real engine source build, unlike ticket07's tiny CMake fixture.
JDBC was then initialized at pinned submodule
`71d7dfeef93eb788f8b03b7bd21a9e4974a7a7c0` and `just configure-build` compiled
and installed its driver. CCI was pinned at
`79d0888c26a2543d31f53eb7b6c9738db110fff4`.

[Build provenance](../../tests/evidence/ticket09-build/provenance.json) records
paths, candidate links, exact source/tooling commits, commands, return codes and
binary/JAR SHA-256. Logs for [configure](../../tests/evidence/ticket09-build/configure.txt),
[build/install](../../tests/evidence/ticket09-build/build.txt) and
[JDBC addition](../../tests/evidence/ticket09-build/jdbc-configure-build.txt) are retained.
The actual version is **11.5.0.2635-30043f4**, 64-bit Linux debug, compiled
2026-10-02 17:49:59. The JDBC addition left cubrid/csql/cub_server hashes unchanged.

`direnv exec . just ctest` returned 0 but reported **No tests were found**.
No engine unit-test coverage is claimed. The relevant public CLI discovery ran
**34 tests, all passing**, including the private-PID/proc reclamation suite:
[output](../../tests/evidence/ticket09-build/cli-tests.txt). Namespace availability
is recorded by that output, not assumed on another host.

## Integrated results

| Boundary | Result and evidence |
| --- | --- |
| Source build → explicit init → direct use | [Source flow](../../tests/evidence/ticket09-flow/results.json): build-only entry creates no runtime; init0, start0, committed SQL marker901; repeated init0 preserves settings/registry/allocation/state. |
| Ready reentry and A→B selection | Same source flow: three direct direnv csql entries read901; trace excludes init/doctor/createdb/validate; copied B `--no-db` then create-db reads902; A→B yields901 then902. This slice copies only B; A is the fresh source installation. |
| Correct/mismatched selection | Source doctor0, explicit wrong preset doctor1, corrected expected selection doctor0, protected artifacts unchanged. |
| Pool exhaustion → incomplete → manual recovery | [Recovery](../../tests/evidence/ticket09-recovery/results.json): tiny pool fails1; wider pool alone fails1; doctor1 explains stage. With no allocation/DB and only two owned state files, archive preserves host registry; explicit wider retry0 and doctor0. |
| Two server/broker/PL environments | [Coexistence](../../tests/evidence/ticket09-coexistence/results.json): fresh-build copies, separate ports/TMP/IPC/PL sockets, same-name DB sentinels111/222, JDBC and PL17, B remains healthy after A server and broker stops. All native calls asserted successful. |
| Shared physical DB | [Shared DB](../../tests/evidence/ticket09-shared/results.json): second server1 and standalone1 with owner user/host/PID/path; original writes remain healthy; normal shutdown permits sequential server/standalone reuse. |
| Read-only diagnosis | [Doctor](../../tests/evidence/ticket09-doctor/results.json): hashes, PIDs and socket metadata unchanged; native error and corroborated owner retained; syscall traces; existing DB remains healthy. Stale B socket is a diagnosed failure, not hidden. |
| Manual stale-socket remedy and post-JDBC source use | [Final source completion](../../tests/evidence/ticket09-completion-green/results.json): marker901 survives, another standalone opener rejects1; await its PL exit, verify no B process or bound socket, unlink exact owned socket, doctor0; normal DB/master stops and zero owned PIDs. |
| Worktree/DB lifetime | [Lifetime](../../tests/evidence/ticket09-lifetime/results.json): actual linked Git worktree removal without force, internal storage removed, external data/log/LOB byte-identical through removal and original SQL/BLOB sentinel readable from B. Unknown ignored files and tracked edits block cleanup until creator-preserved; mixed storage is a preserve/review case. |

## Attempts and limits

The initial source-flow harness reached both normal server/master stops, then its
strict zero-owned-process assertion found the source build's Gradle daemon.
[Exact PID/command ownership](../../tests/evidence/ticket09-build/owned-gradle-stop.json)
was confirmed before SIGTERM. The initial result remains unmarked as a passing
whole harness; its successful command steps and the completed follow-up together
provide the source-flow evidence.

A supplementary continuation initially assumed doctor must immediately report a
stale B PL socket after rejected standalone access. PL can still be exiting:
doctor correctly returned0 with a confirmed live PL owner, then1 after it exited.
The harness now waits for actual B process exit before unlinking. That interrupted
attempt also lost its source master before later stop commands; its servers retried
the missing master. The cause was not independently established. Its
[partial results and native logs](../../tests/evidence/ticket09-completion/results.json)
are retained, including exact-prefix SIGTERM cleanup of four owned server/PL PIDs.
A later source preflight reported the remaining unbound master socket; the
[preflight output](../../tests/evidence/ticket09-completion-final/post-jdbc-source-doctor.txt)
is retained. The final continuous probe removed only confirmed stopped owned
socket paths, then completed native work and normal stops. These observations do
not establish general abnormal-shutdown recovery or an engine defect fix.

The earlier01/03/05 native evidence used installed **2602-a0026f9**. Later06/07/08
used installed **2635-30043f4**. This ticket independently built **2635-30043f4**
and recorded hashes, then reran engine-dependent integration boundaries. Earlier
CLI state/concurrency/collision/reclamation evidence remains applicable to
unchanged production behavior; it was not replaced with native simulations.
The new discovery run checks composition, not extra claims about engine locking.

Normal local-filesystem paths, one build with Java8, standard server/client/
standalone use, one generated broker, and PL are covered. Cross-version DB
compatibility, simultaneous first-opener races, arbitrary utility modes, disabled
locking, crash recovery, network filesystems, HA, Manager and containers remain
outside the evidence. Allocation is not an OS reservation against later outsiders.
Prepared entry timing samples are observations, not an SLA; ticket07's old/new
comparison remains a build-only comparison, not ready-legacy timing evidence.

## Acceptance coverage map

The rows below cover every validation area in the approved specification. Prior
owner evidence remains authoritative for unchanged narrow behavior.

| Specification area / stories | Prior owner evidence | Integrated addition |
| --- | --- | --- |
| First init (1,2), short identity/socket limit (13) | 01 tests/test_cli.py and ticket01 | Fresh source build/init; coexistence socket paths |
| Environment-only/add DB (3,4), existing DB preservation/failure (5,6), additional registry (20) | 03 tests/test_database.py and ticket03 | Source B no-db/create; shared native reuse |
| Repeat/interrupted state (7,8) | 02 tests/test_state.py; docs/evidence/ticket02-state.md | No-write repeat and concrete pool-failure recovery |
| Read-only diagnosis/owner (9,10,25) | 06 tests/test_doctor.py and native syscall evidence | Rebuilt native hashes/PIDs/owner proof, mismatch and socket remedy |
| Numeric allocation/stopped owner (11,12,14), concurrent init (15) | 01/02 public CLI and 04 reclamation suite | Broker IPC/native coexistence; 34-test integrated discovery |
| Pool/reclamation/uncertainty (16,17,18) | 04 tests/reclamation_cases.py private PID/proc cases | Real selected installs, tiny-pool exhaustion and bounded retry |
| Same-name separate DB/master/PL (13,19) | 05 real_coexistence.py | Rebuilt JDBC/PL coexistence, stop noninterference |
| Direct commands/client use (21,22) | 01/03/05 native evidence | Real source and shared native flow |
| Shared storage exclusion/sequential use (23,24,25) | 03 native evidence | Rebuilt second-server/standalone rejection, health and reuse |
| DB lifetime (26) | 08 real_database_lifetime.py and manual procedure | Rebuilt real Git removal and external SQL/BLOB preservation |
| Selected preset/cheap loading (27,28) | 07 tests/test_environment.py, compare_environment.py, companion tests | Actual engine build, env trace, repeated entry, A→B and mismatch |
| Existing integration/agent guidance (1,21,27–30) | 07 companion coordinator/envrc/source guidance | Candidate symlink provenance; updated README/HANDOFF/AGENTS/workflow; unchanged container boundary |

## Cleanup and reproduction

[Cleanup](../../tests/evidence/ticket09-cleanup/results.json) records zero owned
processes, no matching SysV IPC or registered Unix sockets, and exact-file cleanup
with symlinks unlinked without traversal. The compressed removal inventory
includes 17,754 owned files/links; source DBs, build output, copied installs,
fixture external DBs (after preservation/reuse checks), private allocation
registries and TMP paths were removed. This final fixture disposal is separate
from the demonstrated rule preserving an external user DB through worktree removal.

Git refused source worktree removal: `working trees containing submodules cannot
be moved or removed`. **The clean source checkout and branch remain** at
`/home/vimkim/gh/cb/workenv09-source`, `verify/workenv09-source`, pinned 30043f492.
No force removal or shared submodule deinitialization was used. Initialized CCI/JDBC
checkouts remain; the build-generated CCI header diff was recorded and only that
known generated change restored. Parent/user can decide their later non-forced
cleanup. The task's CLI worktree remains for review as usual.

To reproduce, create a fresh pinned CUBRID source worktree and select candidate
MY_CUBRID/CUB_WORKENV_CLI, an explicit unique CUB_WORKENV_INSTALL and compatible
JAVA_HOME. Use the live preparation/configure/build workflow above, initialize
JDBC before configure/build when testing broker JDBC. Inspect/stop only the
owned Gradle build daemon before a strict zero-process runtime check. Then run:

```sh
python3 tests/real_source_workflow.py --source SOURCE --install INSTALL \
  --tooling TOOLING --java-home JAVA8 --output NEW_FLOW_DIR
python3 tests/real_manual_recovery.py --install INSTALL --output NEW_RECOVERY_DIR
python3 tests/real_coexistence.py --install INSTALL --java-home JAVA8 --output NEW_COEXIST_DIR
JAVA_HOME=JAVA8 python3 tests/real_database.py --install INSTALL --output NEW_SHARED_DIR
python3 tests/real_doctor.py --install INSTALL --java-home JAVA8 --output NEW_DOCTOR_DIR
python3 tests/real_database_lifetime.py --install INSTALL --java-home JAVA8 --output NEW_LIFETIME_DIR
```

Text logs normalize trailing whitespace only. Each script uses dedicated pools/private namespaces, captures native daemon output
to regular files, and records commands/status. The source workflow and recovery
fixtures are deliberately retained for reviewed cleanup; consult their results
before removing exact owned files. `complete_source_evidence.py --prior
FLOW_DIR/results.json --output NEW_DIR --db-name UNIQUE_NAME` exercises the
supplementary socket remedy on that owned stopped fixture. Never use fixture
cleanup scripts on an arbitrary user worktree.
