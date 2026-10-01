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

The CLI is currently planned, not implemented. Native shared-database exclusion and any need for additional `run` protection or owner diagnostics remain to be experimentally verified.
