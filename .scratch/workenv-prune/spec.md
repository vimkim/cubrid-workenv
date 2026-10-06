# Workenv prune

Status: implemented-pending-review
Work item: 278

Add a command to remove stale, missing Git worktree registrations reported by
workenv::all and reclaim their unused resource assignments. Preserve existing
worktrees, branches and all data/install/TMP paths. Keep live, locked or uncertain
entries with an explanation. Preview/apply behavior follows the reset commands.

The detailed contract and verification are in [prune](../../../docs/prune.md).
The companion my-cubrid module exposes `workenv::prune` and `prune-apply`.
No live pruning is performed during implementation; the live preview identifies
four metadata-only stale registrations in the CUBRID repository.

Verification: 39 CLI unittest entries passed, including eight private-namespace
prune scenarios. Companion Just smoke verified root selection from a subdirectory,
CUB_WORKENV_CLI routing, and preview/apply argument differences. Live CUBRID
preview selected exactly the four reported missing registrations; none had a
matching allocation. No live prune was applied during implementation.
