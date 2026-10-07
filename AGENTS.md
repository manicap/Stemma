# AGENTS.md

## Project

Stemma is a Django-based family information system. Preserve the approved architecture and move the project toward a genuinely usable first production candidate through small, verifiable vertical slices.

This file contains the execution policy for the active development branch `agent/rc-0.2`. It does not grant permission to change approved architecture, ACP decisions, security policy, or the meaning of documented system values.

## Source of truth

The Git repository is the authoritative source of code and documentation.

Before implementing a non-trivial change, read the relevant current documents, especially:

- `docs/00_README.md`
- `docs/05_PRAVIDLA_DOKUMENTACE.md`
- `docs/06_ROZHODNUTI_A_OTEVRENE_OTAZKY.md`
- `docs/07_ROADMAPA.md`
- `docs/08_ARCHITEKTONICKE_PRINCIPY.md`
- `docs/09_CODING_STANDARD.md`
- `docs/11_DATABAZOVY_NAVRH.md`
- `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md`

When documentation and an older discussion differ, the newest authoritative documentation in the repository wins. When two authoritative documents appear to differ, prefer the more specific rule only when they can be reconciled without changing product meaning. Otherwise escalate.

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

Current applications live in the repository root:

- `accounts`
- `common`
- `people`
- `places`
- `events`
- `materials`
- `health`

The approved design also plans this domain application, but its package does
not exist yet and must not be treated as implemented:

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
- Do not change approved architecture, ACP decisions, access-control semantics, or the meaning of system values without explicit user approval.

## Autonomous operating mode

On `agent/rc-0.2`, the default behavior is to continue working within the explicitly approved slice rather than stop after every implementation step.

For reversible implementation decisions that are consistent with approved documentation and architecture:

- choose the simplest maintainable option,
- prefer existing project patterns over new abstractions,
- document a material decision when required,
- implement it,
- verify it,
- fix discovered defects,
- and continue to the next smallest useful vertical slice without asking for routine approval.

Do not ask the user to choose between equivalent low-risk implementation details. Minor naming, internal refactoring, test structure, template structure, and similarly reversible details should be resolved autonomously using existing project conventions.

Do not treat a completed internal milestone as sufficient evidence of progress. Prefer vertical slices that move the application toward actual user-visible usefulness while respecting the documented roadmap and dependencies.

## Escalation policy

Stop and ask the user only when at least one of these conditions is true:

1. Two current authoritative documents contain a material conflict that cannot be reconciled without changing product behavior.
2. The next step requires a new or changed ACP, a change to approved architecture, or a change to the meaning of a documented system value.
3. A security, privacy, visibility, authorization, or access-control policy is materially undefined and the choice would affect what real users can see or modify.
4. The action is destructive or meaningfully irreversible, including intentional data loss, destructive migration, deletion of user data, history rewriting, or force-push.
5. The work requires credentials, secrets, an external account decision, paid service activation, or access that is not already available.
6. The work would deploy to or mutate a real production environment or real user data and that production action has not been explicitly authorized.
7. A material user-visible product decision has multiple incompatible interpretations and current documentation does not determine the intended behavior.
8. Required validation remains failing after at least three materially different reasonable attempts and continuing would require a risky workaround, weakening tests, or guessing at architecture.

When escalating, provide one concise message containing: the blocking fact, the relevant evidence, the safest recommended choice, and the consequence of each materially different alternative. Do not ask several low-level questions separately.

## Lead-agent workflow

The main agent is the implementation owner and should execute this loop autonomously:

1. Complete Level 0: verify repository state, classify the change, and read the
   relevant current documentation.
2. Determine the actual implementation state rather than trusting milestone
   labels alone, then choose the smallest coherent slice with clear acceptance
   conditions.
3. State a short internal plan and implement only the required files. Add or
   update tests for changed behavior.
4. Complete Levels 1 and 2: use focused feedback during implementation, finish
   the behavior and documentation, then inspect the whole affected diff.
5. Complete Level 3 reviews selected by the review matrix.
6. Fix valid findings. Rerun only checks and reviews invalidated by the fix,
   unless the fix expands the impact classification.
7. Complete the Level 4 final gate once over the stable diff.
8. Complete Level 5: record the result, commit and push the accepted coherent
   slice, verify remote equality, and verify a clean tracked tree.
9. Continue only when an explicit current goal remains. Stop autonomous feature
   expansion once its documented target has been reached.

Do not solve a failing test by deleting it, weakening its assertion, bypassing authorization, hiding an error, or reducing documented guarantees unless the test is demonstrably incorrect according to authoritative documentation.

## Subagents and independent review

Use subagents for bounded, primarily read-only independent work when the environment supports them. The lead agent remains responsible for final implementation and integration.

