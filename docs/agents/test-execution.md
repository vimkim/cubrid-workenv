# Agent test execution

## Status and scope

The `cub-workenv` CLI is planned, not implemented. These instructions describe the agreed execution model; they do not claim that initialization or runtime protection has already been verified. Container tests follow the separate `cubrid-box` workflow.

## Separate physical databases

After initialization assigns nonconflicting resources and direnv loads the intended worktree environment, ordinary `cubrid` and `csql` commands may run directly. Agents do not have to prefix every host database test with `cub-workenv run`.

Use the selected worktree's binaries, configuration, database registry, and resource assignments. Test runners must preserve that selection in child processes. Initialization avoids known resource conflicts at that time; it does not continuously defend against later interference by external tools. Diagnose suspected problems explicitly, using `cub-workenv doctor` once available.

## Shared physical database storage

Different worktrees may intentionally reuse one physical database, but concurrent independent opening must be prevented. This concerns both a second server and standalone access such as `csql -S`. An ordinary `csql` client connecting to an existing server is allowed and does not need another exclusive database lock.

First verify native CUBRID behavior using a disposable database: competing server starts and standalone access while a server is running must reject the second opener without disturbing the owner. No such runtime verification has been completed yet.

Use those results to decide whether `cub-workenv run` is needed for additional exclusion, useful owner diagnostics, or both. It is a candidate interface, not an established requirement for all tests or all database launches. If provided, it should be explicit rather than transparently replacing `cubrid` or `csql` through PATH wrappers.

Report the owning worktree and process when possible. Any additional protection must last for database use, not merely the launch command. Manual recovery after abnormal termination is acceptable; database format compatibility between versions remains the user's responsibility.

## Protect other instances

Use the selected environment's instance-specific stop commands. Do not use host-wide name-based termination such as `pkill cub_server` or `pkill cub_master`, or remove another environment's sockets, shared-memory segments, or ownership records. Escalate uncertain manual recovery to the user; permission for user-managed recovery does not authorize automatic takeover.

Neither initialization nor a command wrapper is a container or sandbox. Inspect runners that perform broad process termination or global cleanup rather than assuming a command prefix provides complete isolation.

## Discovery by agents in CUBRID worktrees

This repository's AGENTS.md applies only within this repository. When this workflow is implemented, link the verified execution guidance from the instructions applicable to CUBRID source worktrees. No external repository guidance has been changed by this document.
