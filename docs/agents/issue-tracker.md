# Issue tracker: Local Markdown

Keep specs and issues in version-controlled Markdown:

- Spec: `.scratch/<feature>/spec.md`
- Tickets: `.scratch/<feature>/issues/<NN>-<slug>.md`, numbered from 01
- Record triage state as `Status:` using triage-labels.md.
- Append discussion under `## Comments`.
- Record dependencies as `Blocked by:` with ticket numbers.

When a skill requests publication, create or update the corresponding
file. When it requests a ticket, read the referenced file.

For wayfinding, keep the map at `.scratch/<effort>/map.md`.
Each decision ticket uses the issues directory and records its `Type:`
(research, prototype, grilling, or task) and `Status:` (open, claimed,
or resolved). Select the lowest-numbered open ticket whose blockers
are resolved. Mark it claimed before working; append its answer,
mark it resolved, and link the decision from the map when finished.
