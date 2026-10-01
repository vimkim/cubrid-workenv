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

Agents must use `cub-workenv run ...` for host-side CUBRID tests and database-opening operations. Read `docs/agents/test-execution.md` before running them. Use the target worktree's prepared environment and keep operations scoped to that environment.

The CLI is currently planned, not implemented. Until it is available and its protection is verified, report the missing prerequisite rather than falling back to an unguarded host test.
