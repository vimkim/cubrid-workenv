# Database lifetime and worktree removal

A worktree-managed DB ends with its source worktree. An external DB survives
that worktree, including when its registry or a symlink to its storage is
inside the worktree. `cub-workenv` has no global remove command. Use this
reviewed, manual procedure after the work is committed and removal is authorized.

## Establish the deletion boundary

Record the canonical worktree path, selected installation, `state.json`,
`env.sh`, all registry entries, and allocation before removing anything.
For each DB inspect its actual data volumes, active/archive logs and LOB
storage, following links **for inspection only**. A registry's three directories
are a starting point: additional volumes, manually changed paths, mounted
storage and utilities' outputs require inspection too. An internal directory
name, an internal registry entry, or a Git ignore pattern is not proof of ownership.

| Storage evidence | Decision |
| --- | --- |
| All physical data/log/LOB storage is internal, known newly generated, and disposable | Include only the verified owned artifacts in the removal list |
| Physical storage is external, including through an internal symlink | Preserve all targets; only an explicitly owned reference may be unlinked |
| Storage is mixed internal/external | Stop and report each location; preserve both portions until the user settles the DB's future |
| Missing/inaccessible paths, unknown files, extra volumes, bind mounts, hard links, or unclear ownership | Stop and report uncertainty; do not infer disposable status |

New CLI-created DBs group `data/`, `log/` and `lob/` beneath their selected
location. This establishes location, not permission to delete everything later
placed there. Existing/reused DBs and manually edited registries need their own
ownership review. Never use native `deletedb` on an external or mixed DB as a
way to remove its local registration.

## Stop, inventory, then remove exact owned artifacts

1. Load the worktree's prepared environment in a dedicated shell. Inspect the
   selected `CUBRID`, `CUBRID_CONF_FILE`, `CUBRID_DATABASES`, `CUBRID_TMP` and
   port against the saved state. Run ordinary `cubrid server stop DBNAME` for
   each running DB of this environment and stop its broker/service as applicable.
   Check that its servers, broker, PL and master have exited. Any failure or
   uncertain process ownership stops the cleanup. Do not use host-wide `pkill`
   or remove sockets/IPC to make a running instance appear stopped.
2. Inspect both ordinary and ignored files:

   ```sh
   git -C "$worktree" status --short --untracked-files=all
   git -C "$worktree" status --short --ignored
   git -C "$worktree" diff
   git -C "$worktree" diff --cached
   ```

   Inventory the filesystem as well; Git may collapse directory entries. Preserve
   user edits, user configuration, unknown files and valuable evidence. A clean
   Git status does not make ignored files disposable. Resolve user changes by
   an authorized commit or user-directed preservation, never forced removal,
   `git clean`, resetting them, or adding ignore rules to conceal them.
3. Write an explicit reviewed removal list for the artifacts created by this
   environment. Retain registry/path evidence outside the departing worktree.
   The list can contain known generated `.cub-workenv` configuration, state,
   creation logs, local registry and the fully internal disposable DB's files.
   It must exclude external targets, unknown additions and user-modified files.
   Known owned symlinks are unlinked as links; never traverse them while deleting.
   Recheck the inventory immediately before deletion and stop if anything changed.
   A post-hoc manifest of an arbitrary user's directory does **not** prove ownership.
4. Unlink those exact owned files and links; remove their now-empty directories
   with `rmdir`. Avoid recursive deletion of `.cub-workenv` or storage parents.
   Handle short TMP paths and any installation separately with the same ownership
   and stopped-process checks; an installation may outlive the source worktree.
   Never remove a selected installation merely because it was selected here.
5. From outside the departing worktree, use non-force Git removal:

   ```sh
   git -C "$repository" worktree remove "$worktree"
   ```

   If Git refuses, inspect and preserve what remains. Do not add `--force`.
   Ignored files need the earlier explicit inspection because Git may remove
   them without refusing. Keep the task branch until its commits are verified
   included in the destination; branch deletion follows the user's normal workflow.
6. Compare the external storage inventory before/after removal. With all prior
   openers stopped, load another compatible prepared environment whose registry
   points at the same external physical storage. Start it normally and query a
   previously committed sentinel, including any LOB payload, then stop it normally.
   This is a verification step, not an automatic backup, move, adoption or repair.

Worktree removal and allocation reclamation are separate events. Do not edit
the host allocation registry as part of this procedure. Ticket 04's allocation
policy considers deleted worktrees on pool exhaustion and skips live or uncertain
resources. A missing worktree path alone is insufficient evidence for reclamation.

## Reproducible native proof

```sh
python3 tests/real_database_lifetime.py \
  --install /path/to/compatible/cubrid/install \
  --java-home /path/to/compatible/java8 \
  --output /tmp/cwe-lifetime-evidence-new
```

The script uses a fresh disposable Git repository with two real linked worktrees,
two installation copies and a private allocation registry, with ports 48000–48999.
It never removes a user's worktree or external DB. Its exact-file cleanup helper
is a **fixture-only reproduction**: the script owns the initially empty environment,
all native writes happen under its control, and it approves a manifest only after
normal shutdown. Do not apply that helper to an arbitrary existing worktree.

The proof covers a real internal DB and real external DB, each with data, log and
LOB files. It records canonical paths, an internal symlink to external storage,
a synthetic mixed-path registration that must be reviewed, and blocked cleanup
for unknown ignored files inside and outside the generated directory, a modified
generated config and a tracked source edit.
Test-injected unknown/config changes are undone only by their creator; the source
edit is committed and retained on a branch before worktree removal. External
files must remain byte-identical through removal, then a second environment must
read the original SQL/LOB sentinel. Allocation registry files must remain unchanged.

[Recorded results](../tests/evidence/ticket08/results.json) and
[post-removal sentinel](../tests/evidence/ticket08/external-sentinel-after-removal.txt)
contain commands, return codes, hashes, paths and verdicts. The mixed registration
is deliberately not opened as a database; it demonstrates the procedure's
preserve-and-review classification, not mixed-DB runtime support. This proof does
not test abnormal shutdown, arbitrary volume extensions, network filesystems,
bind mounts, cross-version compatibility, concurrent user file edits or allocation
reclamation. It does not provide a race-safe general-purpose deletion utility.

The script retains its unique `/tmp/cwe-life-*` fixture for inspection and reports
remaining fixture-prefix processes. Preserve failures for diagnosis. After reviewing
a successful run and verifying no owned process remains, the fixture's creator may
remove the remaining disposable files, installation copies and private Git repository;
this separate test-harness cleanup does not claim external production DB disposal.

The retained [initial failed attempt](../tests/evidence/ticket08-registry-format-trial/results.json)
failed in the proof script's registry parser before starting any DB server: native
registry fields use tabs. Parsing fields by whitespace fixed the harness; it did
not require a production change. The final recorded run uses that corrected parser.

After review, the creator removed all three recorded fixture roots and their five
short TMP directories. [Cleanup evidence](../tests/evidence/ticket08-cleanup.json)
records no owned processes, no matching IPC or registered Unix sockets, and free
ports 48000–48003 before removal. Remaining linked fixture worktrees were removed
without force after exact owned-file cleanup. The earlier successful run's
[extra evidence](../tests/evidence/ticket08-first-pass/results.json) was preserved
first. This later disposal concerns only the test harness's own external DBs; the
recorded preservation and sentinel checks occurred before that separate cleanup.
