# AGENTS.md

## Project

Stemma is a Django-based family information system. Work in small, reviewable steps and preserve the approved architecture.

## Source of truth

The Git repository is the authoritative source of code and documentation.

Before implementing a non-trivial change, read the relevant current documents, especially:

- `docs/00_README.md`
- `docs/05_PRAVIDLA_DOKUMENTACE.md`
- `docs/07_ROADMAPA.md`
- `docs/08_ARCHITEKTONICKE_PRINCIPY.md`
- `docs/09_CODING_STANDARD.md`
- `docs/11_DATABAZOVY_NAVRH.md`
- `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md`

When documentation and an older discussion differ, the newest documentation in the repository wins.

## Current technical baseline

- Python 3.14
- Django 5.2 LTS
- SQLite
- Django configuration package: `config`
- Custom user model: `accounts.User`
- Server-rendered Django templates
- HTMX for partial page updates
- Minimal custom JavaScript
- No SPA architecture without an approved ACP

Use `settings.AUTH_USER_MODEL` or `get_user_model()` instead of importing the user model directly where Django recommends it.

## Project applications

Applications live in the repository root:

- `accounts`
- `common`
- `people`
- `places`
- `events`
- `materials`
- `health`
- `audit`

`common` contains shared fixed choices, abstract models, validation and helper functions. Business entities belong to their domain applications.

## Architecture rules

- Store each fact, relationship, source and physical file only once.
- Birth and death are events, not fields on a person.
- Derived values such as age, living/deceased state and Roman numbering are not stored without an approved reason.
- Do not replace incomplete dates with false precise dates.
- Use Django `TextChoices` for fixed validation or security values.
- Use lookup models for user-manageable or extensible vocabularies.
- Use explicit linking models for attachments and sources; do not use generic relations for business links.
- Keep write business logic in domain services.
- Keep complex read queries in selectors.
- Views coordinate HTTP, forms, services and responses; they must not contain large business rules.
- Significant multi-object writes must use `transaction.atomic()`.
- Enforce permissions on the server, not only in the UI.
- Do not log or audit passwords, tokens, secrets or file contents.
- Preserve the distinction between archiving and soft deletion.
- Do not introduce a dependency without a clear and documented benefit.
- Do not change approved architecture or the meaning of system values without stopping and reporting the conflict.

## Implementation workflow

For each task:

1. Inspect the current branch, working tree and relevant documentation.
2. State the planned small change before editing.
3. Modify only files required by the task.
4. Add or update tests for every new behavior.
5. Do not create migrations unless database models or fields changed.
6. Keep structural and data migrations separate when that improves clarity.
7. Do not rewrite migrations already shared in the repository; create a new migration for corrections.
8. Run the relevant checks and report exact results.
9. Summarize changed files, risks, deviations and a proposed commit message.

Before a larger architectural decision, stop and request approval. If needed, identify the affected documentation and whether a new ACP is required.

## Documentation updates

Documentation is part of the product and must remain consistent with the implementation.

Update existing documentation when a change:

- completes or materially advances an implementation milestone,
- changes the current project state recorded in the roadmap or README,
- introduces or changes a model, fixed system value, validation rule, permission, workflow or architectural decision,
- resolves an open question,
- creates a meaningful difference between implementation and the current documentation.

Create new documentation only when the subject is significant, long-lived and not adequately covered by an existing document. Before creating a new document:

- verify that the information does not belong in an existing document,
- follow the naming and numbering rules in `docs/05_PRAVIDLA_DOKUMENTACE.md`,
- add the new document to `docs/00_README.md`,
- record the addition in `docs/CHANGELOG.md`,
- do not create a new ACP document; architectural decisions belong in `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md` and require explicit approval.

For significant documentation updates:

- update the relevant document version, revision date and status when required by `docs/05_PRAVIDLA_DOKUMENTACE.md`,
- update `docs/CHANGELOG.md`,
- update `docs/07_ROADMAPA.md` when milestone status changes,
- update `docs/00_README.md` when the current project state or documentation index changes,
- update `docs/06_ROZHODNUTI_A_OTEVRENE_OTAZKY.md` when a decision is made or an open question is resolved,
- do not create or modify an ACP without explicit approval.

Do not update documentation for trivial internal refactoring, formatting-only changes, or tests that do not change documented behavior or milestone status.

If it is unclear whether documentation should be updated or created, stop and report the affected files and recommended action before editing.

## Git and branch safety

Protect the repository history and the user's local work.

Before editing:

- run `git branch --show-current` and `git status --short`,
- confirm that the repository is Stemma and that the expected base branch is active,
- stop if there are unrelated uncommitted changes, merge conflicts, an unfinished rebase, or an unexpected detached `HEAD`,
- never discard, overwrite, stash, stage, or modify unrelated user changes without explicit approval.

Branch workflow:

- The normal active integration branch for MVP work is `feature/mvp`.
- Small, sequential, reviewed tasks may be implemented directly on `feature/mvp` when the task explicitly allows local edits there.
- For larger, risky, experimental, or parallel tasks, create a dedicated task branch from the current `feature/mvp` state.
- Name task branches `codex/<milestone>-<short-description>`, for example `codex/m1-partial-date-validation`.
- Do not create a new branch for trivial formatting-only work or a tiny follow-up that belongs to the current uncommitted task.
- Do not switch branches, create a branch, or create a worktree unless the task explicitly permits it or the current task is classified as larger, risky, experimental, or parallel. When uncertain, stop and ask.
- If working in a Codex worktree, verify the selected base branch before editing. If `HEAD` is detached, create a named task branch before any commit.

Commit and remote rules:

- Do not commit, amend, merge, rebase, push, force-push, open a pull request, or delete a branch unless the user explicitly requests that action for the current task.
- Before a requested commit, run tests and checks, inspect `git diff --check`, `git status --short`, and the staged diff.
- A commit must contain only one coherent change and must not include unrelated files, secrets, local settings, caches, generated artifacts, or database files.
- Never use `git add .` or `git add -A` when a narrower explicit file list is available.
- Never use destructive commands such as `git reset --hard`, `git clean -fd`, checkout/restore that discards changes, or history rewriting without explicit approval.
- Never force-push. Never rewrite commits already pushed to a shared branch.
- Do not merge a task branch into `feature/mvp`; prepare the diff and report the recommended integration step unless explicitly instructed otherwise.

At the end of each task, report:

- current branch,
- changed and untracked files,
- whether a task branch or worktree was used,
- whether any commit, push, merge, rebase, or pull request was performed,
- the exact recommended next Git command, if appropriate.

## Required checks

Run at least:

```text
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

For a single application, also run its focused tests first, for example:

```text
python manage.py test common
```

For staged changes, check whitespace and the diff:

```text
git diff --check
git status --short
git diff
```

## Code style

- Follow PEP 8.
- Prefer readable, explicit and type-annotated Python.
- Add concise docstrings where they clarify responsibility.
- Keep commits small and focused.
- Use Czech labels for user-facing text and stable English technical values for stored choice values unless current documentation specifies otherwise.
- Preserve UTF-8 encoding and a single newline at end of file.

## Current milestone

The active implementation branch is `feature/mvp`.

Milestone M0 is complete. Current work is milestone M1: the shared `common` foundation, including fixed choices, abstract models and partial-date validation with tests.