Default review roles are:

### Documentation auditor

- compare implementation with current documentation,
- identify stale milestone claims or undocumented behavior,
- flag true contradictions,
- do not invent product requirements.

### QA and test reviewer

- inspect changed behavior and tests independently,
- look for missing edge cases and regressions,
- verify that tests exercise behavior rather than merely implementation details.

### Security and access-control reviewer

Use whenever authentication, authorization, visibility, health data, private data, selectors, services, forms, or direct-object URLs are involved.

- attempt to find ways to bypass intended access rules,
- check anonymous, authenticated, inactive, staff, superuser, and object-visibility cases when relevant,
- treat server-side enforcement as mandatory.

### UI/UX reviewer

Use whenever user-facing views, templates, forms, HTMX interactions, responsive layout, validation messages, or navigation change.

- verify the feature as a user flow, not only as isolated code,
- check failure and empty states where applicable,
- prefer the approved UI/UX documentation over ad-hoc redesign.

Subagents should normally report findings rather than modify shared files. If an isolated worktree is explicitly used for parallel implementation, the lead agent must review and integrate the result and must prevent overlapping writes to the same files.

If subagents are unavailable, perform the same review roles sequentially as independent review passes before accepting the slice.

## Staged invalidation-based gate

ACP-009 refines the validation and review orchestration authorized by ACP-006.
A successful check remains valid until a relevant input changes. Workflow order
alone does not invalidate it. Run the most expensive checks only after the diff
is stable; when impact is uncertain or shared across applications, use the
stricter gate. Explicit acceptance criteria or user instructions may always
require more than these minimums.

### Level 0 - entry

- Verify the branch, HEAD, tracked working-tree state, and repository identity.
- Fetch and compare with the expected remote once. Repeat only if remote state
  may have changed or the final push needs verification.
- Classify the change by affected files, behavior, applications, security
  footprint, query shape, UI surface, and documentation impact.
- Read the relevant current documentation and inspect existing implementation
  evidence before editing.

### Level 1 - implementation feedback

- Run the smallest focused tests that give useful feedback for the current edit.
- Run an application suite only when the change affects that application's
  behavior or shared fixtures used by it.
- Check migration drift only for model, migration, application registry, or
  schema-affecting settings changes.
- Run Django's system check only for relevant Django Python, URL, template,
  settings, application registry, or configuration changes.

### Level 2 - functionally complete slice

- Run the affected application or cross-application regression set selected by
  the impact classification.
- Complete the documentation impact analysis and all required documentation
  updates, including metadata and changelog, before documentation review.
- Inspect the complete diff for scope, accidental weakening, and unrelated
  changes.
- Run query-count/N+1 or browser/UI checks only when query shape or user-visible
  behavior is affected.

### Level 3 - impact-based review

- Request QA review for behavioral changes, HTTP/UI flows, validation, test
  contracts, and shared services or use-cases.
- Request security review for permissions, actor-aware APIs, health data,
  authentication/session/CSRF, lifecycle, file/storage delivery, protected
  direct URLs, and visibility filtering.
- Request documentation review for changed documentation or changes to models,
  behavior, permissions, workflow, milestones, or decisions. It runs only after
  the documentation impact analysis and documentation edits are complete.
- Request UI/UX review when views, templates, forms, HTMX, navigation,
  responsive layout, or user-visible failure and empty states change.
- After a local finding, repeat only the affected checks and relevant reviewer.
  Expand the review set only when the fix reaches another domain.

### Level 4 - final gate over a stable diff

- Run the full test suite once for executable or shared Python changes, or for a
  cross-application change. A later documentation-only correction does not
  invalidate that PASS.
- Run Django's system check and migration drift check only when the impact rules
  above require them.
- Perform final diff, whitespace, secret, generated-artifact, database-file, and
  tracked-status inspection.

### Level 5 - closure

- Confirm that required document metadata and the changelog were completed and
  reviewed at Level 2 and Level 3.
- Verify the tracked working-tree state, then stage only explicit relevant files.
- Create one coherent commit and push it to `origin/agent/rc-0.2`.
- Verify local and remote HEAD equality and a clean tracked working tree.

Do not routinely repeat the full suite, fetch, system check, migration check, or
all reviewers without an invalidating change. A failed check is not a reusable
PASS; diagnose it and rerun the affected check after the fix.

### Invalidation matrix

