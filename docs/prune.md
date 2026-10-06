# Prune missing Git worktrees and idle allocations

```sh
cub-workenv prune --worktree /path/to/current/worktree          # preview
cub-workenv prune --worktree /path/to/current/worktree --apply  # apply
```

Prune handles stale linked worktree registrations left after their directories
were removed outside Git. These registrations otherwise appear as missing rows
in `just workenv::all`. It operates only on the specified Git repository's
registered linked worktrees. Existing directories and the main/bare worktree
are never selected. Branches are retained.

The allocation namespace defaults to the current worktree's recorded state-home,
otherwise `${XDG_STATE_HOME:-$HOME/.local/state}/cub-workenv`. Use `--state-home`
for another explicit namespace. The command does not search unrelated namespaces
or infer which Git repository owns allocations whose Git registrations were
already removed. Keep cooperating worktrees in the same allocation namespace.

For each missing registration:

- If no matching allocation exists, only stale Git metadata needs removal.
- If an allocation exists, require the allocator's deleted/inactive checks:
  unused TCP ports, absent assigned SHM keys, empty or absent TMP, no live Unix
  sockets, and no process references to its worktree/install/TMP/port.
- Locked Git worktrees, symlink/inaccessible paths, remaining TMP artifacts,
  incomplete allocation records and uncertain/live owners are retained with a
  `KEEP` reason. Reset identities can be removed after the same applicable
  path/process checks; they already have no numeric resources assigned.
- Exited zombie processes are not active owners. Their unreadable environment
  is not grounds for treating them as live; live inaccessible processes remain
  blockers.

Preview creates no state files. Apply holds the allocation lock and rechecks Git
lock/path and resource evidence before each targeted non-force `git worktree
remove` for a missing directory. It does not run a broad `git worktree prune`,
delete branches, kill processes, remove kernel IPC, or delete TMP/install/storage
paths. Available numbers can then be allocated by later initialization.

Eligible entries can succeed even if others are blocked. Any retained missing or
uncertain entry produces a nonzero exit with its reason. Repeated application is
safe when no missing registrations remain. Inspect `just workenv::all` afterward.

The numeric/identity record is released under the allocator lock before removing
Git metadata. A Git refusal restores the record before releasing that lock. An
interruption between publications can leave stale Git metadata with no allocation;
a later prune completes it. Git worktree operations and external native launches
do not participate in this lock: avoid concurrently recreating/removing the same
paths or launching their old environments during maintenance. Run in the host
PID/network/IPC namespaces used by those environments.

`tests/prune_cases.py` runs real Git, process and port fixtures under private
Linux PID/proc/IPC namespaces. It checks preview immutability, metadata-only and
allocation cleanup, preservation of live worktrees/branches/external storage,
partial success, locked/symlink paths, live owners, reset identities, zombie
handling, and allocation restoration after Git refusal. Native DB utilities are
stubs; no database compatibility claims are made.
