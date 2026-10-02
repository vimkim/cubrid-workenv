# Ticket 07 verification

## Scope and boundaries

The implementation joins `cubrid-workenv` and the personal `my-cubrid` tooling in
separate topic worktrees. Personal tooling commits: `44c1814c80914baac6c19434e4dd93c1bb555946` and
`49e4b22253530baf240bc2cfee3dc4018834317e`. It does not install the CLI globally, restow existing
source trees, migrate legacy state, alter user installations, or require host
initialization for containers.

`cub-workenv env --worktree PATH [--preset NAME] [--install PATH]` emits Bash.
Callers evaluate stdout even on failure so inherited runtime variables and paths
are cleared, then preserve the command/evaluation failure status. Uninitialized
worktrees return build-only cleanup with explicit init guidance. Completed loading
checks the small state file and selected artifact only. Full diagnosis remains an
explicit `doctor` operation. `env.sh` itself clears inherited selection before
checking readiness, and composes tools/library paths rather than replacing them.

Personal integration additionally accepts `CUB_WORKENV_CLI` and
`CUB_WORKENV_INSTALL`. The latter is the build destination and expected runtime
selection; same-basename worktrees require distinct explicit installation prefixes.
`build`, `install`, `stop-and-build`, and the shared `just build` recipe leave init
explicit. New environments use cheap selection for coordinated runtime recipes;
legacy environments retain the old explicit runtime guard path. The container
recipe uses `installation-use`, retaining the install lock without host validation.
Legacy pwddb name/list lookup supports the new registry; destructive and creation
lifecycle operations refuse the legacy assumptions and give precise alternatives.

## Reproductions

- `python3 -m unittest discover -s tests -p 'test_*.py'`: 16 tests passed on the
  ticket's 01+02 prerequisite base, including PATH composition, incomplete artifact
  cleanup, preset/install mismatch and no-write build-only loading.
- In the personal tooling worktree: `python3 tests/runtime-lock-test.py` (13),
  `python3 tests/runtime-environment-test.py` (14), `python3 tests/pwddb-test.py` (25)
  passed. `CUB_WORKENV_CLI=<this CLI> python3 tests/workenv-integration-test.py`
  passed; it exercises both repositories through public CLI, shell loader, helper
  and coordinator boundaries. Bash syntax and Git whitespace checks passed.
- TDD observed failures before fixing hardcoded PATH replacement, inherited
  runtime leakage, automatic legacy initialization, new-environment legacy
  manifest rejection, and container host-init coupling.
- [Real-flow script](../../tests/real_environment.py) runs the shared live
  `just configure`/`just build` on a disposable tiny CMake C project, proving actual
  compile/install succeeds before `.cub-workenv` exists. After explicit init, the
  shared `just ctest` path executes and passes the fixture executable test. This is a build-integration
  test, **not a CUBRID engine rebuild**; ticket09 owns the full source build flow.
- The script copies real CUBRID installations independently, explicitly initializes
  them in an isolated 46000–46999 pool, starts two `testdb` servers, writes different
  markers, repeats direnv entry, switches a single shell A→B, and queries ordinary
  `csql`. [Results](../../tests/evidence/ticket07/results.json) include exact commands,
  timings, selected states, copied-binary hashes, and an empty cleanup remainder.
  The copied installation's actual versions are in `a-version.txt`/`b-version.txt`.
  [A→B output](../../tests/evidence/ticket07/switch-a-to-b.txt) proves 701 then 702
  and B's selected install/TMP/registry/master port.
- `a-execve.txt` and `b-execve.txt` record repeated-entry execution. No CUBRID utility,
  init, doctor, legacy validate, installation hash, or host resource scan executes.
  Existing build-tool setup (Homebrew ncurses lookup) remains in the shared loader.

## Timings and limits

[Comparison script](../../tests/compare_environment.py) alternates old personal
`.envrc` at `f2aa990` and the changed loader on the same disposable uninitialized
CUBRID-shaped Git fixture, with the same HOME, preset, PATH and tool versions.
All six entries succeed and remain build-only. The fixture is explicitly not a
legacy initialized runtime: these samples do not quantify removed full validation
on a ready legacy environment.

[Raw comparison](../../tests/evidence/ticket07-comparison/results.json), seconds:

| Entry | Old | New |
| --- | ---: | ---: |
| 0 | 0.230126 | 0.111910 |
| 1 | 0.204924 | 0.110314 |
| 2 | 0.211439 | 0.115207 |

Prepared new-environment entry
samples are recorded separately in real-flow results. These local observations are
not an SLA or a claim of equal warm/cold cache conditions. The reproduction keeps
HOME unchanged and uses task-specific XDG, install, and tooling paths. Native
text logs normalize trailing whitespace; commands, return codes and values remain
unchanged.

The first native harness attempted capture through pipes and timed out because a
CUBRID daemon retained the pipe. It cleaned up only owned processes. The corrected
harness captures native output to files. A subsequent relative strace output path
was corrected to an absolute path before the successful evidence run. Earlier
attempts' logs remain in `/tmp/cwe-ticket07-*-evidence` for inspection; final evidence
contains the successful versioned run. Existing source/user installations were
read only and generated databases, copies, TMP directories, and owned processes
were removed after verification.
