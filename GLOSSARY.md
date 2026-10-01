# CUBRID Work Environment

The host-side environment prepared for a CUBRID source worktree.

## Language

**Work environment**:
The databases and runtime settings associated with a CUBRID source worktree for direct execution on the host, using one selected build preset at a time.
_Avoid_: Container, runtime engine

**Initialization**:
The explicit first-time preparation of a work environment. Repeating initialization on an initialized worktree reports that state without changing the environment.
_Avoid_: Repair, reset

**Diagnosis**:
Inspection of a work environment that reports problems and corrective steps without changing it.
_Avoid_: Automatic repair

**Allocation**:
A recorded assignment of host resources to a work environment, retained while that environment is stopped.
_Avoid_: Exclusive operating-system reservation

**Shared physical database**:
One stored database intentionally reused by multiple work environments, with at most one work environment running it at a time.
_Avoid_: Replicated database, concurrently shared database

**Worktree-managed database**:
A database stored inside a worktree whose lifetime ends when that worktree is deleted.
_Avoid_: Shared-lifetime database

**External database**:
A database stored outside the worktree and preserved when that worktree is deleted. It may be reused by other work environments.
_Avoid_: Automatically disposable database
