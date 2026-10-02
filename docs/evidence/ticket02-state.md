# Ticket 02: initialization state and concurrency

Verified on 2026-10-02 from integration base `c010fe446222204c4f8f9d4f67b06a1bede87a9b`.

Run: `python3 -m unittest discover -s tests -p 'test*.py' -v`

Result: 13 tests passed, including seven new CLI/artifact tests in
`tests/test_state.py`. New tests use disposable state directories and ports
43000–43999, checking actual port availability through the allocator.

| Acceptance | Evidence |
| --- | --- |
| Repeated initialization ignores changed options and preserves contents | `test_repeat_ignores_changed_options_but_detects_missing_artifacts` changes install, preset and state home; compares all files, including allocation records |
| Missing/corrupt artifacts fail without repair | Same test removes cubrid.conf; `test_corrupt_state_diagnosis_and_uninitialized_diagnosis_are_read_only` supplies malformed state JSON and checks error output and unchanged files |
| Failure after allocation retains state | `test_failure_after_allocation_preserves_work_clues` holds the external allocation lock, introduces a settings directory collision, then observes settings-stage failure and retained allocation |
| Failure after settings retains native error | `test_native_failure_retains_stage_and_doctor_explains_without_changes` supplies a native utility that exits 9, checks database stage and createdb.log guidance |
| Failure after DB work cannot publish readiness | `test_failure_after_database_does_not_publish_environment` makes env.sh unwritable as a file using a directory collision; state remains preparing at environment publication |
| Abrupt termination and subsequent init preserve incomplete state | `test_terminated_initializer_leaves_incomplete_state` has the disposable native fixture SIGKILL its initiating CLI; doctor reports the recorded database stage |
| Same-worktree serialization and independent-worktree progress | `test_same_worktree_serializes_but_other_worktree_can_finish` holds A's native command on an owned gate; B completes with distinct allocations while a second A waits; exactly one native invocation writes A's call record |
| Minimal read-only doctor | Failure tests compare file bytes before and after doctor and reinitialization; doctor reads the original state home and never creates an initialization lock |

TDD observations: changed-option repeat initially failed because CLI validated
the replacement installation before reading completed state. The native-failure
check initially failed because no stage was recorded. Both passed after their
corresponding implementation changes. Additional failure/concurrency checks
exercise the existing atomic publication and lock boundaries without adding
production fault-injection hooks.

Native executables here are controlled shell fixtures at the subprocess
boundary. These tests prove state handling and locking, not actual DB creation,
broker/PL coexistence, native DB exclusion, or crash durability after power loss.
Ticket 01's real engine smoke evidence remains separate. Full doctor resource,
DB registration and owner inspection belongs to ticket 06.

## Additive interfaces

- `cub-workenv doctor --worktree PATH` inspects state without requiring install
  or preset options. Success is zero; missing, corrupt or incomplete state is
  nonzero with manual inspection guidance.
- Existing state schema/status stay unchanged (`schema: 1`, `preparing`/`ready`).
  `stage` describes the operation about to run; `error` preserves a caught
  failure. SIGKILL may leave a stage without an error.
- `doctor.read_state(worktree)` validates the JSON envelope;
  `doctor.ready_problems(state, worktree)` returns lightweight artifact issues;
  `doctor.diagnose(args)` provides the CLI boundary for ticket 06 to extend.
- Repeated init checks the recorded installation and state home, ignores new
  options, and performs no DB opens or host process scans.

## Ticket 03 integration follow-up

On parent-provided base `d8781009bcb2b7a1ac59ea135a327ae90542bdeb`,
updated ticket 02's successful native fixtures to emit a registry row from
createdb's public `-F`, `-L`, `-B` and DB-name arguments. This includes the
post-DB publication failure and concurrent initialization fixtures. The fixtures
therefore reach their intended lifecycle stages under ticket 03's registry
publication contract. Failure/SIGKILL fixtures still exit before registration.

Doctor now points to the actual initialization log, `createdb-testdb.log`.
Concurrent-test cleanup releases the gate and joins every started child before
asserting exit status; its cleanup also covers failures during gate setup.
Timeout cleanup kills only the owned fixture CLI and collects its output.

Validation: `python3 -m unittest discover -s tests -p 'test*.py' -v`
passed all 18 tests (including all seven ticket 02 tests); `git diff --check`
passed. This is fixture integration evidence, not a new native-engine claim.
