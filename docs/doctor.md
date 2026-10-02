# Read-only diagnosis

`cub-workenv doctor --worktree /path/to/source` reports initialization state,
selected installation/preset, configuration drift, registration paths, recorded
allocation conflicts and live Linux TCP/Unix-socket/SysV shared-memory use.
It never runs CUBRID, opens a DB volume, binds a resource, reclaims allocations,
removes files or signals a process. The ordinary repeated `init` boundary remains
lightweight; these host scans happen only in doctor.

Optional `--install /expected/install --preset expected` compares the requested
selection with the saved selection. A mismatch requires an explicit manual
transition; doctor does not select another preset or convert database formats.

Pass `--native-error-file /path/to/captured-error.txt` to retain existing native
output, including user, host, PID and physical path. Doctor never reproduces an
error by attempting another DB open. It supplements a native error with a
worktree only when the local hostname/user, current active-log inode lock,
process environment and an allocation's DB registration all match. Historical
or inaccessible owner evidence is printed as unconfirmed. An existing valid
native lock is informational: sequential shared DB use is permitted.

For resource ownership, doctor joins actual socket descriptors or shared-memory
mappings to PIDs and matches all of CUBRID, CUBRID_CONF_FILE, CUBRID_DATABASES,
CUBRID_TMP and CUBRID_CUBRID_PORT_ID to the allocation. A recorded allocation
alone is not proof of the current resource owner. Stale socket paths and occupied
resources without a confirmed owner require manual inspection. No process scan
is an atomic snapshot; permissions, PID exits/reuse and other namespaces limit
inspection. The inaccessible PID count is printed on every full scan.

Local file-backed DB registrations are checked with filesystem metadata only.
Additional DB names and the same name in other environments are allowed.
Legacy four-field registrations without a LOB field are valid: doctor checks
the data and active log and reports LOB as not registered. Native source
`src/base/databases_file.c:449–462` and `:548–561` explicitly preserves this
backward compatibility. Initial `testdb` reuse still requires the documented
five-field local file-backed registration; this diagnostic support does not
broaden initialization's reuse contract. Data,
active-log and LOB paths may be external and are never removed. Remote/non-file
LOB registrations are retained and explicitly marked outside physical storage
verification. These checks do not establish file-format compatibility, complete
volume-chain integrity or a usable database; only native operations can do that.

The generated broker section is checked against its allocation. Extra enabled
broker sections are reported as unallocated; their port/key ownership must be
reviewed explicitly. Ordinary unrelated settings and DB-specific sections are
accepted. Disabling PL Unix sockets is reported because the allocated PL socket
isolation no longer describes that configuration.

## Known native locking prerequisite

CUBRID's hidden `file_lock` setting defaults to true. Explicit false values in
any inspected `cubrid.conf` section, the current selected environment, or a live
confirmed-instance process's `CUBRID_FILE_LOCK` are errors. Correct the relevant
configuration/launch environment before independently opening shared storage.
Changing a file does not retroactively change a running process's settings.

Source evidence, inspected at CUBRID commit
`30043f492225c8350aa15455dc329c87227b5fdf`:

- `src/base/system_parameter.c:135` names `PRM_ID_IO_LOCKF_ENABLE` as `file_lock`.
- `src/base/system_parameter.c:1162` defines the hidden server boolean with
  default true.
- `src/storage/file_io.c:1192` returns `FILEIO_LOCKF` before acquiring the native
  lock when that boolean is false.
- `src/base/system_parameter.c:7358` (`prm_check_environment`) uppercases each
  parameter name and calls `envvar_get`, applying a provided environment value.
  `src/base/environment_variable.c` prefixes such names with `CUBRID_`.

This is source evidence for a known hidden switch, not a claim that the public
manual documents it. Doctor does not audit special utility modes, engine
internals, alternate config includes, runtime-only SQL changes, network
filesystems or every possible way to bypass native locking.

## Manual next steps

- Uninitialized: build/install the intended preset, then explicitly run init.
- Incomplete: inspect the recorded stage, native log, settings and allocation;
  establish that the initializer has stopped, preserve DBs, and decide recovery.
- Missing/drifted artifacts: compare the reported setting with saved allocation
  and selected installation; correct the intended artifacts deliberately.
- Missing storage: inspect the registry and the actual storage location; never
  recreate or delete a registered DB merely to make diagnosis pass.
- Resource conflict/unconfirmed owner: inspect the named resource/PID and owner
  on the reported host. Stop only an instance you have positively identified and
  are authorized to stop. Doctor performs no takeover or automatic repair.

## Evidence

[Native run](../tests/evidence/ticket06/native/results.json) uses two independent
copies of the installed `11.5.0.2635-30043f4` build with Java 8. It records matching
bin/lib hashes for both copies, native busy output, successful doctor output,
strace logs, before/after configuration/registry/allocation/DB hashes, unchanged
live PIDs, successful SQL health after diagnosis, and exact cleanup results.
A succeeds. A rejected standalone attempt can leave B's PL socket file behind:
doctor B then correctly fails with a stale/unconfirmed-path diagnosis, preserving
that file and the full native owner message. The harness accepts that specific
observed diagnostic and still requires unchanged artifacts/PIDs and healthy A.
The source installation had advanced since the earlier 01/03/05 experiments;
this report deliberately identifies the actual copied version.

`tests/real_doctor.py --install PATH --java-home PATH --output NEW_DIRECTORY`
reproduces that run. An initial harness attempt used subprocess pipes inherited
by native daemons and timed out waiting for pipe EOF; the corrected harness uses
output files. All of that attempt's owned processes and disposable files were
cleaned. The timeout did not establish a CUBRID startup failure.
