# Allocation reclamation

Assignments survive stopped work environments. Only exhaustion of the configured
TCP or SysV shared-memory pool triggers inspection of recorded worktree paths.
There is no source-root traversal. The existing host allocation flock serializes
inspection, record release and reassignment with other cooperating initializers.

A record is released only when its worktree path is absent and its ports,
shared-memory keys, TMP/socket directory and discoverable process references
show no activity. Both IPv4 and IPv6 TCP bindings count as occupancy. Existing
worktrees, symlinked or inaccessible paths, remaining TMP entries (even stale
files), bound Unix sockets (including unlinked paths), and occupied IPC are kept.
No process, database, socket file, TMP directory or IPC segment is removed.

The allocator reads Linux `/proc` command lines and, for same-user processes and
foreign CUBRID/Java candidates, environment and executable/current-directory
paths. Worktree, installation and TMP paths identify a possible owner; the
CUBRID master-port environment override also counts. An inspection permission
failure keeps the allocation. Unrelated foreign daemons are excluded by command
identity. A restricted `/proc` mount or invisible PID namespace cannot establish
host-wide absence: run cooperating initialization in the same host namespace.
This is a point-in-time check, not an OS reservation against later outside use.

On exhaustion, `allocations-reclamation.json` in `--state-home` records the most
recent pass as a list of `{allocation, action, reason}` objects. The ordinary
`allocations.json` schema is unchanged. The report and stderr explain retained
owners and reclaimed records. If capacity is still insufficient, initialization
fails and names `--port-start/--port-end` and `--shm-start/--shm-end` as explicit
configuration choices. The pool never grows automatically. The preparing state
of a failed initialization remains for diagnosis and manual recovery.

Permission uncertainty can prevent reclamation on a busy multi-user host even
when a record appears stale. Resolve visibility or inspect the report manually;
absence of the source directory alone is insufficient evidence. Reclamation
does not bypass the dedicated-installation check when a caller selects an
installation still recorded for another worktree.

## Verification

`python3 -m unittest discover -s tests -v` includes a subprocess suite using
Linux `unshare` and `setpriv`. It creates a private PID/proc namespace and drops
capabilities so positive process-absence evidence and actual permission denials
are reproducible without inspecting unrelated host processes. TCP, UDS and SysV
resources are real. Nine CLI/artifact cases cover retention, delayed reclamation,
IPv6 occupancy, IPC, linked/unlinked sockets, live owners, inaccessible paths and
processes, dangling symlinks, shared-memory exhaustion and concurrent allocation.
The wrapper reports a skip if the required Linux namespace tools are unavailable.

The fixture executables write native-shaped database registry output only; this
suite proves allocator behavior, not CUBRID database creation or broker behavior.
Ticket 05's separate engine evidence establishes the emitted broker IPC settings.
See [recorded checks](../tests/evidence/ticket04/README.md).
