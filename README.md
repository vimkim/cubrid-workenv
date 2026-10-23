# cubrid-workenv

Prepare a dedicated CUBRID host environment for each source worktree, then use
ordinary `cubrid` and `csql` commands.

<p align="center">
  <img src="assets/readme/worktrees.svg" width="100%" alt="Two worktrees with dedicated installations and separate physical databases named testdb: A reads 111 and B reads 222.">
</p>

**Same database name, different data.** In the [recorded coexistence check](tests/evidence/ticket09-coexistence/results.json),
A read `111` and B read `222` through csql and JDBC. B continued working after
A's server and broker stopped. [See the verification report →](docs/evidence/ticket09-workflow.md)

[Get started](#get-started) · [Commands](#commands) · [Boundaries](#boundaries) · [Verification](#verification)

## Get started

Requires **Linux, Python 3.10+, and Bash**. With [uv](https://docs.astral.sh/uv/)
installed, run from this checkout to install or refresh the CLI:

```sh
just sync
cub-workenv --help
```

`just install` is an alias. Without just, use `uv tool install --reinstall .`.

**Build and install CUBRID first.** Choose an installation dedicated to this
worktree. `--preset` records your selected build label; initialization does not
configure, build, or install CUBRID.

```sh
cub-workenv init --worktree /path/to/source \
  --install /path/to/dedicated/install --preset debug_gcc
source /path/to/source/.cub-workenv/env.sh

cubrid server start testdb
csql -C -u dba -c 'select 42;' testdb
cubrid server stop testdb
```

The query should return `42`. Initialization creates `testdb` by default.
PL uses the installation's default Java unless `--java-home` or `JAVA_HOME`
selects a compatible JDK at initialization.

<details>
<summary>Installation paths and updates</summary>

`just sync` installs an independent command with `uv tool install --reinstall .`;
source changes take effect after the next sync. It also replaces the legacy
launcher symlink from this checkout while preserving unrelated files and links.

If needed, add uv's command directory to your PATH. The usual default is
`~/.local/bin`:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

In Nushell, use `path add ~/.local/bin`. Set `CUB_WORKENV_BIN_DIR=/your/bin`
or `UV_TOOL_BIN_DIR=/your/bin` when installing to select another directory.
You can also run `bin/cub-workenv` directly from the checkout.

</details>

## What each worktree gets

- **A selected installation.** One dedicated CUBRID installation and a recorded
  preset, loaded together when you enter the environment.
- **Local settings and storage.** Configuration, database registry, state,
  utility logs, and the Bash loader live in `.cub-workenv/`. New databases use
  `.cub-workenv/db/` unless you select external storage.
- **Distinct runtime resources.** Allocated master and broker ports, two broker
  SysV shared-memory keys, and a short TMP directory for master and PL sockets.

Loading `env.sh` checks readiness, clears inherited CUBRID overrides, and selects
the installation's binaries and libraries while retaining development-tool paths.
It does not initialize databases or run diagnosis. Repeating `init` on a ready
environment is a no-op, even with different options.

Keep cooperating environments in the **same host allocation namespace**.
It defaults to `${XDG_STATE_HOME:-$HOME/.local/state}/cub-workenv`.
Stopped environments retain their assignments; allocation avoids recorded and
currently occupied resources. It is not a lasting OS reservation.

For pool ranges, storage defaults, direnv integration, and recovery, follow the
[complete workflow](docs/workflow.md).

## Commands

| Command | Purpose |
| --- | --- |
| `init` | [Prepare an environment](docs/workflow.md#first-use); `--no-db` defers `testdb` creation. |
| `create-db NAME` | [Add a database](docs/database-selection.md); `--path` selects external storage. |
| `env` | [Emit Bash](docs/workflow.md#first-use) to load a ready environment and check expected selections. |
| `doctor` | [Inspect selection, storage, and ownership](docs/doctor.md) without changing them. |
| `reset` / `reset-all` | [Preview release of ports and SHM assignments](docs/reset.md) for reinitialization. |
| `prune` | [Preview removal of missing linked worktree registrations](docs/prune.md) and their idle allocations. |

For example, add a database or check the expected selection:

```sh
cub-workenv create-db example --worktree /path/to/source
cub-workenv doctor --worktree /path/to/source \
  --install /path/to/dedicated/install --preset debug_gcc
```

`reset`, `reset-all`, and `prune` apply changes only with `--apply`, after
inactivity checks. They do not stop processes or delete database storage.

## Boundaries

**Separate physical databases can run side by side. Shared physical storage
must be opened sequentially.** Native CUBRID locking rejected a second server
and standalone opener in the tested normal paths; ordinary clients connect to
the running server. Read [DB selection](docs/database-selection.md) before
reusing storage, and [database lifetime](docs/database-lifetime.md) before
removing a worktree. External data, logs, and LOB storage survive worktree removal.

The generated configuration enables a server, one `workenv` broker, and PL over
Unix sockets. HA and CUBRID Manager are not enabled. Host preparation is
independent of the separate `cubrid-box` container tool.

Failed initialization preserves its stage, allocations, logs, and database
evidence for [manual recovery](docs/workflow.md#diagnose-and-recover-deliberately).
There is no automatic repair or cross-version database conversion. Installing
this CLI does not apply companion personal-tooling changes or restow existing
source trees; review that integration separately.

## Verification

The [integrated verification report](docs/evidence/ticket09-workflow.md) records a
fresh **CUBRID 11.5.0.2635-30043f4** source build on Linux with **Java 8**:
direct csql, JDBC, PL, two-environment coexistence, shared-DB exclusion,
read-only diagnosis, and internal/external database lifetime.

These results cover the recorded builds and normal local-filesystem paths.
Cross-version compatibility, crash recovery, network filesystems, HA, Manager,
and container behavior are outside that evidence. Use a JDK compatible with
your CUBRID build; Java 21 failed PL startup in an earlier recorded experiment.

Run the CLI test suite from this checkout:

```sh
python3 -m unittest discover -s tests -v
```

Native acceptance scripts and their reproduction commands are documented in the
[verification report](docs/evidence/ticket09-workflow.md#cleanup-and-reproduction).
For development context, see the [specification](.scratch/workenv/spec.md),
[native locking experiment](experiments/native-db-exclusion/README.md),
[allocation reclamation](docs/allocation-reclamation.md), and [handoff](HANDOFF.md).
