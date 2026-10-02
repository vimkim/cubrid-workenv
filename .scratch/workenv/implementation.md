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
| 06 | 02, 03, 05 | Verified and integrated | `c7776ac`; review repair `f0f22b5` | [Ticket06](issues/06-doctor.md), 31 tests plus native read-only/PID/syscall proof |
| 07 | 02 | Verified and integrated; tooling topic retained | `29555b7`; tooling `74a13cf` | [Ticket07](issues/07-environment-integration.md), 34 integrated tests and native/cross-repository flow |
| 08 | 03 | Verified and integrated | `68060e0` | [Ticket08](issues/08-database-lifetime.md), real non-force Git removal and external SQL/BLOB preservation |
| 09 | 04, 06, 07, 08 | Verified and integrated | `2e470ee` | [Full source workflow and acceptance map](../../docs/evidence/ticket09-workflow.md), rebuilt native checks and bounded cleanup |

Ticket triage remains `ready-for-human` after implementation and verification; this table records actual integration separately. Acceptance evidence belongs in each ticket and its linked artifacts. Only verified integrated tickets unblock successors.

## Final review

Completed independent Standards and Spec reviews of core `60d367c...2e470ee` and companion tooling `f2aa990...74a13cf`. All findings were addressed by the responsible ticket owners and rechecked; both axes have no remaining findings. Parent verification passed all 36 CLI tests after final integration. See [final review](../../docs/evidence/final-review.md) for fixed references, findings, verification and cleanup limits. All nine tickets are ready for local-main review; main remains unchanged pending user confirmation.

## Binary evidence provenance

Tickets01/03/05 and parent integration03-05 used copied `11.5.0.2602-a0026f9`. The shared source installation changed externally during implementation: ticket08 records `11.5.0.2635-30043f4`. These are distinct evidence sets, not an unchanged binary. Each native run records its actual version. Ticket09 independently built pinned engine `30043f492` as `11.5.0.2635-30043f4` and recorded binary/JAR hashes; its native integration evidence is distinct from copied-installation runs. Existing engine develop user changes were observed and preserved.

## Personal tooling boundary

Verified companion commits are in `/home/vimkim/my-cubrid-workenv-07`, branch `impl/workenv-07`, tip `74a13cf2508e1da8c528b0c0f1723566ab8a853d`, based on `f2aa990`. Existing CUBRID worktrees link directly into the personal tooling main worktree. The candidate is tested through `MY_CUBRID`; changing that live shared main worktree would affect existing environments, so it is retained for separate explicit application rather than silently rolled out.
