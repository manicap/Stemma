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
