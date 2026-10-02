# Ticket 04 evidence

2026-10-02, Linux host, Python unittest via public `bin/cub-workenv` and generated
allocation artifacts. Base: `75f9a5a18d4a669c54c8093c63077e3074cdb378`.

- [Discovery](discovery.txt): 17 tests passed, including the nested suite below.
- [Reclamation cases](reclamation.txt): nine cases passed in a private PID/proc
  namespace with capabilities dropped. No network or IPC namespace is used;
  ports, sockets, and SysV shared-memory objects are actual bounded resources.
- Initial RED: deleted inactive worktree test failed with the former `Port pool
  47000-47001 exhausted` error. GREEN after locked reclamation implementation.
- Second RED: IPv6-only listener still allowed reclamation (`returncode == 0`).
  GREEN after IPv4 plus IPv6 port probing.
- Ordinary host positive reclamation initially failed closed on unreadable
  `/proc/4938/environ`, a foreign UID 11161 `cub_server xrn`, and same-user PAM
  infrastructure. No host process was changed. Private process visibility makes
  absence provable; the nondumpable-process test separately verifies refusal
  under actual permission uncertainty.

Fixtures create owned temporary installations, registry-shaped output, and
zero-length fixture database files; no claim of native DB engine behavior is
made. Test cleanup removes only fixture directories, exact child processes and
the test's own shm id. Product reclamation only updates allocation metadata.

The host can have inaccessible processes; strict checks may therefore retain
apparently stale records. External process/resource creation can race a snapshot,
as with any allocation check that is not a lasting operating-system reservation.
