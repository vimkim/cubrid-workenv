# cub-workenv design interview

Status: in progress; implementation requires confirmed shared understanding.
Work tracker: 249.

## Settled in round 1

- Worktree relocation and renaming are outside the supported workflow. The user has no need for them; do not design relocation support.
- Running init on an already initialized worktree warns that it is already initialized and leaves it unchanged.
- If checks suggest a problem, direct the user to cub-workenv doctor.
- The scope of doctor, exit statuses, partial initialization recovery, identity scheme, and check depth remain undecided.

## Existing tooling facts

Read-only investigation of /home/vimkim/my-cubrid found:

- Existing bin/my-cubrid-runtime init provisions settings after an installed prefix exists; DB creation is separate in bin/_cubrid_database.py.
- bin/cubrid-build-coordinator.sh invokes initialization after installation.
- stow/cubrid/.envrc selects preset-specific installations and runs full validation on entry.
- docs/direnv-latency-2026-10-01.md reports a measured median improvement from 7.235s to 2.351s through indexed collision lookup. Cheap environment loading remains a proposal; live isolation was not requalified.

These observations describe the old tool, not requirements for the new one.

## Settled in round 2

- Collision prevention is required at initialization against resources already in use. Workenv is not responsible for preventing later intrusive tools or other worktrees from taking those resources; no continuous reservation guarantee is required.
- Doctor diagnoses and explains corrective steps without modifying state.
- Interrupted initialization is reported as incomplete; preserve partial state and direct the user to doctor rather than silently retrying or deleting it.
- One environment per worktree, with one selected build preset at a time. Changing the selected installation is explicit.
- Normal first-time flow: build/install, then explicit cub-workenv init prepares settings and requested databases using installed binaries.
- Start with a fresh environment, but existing database registry entries and additional databases are not inherently invalid. An existing database may be used when its settings do not conflict with other existing, running databases.
- The user emphasizes that using a database and commands such as csql, cubrid server stop, and cubrid broker stop must avoid affecting others.

## Unresolved boundary after round 2

- Whether command-time checks are required when a collision arises after successful initialization, and whether raw CUBRID commands or workenv-mediated commands are covered.
- Which existing database inputs may be adopted; distinction between new environment preparation and existing database reuse.
- Whether resource assignments of stopped environments are excluded from allocation.

## Settled in round 3

- Protection remains initialization plus explicit diagnosis. No automatic per-command conflict guard is required for interference occurring after initialization.
- Maintain a host-local allocation registry recording which worktree owns each assignment. Avoid assignments of known initialized worktrees, including stopped ones.
- Assign resources sequentially from a pool. When exhausted, inspect registered worktree paths under ~/gh/cb for deleted worktrees and consider their allocations for reclamation.
- Reclamation safety checks and behavior when no safe allocation is available remain to be settled. A missing directory alone does not establish that its processes/resources are unused.
- Explicitly requested existing databases may be reused when compatible; preserve their files and registry entries and leave unrelated database entries untouched. Report conflicts instead of silently rewriting existing settings or ownership.
- Duplicate database names across separate environments are allowed. Check resource and storage conflicts, not name equality alone. Environment loading selects the intended master and database registry.

## New requirement: sequential physical database reuse

- Different worktrees may intentionally use the same physical database to avoid expensive creation/loading, e.g. SELECT performance comparisons between versions.
- Workenv must prevent the current worktree from starting that database while another worktree instance is running it, protecting the existing owner.
- This adds runtime enforcement specifically for physical database exclusivity; the earlier initialization-only decision continues to describe general port/socket/shared-memory interference.
- Enforcement entry points, unmanaged processes, standalone utilities, physical database identity, crash recovery, and version compatibility remain unresolved.
- A SELECT-only workload is not yet established to mean physically read-only database access.
- Pool reclamation questions Q12 and Q13 remain unanswered.

## Settled in round 4

- Reclaim a deleted worktree allocation only when resource checks establish it is unused. Skip live or uncertain resources; do not kill processes or delete databases as part of reclamation.
- If no safe pool slot is available after reclamation, fail with an allocation report and guidance for explicitly expanding the configured pool.
- The SELECT performance comparison is only an example. No read-only restriction or file-immutability promise is required for shared databases.
- When another worktree owns a running shared database, fail startup immediately, identify the database and owner, and neither wait nor stop/take over the owner.
- These settle Q12 through Q15. Shared-database enforcement coverage and lifecycle remain under investigation.

## Shared-database enforcement investigation

Read-only source inspection of /home/vimkim/gh/cb/develop found native Linux active-log fcntl exclusion in src/transaction/log_manager.c:1166 and src/storage/file_io.c:1233. Data volumes are opened earlier. Locking can be disabled; unusual stale-owner handling remains unverified. Native exclusion is useful but not yet evidence of the requested unconditional protection.

Existing personal coordinator locks are per installation, not physical database, and do not remain held by a daemon after the launch supervisor exits (cubrid-build-coordinator.sh:63,347). A cooperating workenv guard would need to cover the full lifetime of database use in both owner and borrowing worktrees. PATH wrappers do not intercept absolute-path binaries or arbitrary external launchers.

