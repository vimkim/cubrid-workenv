# Database selection

`cub-workenv init --no-db --install /selected/install --preset debug_gcc`
prepares the environment without creating or opening a DB. Later run
`cub-workenv create-db example --path /external/example` (or omit `--path`
for `.cub-workenv/db/example`). The location must not already exist and must
not contain whitespace. All data/log/LOB directories stay beneath it.
Names start with a letter and contain up to 63 letters, digits or underscores.
Names must also keep the allocated PL socket path below 108 bytes.
The initial DB sizes remain 64 MB data and 32 MB log, with `en_US.utf8` locale.

Default init creates `testdb`; `--db-path /external/testdb` changes its new
storage location. An existing `testdb` registration is reused without
opening its volumes. Registrations are discovered at `databases.txt` or
`databases/databases.txt` under the worktree. Use
`--database-registry /path/to/databases.txt` to select an explicit registry,
including one pointing to a shared external DB. Multiple discovered
registries require explicit selection. The selected registry is copied,
not shared as a writable configuration file. Other instance settings are
never imported. Unknown preexisting `.cub-workenv` artifacts still require
inspection rather than automatic adoption.

Reuse currently accepts a five-field local registration: name, absolute
data directory, `localhost`, absolute log directory, and `file:` absolute
LOB directory. Directories, the primary volume and active log must exist.
This checks registration and storage shape, not DB health or file-format
compatibility. Remote registrations, absent files, ambiguous registrations,
and storage overrides of registered `testdb` fail while preserving storage.
`--no-db` preserves registry bytes without validating/opening its DBs.

Additional creation refuses an already registered name before touching
storage, and refuses any existing target directory. Native `createdb`
uses a temporary registry because it otherwise rewrites unrelated rows and
comments. Only its new registration is appended to the original registry;
original bytes and user settings remain intact. Cooperating initialization
and creation commands use the same environment preparation lock. This is
not a runtime DB lease. Concurrent manual registry edits require care;
detected edits cause failure and leave the newly created storage for
inspection. Failed creation keeps its storage and `createdb-NAME.log`;
it does not retry, overwrite or delete it.

Ordinary `cubrid` and `csql` commands retain native diagnostics. Shared
physical DBs must be opened sequentially. The real acceptance script
`tests/real_database.py` prepares two environments through the CLI using
separate installation copies and ports 44000–44999. Its retained evidence
is in `tests/evidence/ticket03/`: initialization while A is running,
second-server and standalone rejection with user/host/PID/path, A's
continued writes, B's subsequent reads, duplicate refusal, and preservation
of additional registry rows and settings during further creation.

The evidence covers the recorded Linux build and normal shutdown path.
It does not establish cross-version compatibility, physical read-only
access, crash recovery, network filesystems, disabled locking, or all
utilities. Temporary runtime and owned processes are removed after the
experiment; binary hashes and command results remain in `results.json`.

Before removing a source worktree, follow the [database lifetime procedure](database-lifetime.md).
It requires explicit artifact ownership, physical storage inspection, normal
shutdown and non-force Git removal, and preserves external/symlink-target DBs.

## Creation provenance for personal lifecycle tooling

Successful new creation now publishes `.cub-workenv/created-NAME.json` with its
exact registration, storage root and primary-volume device/inode. Default init
and additional `create-db` use the same path. Reuse never publishes provenance
for preexisting storage. A retained receipt blocks later reuse of that name
until the old physical storage and metadata have been explicitly inspected.
The CLI still offers creation only; a receipt is not permission to delete an
external DB, a runtime lease or an additional environment-selection authority.

The companion personal helper accepts automatic deletion only with matching
provenance and wholly internal physical storage. Older, reused, external, mixed
or uncertain DBs need manual review. After manual native deletion, preserve the
old receipt with the reviewed evidence before creating new storage under that
name; do not remove it merely to bypass a preservation error.
