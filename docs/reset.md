# Reset numeric resource assignments

`reset` releases one worktree's master/broker ports and broker SHM keys.
`reset-all` releases those assignments for every record in one host allocation
namespace, including registered worktrees that have since been removed. Neither
command deletes databases, logs, configuration files, installation trees, TMP
paths, or their contents. Identity records retain `worktree`, `install`, and
`tmp`; only the four numeric fields are released. This is explicit maintenance,
separate from exhaustion-triggered reclamation of deleted worktrees.

```sh
# Inspect first; neither command applies changes by default.
cub-workenv reset --worktree /path/to/source
cub-workenv reset-all

# After stopping affected instances and reviewing the preview:
cub-workenv reset --worktree /path/to/source --apply
cub-workenv reset-all --apply
```

`reset` defaults to the worktree's recorded allocation namespace. `reset-all`
defaults to `${XDG_STATE_HOME:-$HOME/.local/state}/cub-workenv`. Both accept
`--state-home PATH`. All means the selected namespace, not every state-home on
the machine and not just the current Git repository. Ready or partially prepared
worktrees absent from that registry are not discovered or silently adopted.

## Before applying

Stop each affected server, broker, master and PL process using its own native
instance commands. End other commands or shells still carrying those allocations.
The reset caller and its non-CUBRID ancestors are exempt from process checks;
reload or leave those shells after resetting. A child cannot revoke environment
variables already loaded in another shell. Prevent other tools from starting
instances until reset and reinitialization finish.

Both preview and apply check free TCP ports, absence of assigned SysV SHM keys,
absence of live sockets under the recorded TMP, and process references to the
worktree/install/TMP/port. Unknown process visibility blocks release. Stale TMP
files remain untouched, and may still need separately reviewed cleanup reported
by `doctor`. No process is killed and no socket or kernel SHM segment is removed.
A port cannot be reclaimed from a running owner; stop that owner. An existing
SHM segment must be removed by its owning broker's normal shutdown or after
manual ownership inspection. Reset releases the allocator's assignments once
those OS resources are unused; it is not a force-cleanup command.

The allocation lock serializes reset with resource allocation. Nonblocking
per-worktree init locks prevent a deadlock with initializers and refuse reset
while a cooperating initialization/database operation is active. Those locks do
not stop unrelated native commands, so this is a maintenance operation rather
than an OS reservation or sandbox. IPC and process checks observe the caller's
Linux namespaces; use the same host namespaces as the instances being reset.

## Reinitialize with stable paths

After reset, state is `reset` and environment loading fails until explicit init.
Saved `env.sh` also rejects that state. Run the usual initialization with the
same worktree, installation, preset and state-home:

```sh
cub-workenv init --worktree /path/to/source \
  --install /existing/dedicated/install --preset debug_gcc
# Then reload direnv or source the newly generated env.sh.
```

Initialization starts numeric allocation at the requested pool beginning
(default ports 41000–41999 and SHM keys 0x62000000–0x6200ffff), skipping other
assignments and OS occupancy. After a full reset, reinitialization order determines
who receives the first numbers. TMP, installation, database registry and physical
storage paths stay unchanged. The existing registry and creation receipts are
retained, even for external or reused databases. `--no-db` continues to defer
default DB creation; without it, existing testdb is inspected/reused without
opening its storage, or a missing testdb is created by the usual init behavior.

Configuration updates replace only the managed numeric settings (including
explicit per-DB master-port settings); comments and unrelated tuning remain.
Additional enabled brokers need manual resource review. `--database-registry`
and `--db-path` are rejected for this transition to preserve the retained DB
selection. The recorded Java selection is preserved. This is not an install or
preset migration. Missing TMP or damaged configuration causes failure rather than
silently replacing unique resources.

A normal repeated init on `ready` remains unchanged. If reset is interrupted
before the final allocation-registry publication, some worktrees can be marked
`reset` while their numbers remain reserved. Rerun the same reset operation to
finish; do not delete the registry or bypass the marker. A failed reinitialization
remains `preparing` with its stage and allocation for diagnosis, as before.

## Verification

`tests/reset_cases.py`, executed by `tests/test_reset.py` in private PID/proc/IPC
namespaces, tests preview byte preservation, single versus all reset, reverse-order
reallocation from the first slots, stable TMP/install/storage paths, retained
registry/comments/tuning, stale environment rejection, existing DB reuse, busy
TCP/SHM/process refusal, initializer-lock refusal, and interrupted publication.
The native utilities in these fixtures are stubs; these tests establish the
metadata/resource lifecycle, not CUBRID database-format compatibility.