| Change type | Required invalidation |
| --- | --- |
| Production Python | Focused and affected regression tests; full suite once on the stable diff. Add system check when Django wiring or configuration is affected. |
| Model | Model/application tests, migration drift check, system check, full suite, QA review, documentation review, and security review if access semantics are touched. |
| Migration | Migration/application tests, migration drift check, system check, full suite, and documentation review when schema or required data state changes. |
| Selector or query shape | Selector/consumer tests and query-count or N+1 coverage; full suite for shared or cross-app impact. Add security review for visibility filtering. |
| Permission or visibility logic | Focused authorization and protected HTTP tests, affected regressions, full suite, and security plus documentation review. |
| Use-case delegation, including actor-aware | Use-case and caller boundary tests; QA review, and security review whenever protected data or writes are involved. |
| HTTP view or template | Focused HTTP/HTMX tests and QA review; browser and UI/UX review for changed user flows. Add security review for protected objects or actions. |
| Test-only | Run the changed tests and their direct consumers. Full suite is required only when shared fixtures, helpers, settings, discovery, or global state changed. |
| Markdown-only | Documentation consistency, documentation review, final diff and whitespace checks. Documentation alone does not invalidate Django tests, system check, or migration drift. Add QA only if application behavior or a test contract changes; add security only if application security or access-control policy changes. |
| Demo seed | Seed tests and affected domain tests; full suite for shared bootstrap changes. Add security review if identities, permissions, or protected sample data change. |
| Settings or app registry | Focused configuration tests, system check, and usually the full suite; add migration drift when schema discovery can change. |
| CSS or JavaScript | Relevant static/UI tests and browser or UI/UX verification; no Django full suite unless templates, shared behavior, or server contracts also change. |
| Documentation correction after review | Repeat documentation consistency and documentation review for the corrected scope. Preserve earlier test PASS results unless executable inputs changed. |

## Migrations

- Do not create migrations unless database models, fields, constraints, indexes, or required data state changed.
- Keep structural and data migrations separate when that improves clarity.
- Do not rewrite migrations already shared in the repository; create a new migration for corrections.
- Never introduce intentional data loss without escalation and explicit approval.

## Documentation updates

Documentation is part of the product and must remain consistent with implementation.

Update existing documentation when a change:

- completes or materially advances an implementation milestone,
- changes the current project state recorded in the roadmap or README,
- introduces or changes a model, fixed system value, validation rule, permission, workflow, or architectural decision,
- resolves an open question,
- creates a meaningful difference between implementation and current documentation.

For routine implementation where it is merely unclear which existing document should receive a small factual update, choose the most specific existing document and continue. Do not stop solely for document-placement uncertainty.

Create new documentation only when the subject is significant, long-lived, and not adequately covered by an existing document. Before creating a new document:

- verify that the information does not belong in an existing document,
- follow the naming and numbering rules in `docs/05_PRAVIDLA_DOKUMENTACE.md`,
- add the new document to `docs/00_README.md`,
- record the addition in `docs/CHANGELOG.md`,
- do not create a separate ACP document; architectural decisions belong in `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md` and still require explicit user approval.

For significant documentation updates:

- update the relevant document version, revision date, and status when required by `docs/05_PRAVIDLA_DOKUMENTACE.md`,
- update `docs/CHANGELOG.md`,
- update `docs/07_ROADMAPA.md` when milestone status changes,
- update `docs/00_README.md` when the current project state or documentation index changes,
- update `docs/06_ROZHODNUTI_A_OTEVRENE_OTAZKY.md` when a decision is made or an open question is resolved.

Do not update documentation for trivial internal refactoring, formatting-only changes, or tests that do not change documented behavior or milestone status.

## Git and branch safety

Protect repository history and the user's local work.

Before editing:

- run `git branch --show-current` and `git status --short`,
- confirm that the repository is Stemma,
- for current RC work, expect `agent/rc-0.2` unless an isolated task worktree was intentionally created from it,
- stop if there are unrelated uncommitted user changes, merge conflicts, an unfinished rebase, or an unexpected detached `HEAD`,
- never discard, overwrite, stash, stage, or modify unrelated user changes.

Branch workflow:

- `feature/mvp` is the preserved pre-agent integration baseline and must not be modified by autonomous RC work.
- `backup/pre-agent-2026-08-17` is a recovery snapshot and must never be moved or used for development.
- `agent/rc-0.1` is the closed RC 0.1 baseline and must not receive further functional development.
- `agent/rc-0.2` is the active development branch.
- The lead agent may create temporary `codex/<milestone>-<short-description>` branches or isolated worktrees from `agent/rc-0.2` when genuinely useful for risky or parallel work, without asking for routine approval.
- Subagents should be read-only by default; parallel write work must be isolated and non-overlapping.

Commit and remote rules for `agent/rc-0.2`:

