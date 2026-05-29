---
name: verify-migration
description: >-
  Manually verify a FINISHED feature or bugfix in this vue3-migration project by
  running the REAL tool end-to-end against a scenario-based test env and saving
  linked, examinable proof. Use after implementing a change and you want to prove
  it works (or that a bug is fixed) — beyond unit tests. Triggers on: "verify the
  feature", "prove the bugfix", "manually test this change", "run the tool and
  show me it works", "show me the migration report for X". NOT for writing the
  feature itself or for pure unit-test runs.
---

# verify-migration — prove a change with a real tool run

The goal: after a feature/bugfix is done, demonstrate it on a real, reset test
environment, run the **actual CLI** (apply mode, so the tool writes its own
migration report), and save artifacts that let **both the developer and you**
verify the outcome — with clickable links to the exact proof.

This is general for any feature or bugfix in this project. Adapt the scenarios
to the change; the mechanics below never change.

## Non-negotiable principles (learned the hard way)

1. **Never mutate a committed fixture.** The runner copies the fixture to a
   throwaway temp dir and runs the tool THERE. Inputs under `tests/fixtures/<env>/`
   stay pristine.
2. **The tool scans the whole project tree.** Generated composables written
   inside the project flip later runs onto the patch path (false results). That's
   why we run on a temp copy and save review output to a git-ignored dir OUTSIDE
   any project root the tool scans (`tests/fixtures/.verify/`).
3. **Reset to pristine before EVERY run.** Each scenario gets a fresh copy so
   there are no pre-existing composables to fuzzy-match against.
4. **Run the REAL tool, applied.** `python -m vue3_migration --root <copy> <cmd>`
   with apply confirmed — this is what writes the genuine `migration-report-*.md`.
5. **Keep fixtures focused.** One scenario per use case / edge case. Avoid member
   names that collide with tooling internals (e.g. a member literally named
   `value`). For a bugfix, include a scenario that reproduces the bug.

## Procedure

### 1. Decide what proves the change
State the observable outcome that proves it. For a **bugfix**, also state the
*before* symptom (what the tool wrongly did) so you can assert it's gone.

### 2. Build or extend the test env
Create scenario inputs under `tests/fixtures/<env>/` (mirror existing fixtures —
`src/mixins/*.js` as `export default {…}`, `src/components/*.vue` importing via
`@/mixins/<name>`, `src/utils/` as needed). One mixin+component per scenario.
Cover the happy path AND edge cases relevant to the change. Reuse
`tests/fixtures/scoping_project/` as a worked example, or `tests/fixtures/dummy_project/`
when you need realistic, messy mixins.

### 3. Write a verification manifest
Create `<env>/verification.json` describing the runs and expectations. Schema and
a worked example: `templates/verification.example.json` in this skill. Each run:
`{ name, command (component|mixin|all), target, expect: { report_contains/absent,
files: { "<relpath>": { contains/absent } } } }`. For a bugfix, put the old buggy
string in `report_absent`/`absent` and the correct behavior in `*_contains`.

### 4. Ensure the review dir is git-ignored
Confirm `.gitignore` contains `tests/fixtures/.verify/` (add it once if missing).
Generated review output is reproducible and must not be committed.

### 5. Run the real tool across all scenarios
```bash
python3 .claude/skills/verify-migration/scripts/run_verification.py <env>/verification.json
```
For each run it: resets a fresh copy → runs the real CLI applied → captures the
tool's `migration-report-*.md`, the generated composable(s), the migrated
component, and the CLI log → checks expectations → writes
`tests/fixtures/.verify/<env>/` with per-scenario folders, an `INDEX.md` (links +
verdicts) and a machine-readable `results.json`.

### 6. (Bugfix only, optional but strong) capture before/after
To prove a regression is fixed: `git stash` the fix, run the manifest into a
`…/before/` out dir, `git stash pop`, run again into `…/after/`. Link both so the
developer sees the report change.

### 7. Examine, then present
Read `results.json` and `INDEX.md`. If any check fails, investigate — a failure
may be a real bug worth surfacing, not just a bad expectation. Then report to the
developer with:
- a link to `INDEX.md`,
- a link to the tool's `migration-report.md` for the key scenario(s),
- links to the exact proof (generated composable / migrated component lines),
- a one-line verdict per scenario (expected vs actual).

## Notes
- The CLI resolves `@/…` to the nearest `src/`, finds components via `rglob`, and
  treats a mixin with no matching composable as `BLOCKED_NO_COMPOSABLE` (→ generate).
  A fixture with no `composables/` dir therefore exercises generation cleanly.
- `_apply_plan` writes the migration report into the run's `--root`; the runner
  collects it. Modes: `component <path>`, `mixin <name>`, `all`.
- Be honest about fixture bias: clean fixtures yield "no action needed" — that
  proves *the behavior under test*, not that real mixins are warning-free.
