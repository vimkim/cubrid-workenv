# Agent test execution

## Status and scope

The CLI implements explicit preparation, environment loading and read-only diagnosis. Use [the workflow](../workflow.md) for preparation, failed-init recovery and removal; use [acceptance evidence](../evidence/ticket09-workflow.md) for tested builds and limits. Container tests follow the separate `cubrid-box` workflow.

## Separate physical databases

After initialization assigns nonconflicting resources and direnv loads the intended worktree environment, ordinary `cubrid` and `csql` commands may run directly. Agents do not have to prefix every host database test with `cub-workenv run`.

Use the selected worktree's binaries, configuration, database registry, and resource assignments. Test runners must preserve that selection in child processes. Initialization avoids known resource conflicts at that time; it does not continuously defend against later interference by external tools. Diagnose suspected problems explicitly, using `cub-workenv doctor`.

## Shared physical database storage

Different worktrees may intentionally reuse one physical database, but concurrent independent opening must be prevented. This concerns both a second server and standalone access such as `csql -S`. An ordinary `csql` client connecting to an existing server is allowed and does not need another exclusive database lock.

Native normal-path rejection of a competing server and standalone opener, existing-server health and sequential reuse have been checked on the builds identified in the [acceptance map](../evidence/ticket09-workflow.md). The original [experiment](../../experiments/native-db-exclusion/README.md) remains a separate historical evidence set. Abnormal termination, changed locking settings, network filesystems and cross-version compatibility remain unverified.

Preserve native owner PID, user, host and physical-path errors. `doctor --native-error-file PATH` can supplement them with a worktree only when current process, native lock and registration evidence agree. The CLI does not add a DB lease or `run` wrapper. Manual recovery needs explicit ownership checks; version compatibility remains the user's responsibility.

## Protect other instances

Use the selected environment's instance-specific stop commands. Do not use host-wide name-based termination such as `pkill cub_server` or `pkill cub_master`, or remove another environment's sockets, shared-memory segments, or ownership records. Escalate uncertain manual recovery to the user; permission for user-managed recovery does not authorize automatic takeover.

Neither initialization nor a command wrapper is a container or sandbox. Inspect runners that perform broad process termination or global cleanup rather than assuming a command prefix provides complete isolation.

## Discovery by agents in CUBRID worktrees

This repository's AGENTS.md applies only within this repository. The companion personal-tooling topic includes source-worktree guidance. Selecting or applying that topic remains separate from this CLI's local integration; existing source trees have not been globally migrated. Confirm which guidance and shared symlinks a source tree actually uses.