- The lead agent may stage explicit relevant files, create a coherent commit, and push to `origin/agent/rc-0.2` after the required checks pass.
- Commit only one coherent accepted slice at a time.
- Every completed and verified vertical slice must be committed separately and pushed to `origin/agent/rc-0.2` before work begins on the next slice. After the push, the working tree must be clean except for explicitly ignored local artifacts.
- Local test launcher artifacts `start_stemma_test.ps1`, `start_stemma_test.cmd`, `stemma_local_test_launcher/`, and packaged variants such as `stemma_local_test_launcher.zip` are user-owned local helpers only. Never stage, commit, or push them.
- Before committing, run the relevant tests and checks, inspect `git diff --check`, `git status --short`, and the final diff.
- Never use `git add .` or `git add -A` when a narrower explicit file list is available.
- Do not amend or rewrite already pushed commits.
- Never force-push.
- Never merge or rebase `agent/rc-0.1` or `agent/rc-0.2` into `feature/mvp` or `main` without explicit user approval.
- Never delete `feature/mvp`, `backup/pre-agent-2026-08-17`, `agent/rc-0.1`, `agent/rc-0.2`, or another user's branch without explicit approval.
- Do not open or merge a pull request into `feature/mvp` or `main` without explicit user approval.
- Never use destructive commands such as `git reset --hard`, `git clean -fd`, checkout/restore that discards user changes, or history rewriting without explicit approval.

After an autonomous slice is accepted and pushed, record enough information in the final run summary to identify the branch, commit, checks, and any residual risk. Routine successful slices do not require the user to approve the next slice.

## Required checks

Select checks from the staged gate and invalidation matrix; do not use one
unconditional list for every change. Every coherent change still requires final
diff, whitespace, artifact, and tracked-status inspection.

Executable or shared Python and cross-application changes require the full test
suite once over the stable diff. Django's system check, migration drift check,
focused security tests, query-count checks, and browser/UI verification are
mandatory when their documented impact condition applies.

The final RC 0.1 acceptance gate in `docs/07_ROADMAPA.md` remains absolute and
includes the complete suite and all checks and evidence stated there. The
invalidation rules optimize intermediate slices; they do not weaken a release
or milestone acceptance contract.

## Testability gate

A vertical slice must not be marked complete or ready for browser verification unless the user has a reproducible, documented way to create the data, accounts, roles, permissions, or other local state required to verify the new behavior manually.

Any feature that requires authentication or specific permissions must include a safe local bootstrap for the relevant test identities before its slice is accepted. Local test credentials must never be hard-coded, staged, committed, pushed, logged, or reused as production credentials.

## Code style

- Follow PEP 8.
- Prefer readable, explicit and type-annotated Python.
- Add concise docstrings where they clarify responsibility.
- Keep commits small and focused.
- Use Czech labels for user-facing text and stable English technical values for stored choice values unless current documentation specifies otherwise.
- Preserve UTF-8 encoding and a single newline at end of file.

## RC 0.1 acceptance contract

The authoritative RC 0.1 acceptance criteria and explicit non-goals are defined in `docs/07_ROADMAPA.md`. ACP-006 in `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md` authorizes this autonomous execution mode only on `agent/rc-0.1`; ACP-009 refines its validation and review workflow.

The lead agent must treat those acceptance criteria as a contract, not as suggestions:

- first audit the actual repository state and mark which criteria already have trustworthy implementation evidence,
- work on the smallest safe vertical slice that closes a real acceptance gap,
- do not recreate already working backend behavior merely to fit the new UI,
- do not mark an acceptance area complete from unit tests alone when the roadmap requires a real browser or end-to-end verification,
- do not declare RC 0.1 complete while any required acceptance area is unverified,
- do not expand RC 0.1 with non-goal features unless they are genuinely required dependencies for a mandatory acceptance criterion.

When all RC 0.1 criteria pass, stop autonomous feature expansion and produce a final RC readiness report. Do not deploy, merge into `feature/mvp` or `main`, or begin unrelated later roadmap work without explicit user approval.

## Current mission

The active development branch is `agent/rc-0.2`; `agent/rc-0.1` is a closed,
protected baseline.

Milestones M0, M1, and M2 are complete. All RC 0.1 acceptance areas A-H are
recorded as complete in `docs/07_ROADMAPA.md`. Autonomous feature expansion
toward RC 0.1 has therefore stopped. RC 0.2 starts with the explicitly approved
read-only person relationship tab.

The current approved goal is only the read-only person relationship UI. It does
not authorize relationship writes or lifecycle actions, Relationship Materials
UI, or another planned person tab. Further functional slices require separate
explicit approval. Use the established architectural boundaries and the
ACP-009 invalidation-based gate.

Do not declare Stemma production-ready merely because roadmap items or automated
tests are complete. Production deployment, integration into `feature/mvp` or
`main`, and any later roadmap target remain separately authorized actions.