Database name alone cannot identify shared physical storage. Aliased paths and shared log/data inventory need consideration. Sequential exclusion also does not establish binary/on-disk compatibility across versions.

## Round 5 (managed-launch requirement revised below)

- Both owner and borrower must use workenv-managed launches for the shared-physical-database exclusivity guarantee. Arbitrary direct binaries are outside that guarantee.
- Ownership must span the full database server lifetime, not merely the start command.
- On-disk compatibility between versions is the user's responsibility; workenv does not convert formats or guarantee backward reopening.
- User proposes tracked allocation for finite numeric resources and worktree-derived pseudo-unique identifiers for filesystem paths.
- Clarification: CUBRID broker SysV shared memory uses numeric keys, not filesystem paths; it remains in tracked allocation. Socket and temporary-directory paths can use a short worktree-path digest, with explicit collision handling and socket-path length constraints.

## Current shared-database agreement after Socratic clarification

This agreement supersedes earlier uncertainty about standalone coverage and prescribing an additional ownership lock before validation.

- Prevent workenv-mediated concurrent opening of one physical database from different worktrees. This includes server launches and standalone opening such as csql -S.
- Ordinary client connections to an already running database server remain allowed.
- Explain rejection with the owning worktree and process information.
- Earlier blanket participation from first use is superseded: first validate native exclusion, then determine whether additional guarding is necessary.
- The lifetime of the launching AI agent is irrelevant. Protection must cover database use, not just the start command.
- Manual recovery of residual ownership state after abnormal termination is acceptable. Automatic crash cleanup is not a requirement.
- Neither read-only database access nor cross-version on-disk compatibility is promised.
- The enforcement mechanism is undecided: inspect code and experiment before choosing native locking, additional flock coordination, or another implementation. The requirement is exclusion and useful attribution, not redundant locking machinery.
- Concurrent native server starts and server-plus-standalone access have not been experimentally verified. User statements that native rejection is absent were explicitly clarified as expectations, not observations.

## Pending verification and design

- Experimentally check competing server starts and standalone access against a running server using disposable database storage; verify the existing owner remains healthy and subsequent opening works after release.
- Determine how owner attribution and physical database identity will work, and document the manual recovery procedure.
- Finish detailed CLI and environment integration, and check/exit-status behavior; initialization defaults are settled below.


## Initialization defaults

- cub-workenv init prepares a default testdb.
- cub-workenv init --no-db prepares the environment and resource settings without creating a database.
- If testdb already exists, preserve and reuse it when possible rather than recreating it.
- A later cub-workenv adopt command is a possible fallback for existing databases, not yet a committed first-version requirement.
- If safe reuse of existing testdb cannot be established, init fails; it does not report successful environment-only initialization. Preserve existing DB files.
- After environment-only initialization, a separate cub-workenv create-db command creates a database. Its arguments/defaults remain to be specified.

## Database lifetime by storage location

- A database stored inside its worktree is worktree-managed and is deleted with that worktree, including normal post-rebase/fast-forward-merge cleanup.
- A database stored outside the worktree (for example under ~/tmp or another shared location) is preserved when the worktree is removed.
- The user will back up or place databases intended for sharing in an external location. Workenv does not automatically relocate or back them up.
- The user explicitly confirmed that storage location determines lifetime.
- Implementation must account for database data/log/LOB paths and references without accidentally deleting externally stored data; exact validation and cleanup mechanics remain to be verified.

## First-version service scope

- Configure isolation for ordinary CUBRID servers, brokers, and PL servers.
- CUBRID Manager is excluded.
- HA is not included in the first version; it may be considered later.

## Invocation and environment loading

- Ordinary cubrid/csql commands may run directly in the prepared worktree environment. Explicit cub-workenv run is a candidate for shared-physical-database protection or diagnostics, pending native exclusion experiments; it is not mandatory for all operations.
- Do not interpose cubrid/csql through a special PATH wrapper directory in the first version. Existing raw commands retain their behavior and are outside workenv-mediated exclusivity.
- Ordinary client connections can use csql directly with the prepared environment.
- On worktree entry, direnv loads prepared environment variables and the installed binaries' PATH. It does not initialize, build, create databases, or run full validation.
- Behavior when no prepared environment exists remains to be settled.

## Agent execution guidance

- The user corrected the blanket run requirement: use the initialized worktree environment for ordinary host tests without requiring a wrapper.
- Updated AGENTS.md and docs/agents/test-execution.md accordingly. Shared-storage exclusion and owner attribution remain goals; whether run is needed depends on native locking experiments.
- Tests are not automatically sandboxed by the command prefix; child-process/runner integration must be validated. Existing container test workflows remain separate.
- Source worktree agents will need a pointer in their applicable guidance; no external repository instructions have been changed.

## Latest correction: initialization versus runtime guarding

- The blanket requirement that every host database test use cub-workenv run is withdrawn.
- Separate physical databases use their prepared worktree settings directly. Initialization is the resource-conflict prevention boundary, with explicit diagnosis for later interference.
- Shared physical storage still requires exclusive opening. Test native server/server and server/standalone exclusion before choosing additional locking or owner diagnostics.
- Earlier managed-launch assumptions are conditional on that implementation decision; they are not a mandate to wrap every test.
