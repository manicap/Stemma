# AGENTS.md

## Project

Stemma is a Django-based family information system. Work in small, verifiable vertical slices that preserve the approved architecture.

This file is intentionally short. **Do not read the whole `docs/` directory.** The rules you need are in the skill `stemma-context` (`.ai/skills/stemma-context/SKILL.md`). Open a document in `docs/` only when the skill or your task explicitly points to it, and then only the relevant section.

The previous long version of this file (25 kB, multi-role review workflow) is preserved in git history before the commit that introduced this version.

## Baseline

- Python 3.14, Django 5.2 LTS, SQLite, server-rendered templates + HTMX, minimal custom JavaScript, no SPA.
- Configuration package `config`; custom user model `accounts.User` (use `settings.AUTH_USER_MODEL` / `get_user_model()`).
- Apps in the repository root: `accounts`, `common`, `people`, `places`, `events`, `materials`, `health`. `audit` is planned and does not exist.
- Local settings: copy `config/settings_local.example.py` to `config/settings_local.py` (never commit it).

## Commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test                      # full suite, ~1 700 tests, ~70 s
python manage.py test people.test_person_search   # focused example
```

In a Cezar task use the task's virtualenv: `.venv/bin/python manage.py ...`.

## How a task runs

- One task = one small slice = one branch = one pull request. The branch is created for you (Cezar worktree). Do not switch, create, merge, rebase or push branches yourself; do not touch `main`, `feature/mvp`, `agent/rc-0.1`, `backup/*`.
- Stay inside the scope of the task. If the task needs something outside it, stop and explain (see Escalation).
- Add or update tests for changed behaviour. Never delete or weaken a test, an assertion or an authorization check to get green.
- Quality is checked by commands after you finish (tests, Django checks, migration drift, diff size, changelog). There are no reviewer roles; review your own diff once before finishing.
- Commit with explicit file paths (no `git add -A`). Never commit `config/settings_local.py`, `db.sqlite3`, `.venv/`, media files or local launcher helpers (`start_stemma_test.*`, `stemma_local_test_launcher*`).

## Changelog (required)

Every task adds one new file `docs/changelog/YYYY-MM-DD-<short-name>.md` following `docs/changelog/_sablona.md`. Write it in Czech for a human: what changed from the user's point of view, why, how to try it. No code listings. A check rejects a task without it.

## Escalation

Stop and explain (one concise message: blocking fact, evidence, safest option, consequences) only when:

1. Two authoritative documents materially conflict.
2. The step needs a new or changed ACP, architecture change, or a changed meaning of a system value.
3. A security, privacy, visibility or access-control rule is undefined and the choice affects what real users can see or modify.
4. The action is destructive or irreversible (data loss, destructive migration, history rewriting).
5. It needs credentials, secrets, paid services or access you do not have.
6. It would touch production or real user data.
7. A user-visible product decision has incompatible interpretations not settled by documentation.
8. Validation still fails after three materially different reasonable attempts.

Otherwise decide low-risk, reversible details yourself using existing project conventions.
