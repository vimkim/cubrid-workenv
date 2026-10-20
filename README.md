# cubrid-workenv

Explicit host work environment preparation for CUBRID source worktrees.
Requires Linux, Python 3.10+ and bash. Run `just sync` (or `just install`) with
uv installed to install or refresh an independent `cub-workenv` command using
`uv tool install --reinstall .`. Source changes take effect after the next sync.
The recipe also replaces the legacy launcher symlink from this checkout;
unrelated existing files or links are preserved. Set
`CUB_WORKENV_BIN_DIR=/your/bin` or `UV_TOOL_BIN_DIR=/your/bin` to select another
installation directory; otherwise uv uses its default user command directory.

If needed, add that directory to your shell PATH (`export PATH="$HOME/.local/bin:$PATH"`
in Bash, or `path add ~/.local/bin` in Nushell). Without just, run
`uv tool install --reinstall .` to install the package, or run `bin/cub-workenv`
directly from the checkout.

```sh
just sync
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
to this work environment. The generated settings enable the server, one `workenv` broker, and PL over
Unix sockets; HA and CUBRID Manager are not enabled. The allocation registry
refuses reuse of one normalized installation by two worktrees because PL
information files live under the installation.
Host initialization is independent of the separate cubrid-box container tool.

The initial internal `testdb` uses 64M data and 32M log volumes, locale
`en_US.utf8`, and `.cub-workenv/db/testdb/{data,log,lob}`. Its registry is
`.cub-workenv/databases/databases.txt`. Settings, state, utility output and the
bash environment artifact also live under `.cub-workenv`. Native utilities use
the selected installation directly, without a `run` wrapper. Loading `env.sh`
checks only the ready marker, clears inherited CUBRID overrides and selects the
installation's bin/lib directories. It retains development-tool paths while replacing inherited CUBRID installation paths.

Host allocations default to `${XDG_STATE_HOME:-$HOME/.local/state}/cub-workenv`;
`--state-home` selects another cooperating allocation namespace for disposable
tests. All cooperating real environments must use the same namespace.
`--port-start` and `--port-end` default to 41000 and 41999 inclusive; each
environment uses one master and one broker port. `--shm-start` and `--shm-end`
default to `0x62000000` and `0x6200ffff` inclusive (decimal or hex accepted).
Each environment uses two SysV keys: broker MASTER and APPL_SERVER. The allocator
checks `/proc/sysvipc/shm` and skips recorded keys, including stopped worktrees.
Allocation skips recorded and currently bound TCP ports and fails when this finite pool is
exhausted. Stopped environments retain assignments. A short flock transaction
protects atomic allocation publication; this is not a lasting OS reservation.
TMP directories use `/tmp/cwe-UID/DIGEST`, beginning with 12 SHA-256 hex digits
and extending on collision. Ownership and socket path length are checked.

PL uses the installation's bundled/default Java unless `--java-home` or
`JAVA_HOME` selects a JDK at initialization. That normalized selection is recorded
and exported as `CUBRID_JAVA_HOME`; inherited CUBRID overrides are not trusted.
Use a JDK compatible with the selected CUBRID build. The verified
11.5.0.2602-a0026f9 installation uses Java 8; Java 21 failed PL startup in the
recorded experiment. Each generated configuration has a single broker, so there
are no unallocated default query-editor/broker sections. Broker connections use
the recorded `broker_port` and the environment's own database registry.

A ready environment's repeated `init` is a no-op. `init --no-db`, `create-db`,
compatible existing registrations, fast `env` loading and read-only `doctor` are
implemented. Failures preserve stage, allocation and DB evidence; automatic
repair and cross-version conversion are outside scope.

Follow the [complete workflow](docs/workflow.md) for deferred DB creation,
external storage, companion direnv/build integration and bounded manual recovery.
The companion personal-tooling change must be reviewed and applied separately;
installing this CLI does not silently restow existing source trees. See
[verification and acceptance coverage](docs/evidence/ticket09-workflow.md) for the
fresh CUBRID source build and integrated native checks.

Checks:

```sh
python3 -m unittest discover -s tests -v
python3 tests/real_smoke.py --install /path/to/installed/cubrid --output /tmp/cwe-new-evidence
python3 tests/real_coexistence.py --install /path/to/installed/cubrid --java-home /path/to/compatible/jdk --output /tmp/cwe-coexist-evidence
```

The real check copies the installation, creates disposable storage, uses only
owned processes, records commands/version/ports/paths/SQL, and removes runtime
files only after confirming no owned processes remain. Output must be a new
directory. See [the implementation specification](.scratch/workenv/spec.md),
[native exclusion evidence](experiments/native-db-exclusion/README.md) and
[handoff](HANDOFF.md) for project scope and remaining work.

The coexistence check copies two installations and uses the same `testdb` name
with different physical databases. It tests real csql and JDBC sentinel reads,
Java stored-function execution, separate master/PL sockets and broker IPC, and
B's continued operation after A's server and broker stops. Runtime cleanup uses
instance commands and exact-installation PID ownership; it verifies no owned
processes or IPC remain. [Ticket 05 evidence](tests/evidence/ticket05/results.json)
records the tested build and resource identities. This verifies that build's
normal host execution; it does not reserve resources against later external
users or establish container, HA, Manager, or cross-version compatibility.

On pool exhaustion, [allocation reclamation](docs/allocation-reclamation.md)
releases only deleted worktrees with no observed activity and reports uncertain
owners without removing processes, files or IPC.
