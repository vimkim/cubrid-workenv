# Numeric reset and complete isolation reports

Status: implemented-pending-review
Work item: 277

User decisions: expose all managed host isolation settings; add single-worktree
`reset` and namespace-wide `reset-all`; release shared numeric resources while
preserving unique paths, databases and logs; require explicit reinitialization.
Implement commands without applying a reset to real user environments.

Behavior and verification contract: [reset workflow](../../../docs/reset.md).
Companion reports in my-cubrid must name the exact environment variables,
master/PL socket and info paths, configuration values and DB storage registrations.
Saved/expected values must not be described as observed running-process state.

Verification: 38 CLI unittest entries passed, including the private-namespace
reset lifecycle suite (nine reset scenarios). Four companion report tests passed.
Live host reset-all preview refused live/uncertain process owners and preserved
allocation-registry/state SHA-256 snapshots. No live --apply was executed.
