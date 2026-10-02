## Agent skills

### Issue tracker

Track specs and issues in local Markdown under `.scratch/<feature>/`.
See `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage roles.
See `docs/agents/triage-labels.md`.

### Domain docs

Use a single root glossary and `docs/adr/`.
See `docs/agents/domain.md`.

## CUBRID host test execution

Use the intended worktree's prepared environment for host-side CUBRID tests. Ordinary `cubrid` and `csql` commands may run directly; `cub-workenv run` is not mandatory for all tests. Read `docs/agents/test-execution.md` for the distinction between separate databases and shared physical database storage.

The CLI provides explicit init/create-db, cheap env loading and read-only doctor.
For build-through-removal operation or recovery after failed initialization, read
`docs/workflow.md`. For proven behavior and unverified limits, read
`docs/evidence/ticket09-workflow.md`. Personal shared-tooling application is a
separate decision because existing source worktrees may link to it.
