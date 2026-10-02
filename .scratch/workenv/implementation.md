# Implementation integration record

Work item: 256
Integration branch: `impl/workenv-integration`
Integration worktree: `/home/vimkim/gh/cubrid-workenv-integration`
Starting main: `60d367cd27592b1331b04339add8acc36c321624`

The approved [specification](spec.md) and [tickets](tickets.md) govern implementation. Each ticket receives a new agent with no inherited conversation and its own sibling worktree. Prerequisites must be verified and present on the integration branch before dispatch. Local main integration awaits user review; remote publication is outside scope.

| Ticket | Prerequisites | Implementation / integration | Accepted commit | Evidence |
| --- | --- | --- | --- | --- |
| 01 | — | Verified and integrated | `1e50074` | [Ticket01](issues/01-initialize-and-connect.md), 6 CLI tests and real server/client flow |
| 02 | 01 | Verified and integrated | `3b73e0f` | [Ticket02](issues/02-initialization-state.md), 13 CLI/state tests |
| 03 | 01 | Verified and integrated | `61184cb` | [Ticket03](issues/03-database-selection.md), 21 integrated tests, combined native evidence in tests/evidence/integration03-05 |
| 04 | 02 | Verified and integrated | `46e4904` | [Ticket04](issues/04-allocation-reclamation.md), 22 discovery tests including 9 namespace cases |
| 05 | 01 | Verified and integrated | `9878abc` | [Ticket05](issues/05-multiple-instances.md), native JDBC/PL/stop proof, 16 integrated tests |
| 06 | 02, 03, 05 | Verified and integrated | `c7776ac` | [Ticket06](issues/06-doctor.md), 31 tests plus native read-only/PID/syscall proof |
| 07 | 02 | Verified and integrated; tooling topic retained | `29555b7`; tooling `aea8078` | [Ticket07](issues/07-environment-integration.md), 34 integrated tests and native/cross-repository flow |
| 08 | 03 | Verified and integrated | `68060e0` | [Ticket08](issues/08-database-lifetime.md), real non-force Git removal and external SQL/BLOB preservation |
| 09 | 04, 06, 07, 08 | In progress | — | — |

Ticket triage remains `ready-for-human` after implementation and verification; this table records actual integration separately. Acceptance evidence belongs in each ticket and its linked artifacts. Only verified integrated tickets unblock successors.

## Final review

Pending Standards and Spec review of the integrated diff against the starting main commit, plus the separate ticket07 tooling diff. Findings return to the responsible ticket agent. Actual CUBRID execution evidence cannot be replaced by mocked commands.

## Binary evidence provenance

Tickets01/03/05 and parent integration03-05 used copied `11.5.0.2602-a0026f9`. The shared source installation changed externally during implementation: ticket08 records `11.5.0.2635-30043f4`. These are distinct evidence sets, not an unchanged binary. Each native run records its actual version; final workflow must identify its own isolated build. Existing engine develop user changes were observed and preserved.

## Personal tooling boundary

Verified companion commits are in `/home/vimkim/my-cubrid-workenv-07`, branch `impl/workenv-07`, tip `aea80789165951be4602d042476c88bd5105e049`, based on `f2aa990`. Existing CUBRID worktrees link directly into the personal tooling main worktree. The candidate is tested through `MY_CUBRID`; changing that live shared main worktree would affect existing environments, so it is retained for separate explicit application rather than silently rolled out.
