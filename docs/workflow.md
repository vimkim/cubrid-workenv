# Build, initialize, use, diagnose

`cub-workenv` prepares one host source worktree and one dedicated installed
CUBRID/preset. Build and install first, then initialize explicitly. Entering a
directory only loads a completed environment; it does not create DBs or run full
diagnosis. The personal tooling integration is a separate repository change;
applying this CLI alone does not replace an existing shared `.envrc` or build
coordinator. Review both repositories before selecting the new tooling. Existing
worktrees that symlink shared tooling are affected when that tooling is applied.

## First use

After building/installing with the chosen source tree's supported workflow:

```sh
cub-workenv init --worktree /path/to/source \
  --install /path/to/dedicated/install --preset debug_gcc \
  --java-home /path/to/compatible/jdk
source /path/to/source/.cub-workenv/env.sh
cubrid server start testdb
csql -C -u dba -c 'select 42;' testdb
cubrid server stop testdb
```

The preset is a recorded selection; init does not configure or compile it.
Installations must be dedicated because CUBRID also writes PL information beneath
its installation. Keep all cooperating worktrees in the same host allocation
namespace. `--state-home` is useful for deliberately isolated test fixtures, not
for hiding production allocations from each other.

To defer DB creation, use `init --no-db` with the same selection arguments, then
`cub-workenv create-db testdb --worktree /path/to/source`. Add `--path
/path/to/external/storage` to create an external DB. Existing registrations can
be supplied to init with `--database-registry /path/to/databases.txt`; read
[DB selection](database-selection.md) before reusing physical storage. Repeating
init on a ready environment is a no-op, including when different options are
supplied. It is not a preset change or a request to create a deferred DB.

With the companion shared loader selected, use `direnv exec . cubrid ...` in a
noninteractive shell; ordinary interactive entry loads the same environment.
For custom Bash integration use `cub-workenv env --worktree PATH --preset NAME
--install PATH`. Evaluate its stdout even on failure to clear inherited runtime
selection, and preserve its failed exit status; do not continue running DB
commands after failed loading. Direct `source env.sh` checks readiness only;
explicit expected-selection checks are provided by `env` and `doctor`.

A→B switching must select B's dedicated install, configuration, registry, TMP and
master port together. The same `testdb` name may contain different data in each.
Normal clients connect to the running server. Workenv does not replace native
commands with PATH wrappers or require a `run` command.

## Diagnose and recover deliberately

```sh
cub-workenv doctor --worktree /path/to/source \
  --install /expected/install --preset debug_gcc
cub-workenv doctor --worktree /path/to/source \
  --native-error-file /path/to/captured-native-error.txt
```

Doctor is read-only. Success and unchanged ready init return 0; preparation or
actual diagnosis errors return nonzero. A historical busy-DB error may be printed
without being a current fault; owner mapping requires current corroboration.
See [doctor](doctor.md) for live-owner criteria and native locking prerequisites.

| Observation | Manual action and completion criterion |
| --- | --- |
| No installation | Build/install the selected preset; rerun explicit init only after its binaries exist. |
| Preset/install mismatch | Restore the intended recorded selection and rerun doctor. A transition to another build needs separate compatibility review; repeated init does not perform it. |
| Pool exhausted | Read the named pool/owner report and recorded stage. Choose a known-safe explicit range, then handle incomplete state below before retrying. |
| Incomplete at allocation, no allocation or DB exists | Apply the bounded pre-allocation procedure below. |
| Failure after allocation or DB preparation | Preserve state, allocation, configuration, registry, native logs and all storage. Diagnose the exact failure. Continue only with a separately reviewed recovery that accounts for every allocated resource and DB; this release has no automatic resume/repair. |
| Stale owned socket after a failed native opener | Prove that this exact environment is stopped, the socket is unbound, and its file is owned by this failed operation. Unlink only that socket and re-run doctor. Uncertain ownership remains an error. |

For **pre-allocation** recovery, first ensure every initializer has exited and
prevent concurrent initialization during the procedure. Record `.cub-workenv`
contents and the host allocation registry outside that directory. Require all
of these facts: state says `preparing` at `allocation`, no `allocation` field,
no registry record for the canonical worktree/install, and the directory contains
only this attempt's `init.lock` and `state.json`. Confirm no DB/config/environment
artifacts, inherited runtime or user files exist there. Preserve that exact
directory by renaming it to a new owned evidence location outside the worktree.
Keep the host allocation registry unchanged. Retry init with the reviewed pool
range, then require ready state and successful doctor. If any prerequisite fails,
use the preserve-and-review path instead. Never delete the whole state directory
or a DB merely because widening the pool did not work.

This bounded procedure was exercised through the public CLI in
[ticket09 recovery evidence](../tests/evidence/ticket09-recovery/results.json).
It is a manual recipe for known owned artifacts, not a generic reset command.

## Shared DBs, shutdown and removal

Two independent openers of the same physical DB are rejected by native locking
in the tested normal paths. Preserve the native user/host/PID/path error, leave
the existing owner running, and wait for its normal shutdown before sequential
reuse. Do not disable locking, add automatic takeover, or treat an ordinary client
as an independent opener. Different versions' file compatibility, abnormal exit,
network filesystems and special utility paths are outside that evidence.

Stop only positively identified instances using their selected native commands.
Before removing a source worktree, follow [database lifetime](database-lifetime.md):
inventory internal/external/mixed storage, preserve user changes and unknown
files, remove only exact owned disposable artifacts, then use non-force Git
worktree removal. External data/log/LOB targets survive removal, even through
internal symlinks. Reclamation of a dead allocation is separate and only occurs
on pool exhaustion after activity/visibility checks.

Initialization checks known conflicts at that point; external tools can later
occupy resources. It is not a sandbox or lasting OS reservation. HA, Manager,
containers, automatic format conversion and global migration are outside this
release. Host initialization does not become a prerequisite for `cubrid-box`.

For provenance, commands, acceptance coverage and observed limits, consult the
[complete workflow verification](evidence/ticket09-workflow.md).

The complete companion-tooling migration retires the legacy runtime engine while
retaining narrow build/install/container coordination. Apply its reviewed commit
and this CLI's creation-provenance revision together. New creation records are
consumed by the personal internal-DB lifecycle recipes; older/reused DBs remain
preserved for manual review. See `my-cubrid/docs/host-workenv.md` for those recipes
and `my-cubrid/docs/complete-workenv-migration.md` for the caller inventory.

## Explicit numeric reset

For a deliberate fresh numeric allocation, use the preview-first `reset` or
`reset-all` workflow in [Reset numeric resource assignments](reset.md).
Databases, logs, installation/configuration paths and TMP identities remain;
only port and broker SHM assignments are released. Explicit reinitialization is
required. This is separate from automatic reclamation and failed-init repair.
