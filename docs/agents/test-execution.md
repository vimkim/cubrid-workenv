# Agent test execution

## Status and scope

This is the agreed usage contract for the planned `cub-workenv` CLI. The CLI and its protection have not been implemented or verified yet. These instructions govern host-side CUBRID database tests, not pure unit tests that open no database. Container tests follow the separate `cubrid-box` workflow.

## Required execution path

Agents must launch host-side database tests, database servers, and standalone database access through `cub-workenv run ...` from the intended initialized worktree. This is mandatory to participate in physical-database exclusion and use the intended worktree's runtime settings.

Planned direct-command examples:

```sh
cub-workenv run cubrid server start testdb
cub-workenv run csql -S testdb
cub-workenv run cubrid server stop testdb
cub-workenv run cubrid broker stop
```

For a test runner, place its command and arguments after `cub-workenv run`. Confirm that the runner and its child processes preserve the selected environment and participate in the required database protection; merely wrapping an arbitrary script is not proof of that behavior. Supported runner integration must be verified during implementation.

If workenv is unavailable, uninitialized, or refuses access because the database is in use, report the reason and owning worktree/process when available. Do not retry through raw binaries to bypass the refusal. Use `cub-workenv doctor` for diagnosis once the CLI exists.

## Protect other instances

Use the selected environment's instance-specific stop commands. Do not use host-wide name-based termination such as `pkill cub_server` or `pkill cub_master`, or remove another environment's sockets, shared-memory segments, or ownership records. Escalate uncertain manual recovery to the user; permission for user-managed recovery does not authorize automatic takeover.

`run` is not a container or a sandbox. It cannot make a script containing broad process-killing or global cleanup commands safe. Inspect such runners and use an appropriately contained workflow rather than treating the command prefix as complete isolation.

## Discovery by agents in CUBRID worktrees

This repository's AGENTS.md applies only within this repository. Before adopting this workflow for agents working in CUBRID source worktrees, add a pointer to this execution contract in their applicable agent guidance. Installing that cross-repository guidance and verifying runner behavior are implementation tasks, not completed effects of this document.
