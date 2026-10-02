# cubrid-workenv

Explicit host work environment preparation for CUBRID source worktrees.
Requires Linux, Python 3.10+ and bash. Run directly from this checkout (no
installation or dependencies required), or add this checkout's `bin` directory
to PATH:

```sh
export PATH="/path/to/cubrid-workenv/bin:$PATH"
cub-workenv --help
cub-workenv init --worktree /path/to/source --install /path/to/installed/cubrid --preset debug_gcc
source /path/to/source/.cub-workenv/env.sh
cubrid server start testdb
csql -C -u dba -c 'select 42;' testdb
cubrid server stop testdb
```

Build and install CUBRID yourself before initialization. `--install` and
`--preset` are explicit: the preset is the recorded user-selected label, not
an inferred or automatically built CMake preset. Use an installation dedicated
to this work environment. This first slice verifies the server/client path;
broker and PL coexistence is still assigned to ticket 05 (PL is disabled here).
Host initialization is independent of the separate cubrid-box container tool.

The initial internal `testdb` uses 64M data and 32M log volumes, locale
`en_US.utf8`, and `.cub-workenv/db/testdb/{data,log,lob}`. Its registry is
`.cub-workenv/databases/databases.txt`. Settings, state, utility output and the
bash environment artifact also live under `.cub-workenv`. Native utilities use
the selected installation directly, without a `run` wrapper. Loading `env.sh`
checks only the ready marker, clears inherited CUBRID overrides and selects the
installation's bin/lib directories. Its baseline PATH is `/usr/local/bin:/usr/bin:/bin`.

Host allocations default to `${XDG_STATE_HOME:-$HOME/.local/state}/cub-workenv`;
`--state-home` selects another cooperating allocation namespace for disposable
tests. All cooperating real environments must use the same namespace.
`--port-start` and `--port-end` default to 41000 and 41999 inclusive. Allocation
skips recorded and currently bound TCP ports and fails when this finite pool is
exhausted. Stopped environments retain assignments. A short flock transaction
protects atomic allocation publication; this is not a lasting OS reservation.
TMP directories use `/tmp/cwe-UID/DIGEST`, beginning with 12 SHA-256 hex digits
and extending on collision. Ownership and socket path length are checked.

A ready environment's repeated `init` is a no-op. Unknown local artifacts and
existing local DB registries are preserved and refused; compatibility-based
reuse is ticket 03. Failure preserves preparation state and allocation evidence;
never delete database files to retry blindly. The `doctor` guidance points to
ticket 02/06's forthcoming diagnosis command. Automatic recovery, reclamation,
direnv/build integration and cross-version DB compatibility are not provided by
this first slice.

Checks:

```sh
python3 -m unittest discover -s tests -v
python3 tests/real_smoke.py --install /path/to/installed/cubrid --output /tmp/cwe-new-evidence
```

The real check copies the installation, creates disposable storage, uses only
owned processes, records commands/version/ports/paths/SQL, and removes runtime
files only after confirming no owned processes remain. Output must be a new
directory. See [the implementation specification](.scratch/workenv/spec.md),
[native exclusion evidence](experiments/native-db-exclusion/README.md) and
[handoff](HANDOFF.md) for project scope and remaining work.
