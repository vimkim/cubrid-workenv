# Explain why cubrid-workenv exists

Status: resolved

## Requested outcome

The README must explain the original problem, its consequences, its causes,
available approaches, and how this tool solves it. Preserve the existing
visual design, examples, evidence scope, and native-command workflow.

The approved follow-up also requests explicit limitations, the rigor of an
academic technical README, and additional improvement proposals. Merge/push
approval includes this requested documentation expansion.

## Evidence

- `.scratch/workenv/spec.md`, Problem Statement: cross-worktree master, broker,
  and PL resource overlap; wrong DB connections or shutdown interference;
  directory-entry preparation/full validation blurs lifecycle boundaries.
- `docs/requirements.md`: independent parallel work without waiting for long
  tests; host configuration and container execution have separate scopes.
- `docs/handoff-instance-isolation.md`: historical source findings on master
  selection, registry/environment routing, broker SHM keys, socket paths, and
  installation-local PL files. Treat this as source analysis, not a new native
  failure reproduction.
- `.scratch/workenv/design-interview.md`, Existing tooling facts: the old shared
  loader ran full validation on entry. The referenced personal latency report
  identifies repeated path comparisons, hashing, and host inspection. Do not
  add timing claims or present its intermediate proposal as current behavior.
- `cubrid_workenv/runtime.py`, `allocation.py`, `loading.py`, and the existing
  workflow/evidence reports establish the current preparation/loading boundary.

## Implementation

Add a concrete A-to-B worktree scenario and the impact on test confidence and
parallel work. Explain all relevant resource classes and inherited selection.
Compare serial execution, manual host configuration, and container workflows
as possible approaches, without claiming to benchmark them. Replace the
existing mechanism section with an explanation tied to the causes and place
it before setup. Keep all critical instructions in Markdown.

No runtime changes or additional native-engine experiments are needed.

For the limitations expansion, organize verification around observations linked
to recorded evidence. Separate implementation scope from unverified scenarios
and future proposals. State the absent engine ctest coverage, stubbed CLI fixture
boundary, diagnostic visibility limits, cooperative allocation assumption,
native-locking prerequisites, finite resource/path constraints, manual recovery,
and limited compatibility/performance evidence. Proposed compatibility, latency,
failure-injection, and structured-diagnosis work must not be presented as shipped.

## Validation

Check local links/anchors, shell syntax, SVG references, and the full diff.
Inspect desktop/mobile previews on light/dark backgrounds, including the added
comparison table and the transition to first use. Commit only this record and
the README in the task worktree for review.

## Result

- Added the A-to-B connection/shutdown scenario, consequences for trustworthy
  tests and parallel work, resource/environment causes, and historical loader
  validation cost. Linked original repository investigation/design evidence.
- Compared serial host runs, manual host configuration, and containers; tied
  the selected host approach to four preparation/allocation/loading/diagnosis
  steps. Replaced the older mechanism section to avoid duplication.
- Added an observation/evidence table, explicit validity and operational limits,
  and four clearly labelled proposals. Distinguished native runs from stubbed
  CLI fixtures and absent engine ctest coverage; retained performance caveats.
- README image/SVG audit passed; 38 local links/anchors resolved; all five
  shell snippets parsed. Desktop/mobile light/dark previews inspected with
  no page overflow or missing image.
- Artwork, commands, runtime implementation, and existing evidence unchanged.
  No native-engine tests rerun for this prose-only follow-up.
