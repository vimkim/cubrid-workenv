# cubrid-workenv

Prepare a dedicated CUBRID host environment for each source worktree, then use
ordinary `cubrid` and `csql` commands.

<p align="center">
  <img src="assets/readme/worktrees.svg" width="100%" alt="Two worktrees with dedicated installations and separate physical databases named testdb: A reads 111 and B reads 222.">
</p>

**Same database name, different data.** In the [recorded coexistence check](tests/evidence/ticket09-coexistence/results.json),
A read `111` and B read `222` through csql and JDBC. B continued working after
A's server and broker stopped. [See the verification report →](docs/evidence/ticket09-workflow.md)

[Why this exists](#why-this-exists) · [How it works](#how-cubrid-workenv-solves-it) · [Get started](#get-started) · [Commands](#commands) · [Boundaries](#boundaries)

## Why this exists

Developers and agents often leave a database running in worktree A while testing
another CUBRID branch in worktree B. **Git separates the source files; host
runtime resources still need their own configuration.** With overlapping settings,
B's commands can reach A's master and its same-named `testdb`, or a broker stop
can affect the other environment.

That makes test results misleading: a query intended to check B's changes may
actually run against A's server. It can also interrupt another experiment or
force developers to wait for long tests before starting their own work.

The causes span several resources. Master and broker ports, broker shared-memory
keys, database registries, and master/PL socket paths can overlap. PL also writes
information files inside the installation. Shell commands select these through
environment variables and configuration, so inherited or partially switched
settings can select the wrong instance. Changing only the DB name or one port
leaves other conflicts unresolved. The [source investigation](docs/handoff-instance-isolation.md)
maps those relationships.

There was a second workflow problem: the previous shared direnv loader ran full
runtime validation on directory entry. Repeated filesystem comparisons,
installation hashing, and host inspection made routine shell entry expensive.
See the [original tooling observations](.scratch/workenv/design-interview.md#existing-tooling-facts).

### Ways to address it

| Approach | Trade-off |
| --- | --- |
| Run host environments one at a time | Stop and switch between runs; long tests block other work. |
| Configure each host environment manually | Coordinate installations, registries, ports, IPC keys, and socket paths for every worktree. |
| Use separate containers | Separate runtime namespaces and manage mounts/storage through a container workflow. |

`cubrid-workenv` automates the coordinated host configuration while keeping
ordinary native commands available. It also separates one-time preparation from
everyday shell entry.

## How cubrid-workenv solves it

1. **Prepare explicitly.** After build and installation, `init` records a dedicated
   installation and preset, writes worktree-local configuration and a database
   registry, and prepares `testdb` unless `--no-db` is selected.
2. **Allocate resources together.** A shared host allocation registry assigns
   distinct master/broker ports and broker SysV shared-memory keys. Each worktree
   gets a short TMP directory for master and PL sockets. Dedicated installations
   keep installation-local PL files separate too.
3. **Load one consistent selection.** The generated `env.sh` clears inherited
   CUBRID overrides and selects the installation, configuration, registry, and
   runtime resources together. Native `cubrid` and `csql` then use that selection.
4. **Keep routine entry cheap.** Loading checks readiness without creating DBs or
   running full diagnosis. Repeating `init` on a ready environment is a no-op;
   explicit, read-only `doctor` handles deeper inspection.

Settings, state, utility logs, and the Bash loader live in `.cub-workenv/`.
New databases use `.cub-workenv/db/` unless you select external storage.
Development-tool paths remain available when the selected CUBRID paths are loaded.

Keep cooperating environments in the **same host allocation namespace**.
It defaults to `${XDG_STATE_HOME:-$HOME/.local/state}/cub-workenv`.
Stopped environments retain their assignments; allocation avoids recorded and
currently occupied resources. It is not a lasting OS reservation.

For pool ranges, storage defaults, direnv integration, and recovery, follow the
[complete workflow](docs/workflow.md).

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
