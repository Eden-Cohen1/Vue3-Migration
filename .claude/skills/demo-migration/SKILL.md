---
name: demo-migration
description: >-
  Demo the vue3-migration tool LIVE against the external demo Vue project
  (default: /Users/base/Projects/dummy_vue_migration_project), apply real
  changes, and leave them in place for review via `git diff` (e.g. an open VS
  Code window). On invocation, ALWAYS ask which route to run — default is 3
  component migrations; alternatives are more components, a mixin retirement, or
  a mix. Triggers on: "run the demo", "demo the migration", "show me the tool
  working on the dummy project", "migrate a few components in the demo repo and
  show the diff". NOT for verifying a specific bugfix against fixtures (use
  verify-migration) and NOT for migrating the user's real production project.
---

# demo-migration — run the tool live on the demo project, show the diff

Goal: reproduce the hands-on demo flow — run the **real CLI** (applied) against
an external Vue project, leave the changes in the working tree, and present the
`git diff` so the developer can eyeball that the tool works as expected. Nothing
is reverted; tool-generated report files are cleaned so only real migration
changes remain.

This differs from **verify-migration**: that one proves a specific change against
copied scenario fixtures with kept artifacts and pass/fail expectations. This one
just *shows the tool working* on a realistic project and hands back a diff.

## Non-negotiable principles (learned the hard way)

1. **Always pass `--root <project>`.** The CLI derives the project root from
   `--root` (or cwd) and **ignores a positional path argument**. `status
   /some/path` silently scans cwd — which once meant scanning the tool's own
   fixtures instead of the target. Run the tool from the tool-repo dir with
   `python3 -m vue3_migration --root <project> <command>`.
2. **The `component` and `mixin` commands are non-interactive except one
   `Apply changes? (y/n)`.** Drive it with `y` (the runner pipes `"y\n"`).
3. **The migration report is a primary deliverable — keep it.** Each applied run
   writes a `migration-report-*.md` (per-file diffs, warnings, confidence
   ratings, checklist) into the project root. The runner **keeps these by
   default** and prints their paths so the developer can open them — that report
   is usually the thing they want to see. Cleanup is opt-in (`--clean-reports`)
   and removes only **untracked** reports from THIS run — **never** a
   tracked/committed one (deleting a pre-existing committed report once polluted
   the diff and needed `git checkout` to restore).
4. **Leave migration changes in place.** The whole point is the developer
   reviewing the diff. Do not revert.
5. **Don't touch the user's real project.** Only the demo project (or a `--root`
   the user explicitly names).

## Procedure

### 1. Locate and check the target
The demo project is resolved portably (so this works on any machine): the
`$VUE3_DEMO_PROJECT` env var, else a sibling `dummy_vue_migration_project` next to
this tool repo, else a built-in fallback path. Override with `--root`. The demo
repo lives on GitHub (`Eden-Cohen1/dummy_vue_migration_project`) — clone it beside
this repo to use these skills elsewhere. Confirm the target exists and is a git
repo (the diff is the deliverable); note any pre-existing uncommitted changes,
since the diff will include them.

### 2. Ask the route (REQUIRED — do this every run)
Use AskUserQuestion to offer:
- **3 components (default)** — the canonical flow: auto-select 3 READY
  components spread across mixin-counts (a 1-mixin, a 2-mixin, a 3-mixin case).
- **More components** — same flow with a larger N (e.g. 6).
- **Mixin flow** — retire one mixin across the whole project
  (`mixin <name>`); pick a widely-used one from the status scan, or ask which.
- **Mix** — a couple of components plus one mixin retirement.

Honor an explicit request (e.g. "do 5 components" or "retire loadingMixin")
without re-asking.

### 3. (Optional) scan to inform the choice
A read-only `status` run helps pick good targets and name mixins:
```bash
cd <tool-repo>
python3 -m vue3_migration --root <project> status
```
It writes a `migration-status-*.md` into the project; the runner cleans it up.
READY components appear as `### [`src/...`]` blocks with `Status: **Ready**`.

### 4. Run the chosen route
Call the runner (it does selection, applies each migration, **keeps** the
migration report(s), validates, and prints the diff + report paths):
```bash
# default — 3 varied components
python3 .claude/skills/demo-migration/scripts/run_demo.py

# more components
python3 .claude/skills/demo-migration/scripts/run_demo.py --components 6

# mixin retirement (+ keep it simple)
python3 .claude/skills/demo-migration/scripts/run_demo.py --components 0 --mixins loadingMixin

# a mix: 2 specific components + a mixin
python3 .claude/skills/demo-migration/scripts/run_demo.py \
    --component-paths src/components/common/SearchBar.vue,src/components/dashboard/StatsOverview.vue \
    --mixins notificationMixin

# different project
python3 .claude/skills/demo-migration/scripts/run_demo.py --root /path/to/other/project

# default keeps the reports; add --clean-reports only if you want them removed
python3 .claude/skills/demo-migration/scripts/run_demo.py --clean-reports
```

### 5. Present the result
Show the developer:
- the **migration report(s)** the runner kept — it prints their paths at the end.
  These hold the per-file diffs, warnings, confidence ratings, and checklist;
  point the developer to open them in their editor (they're often the main thing
  they want to see). Do NOT delete them.
- the `git diff --stat` (which components + which composables changed),
- 1–2 representative diffs that showcase behavior (mixin import removed,
  `setup()` injected, a composable patched — e.g. a generated `computed`, an
  added return key, a lifecycle hook converted),
- a one-line verdict per file, and a reminder that **changes are left in place**
  for review in their editor (`git -C <project> diff`).

Optionally validate hand-checked composables with `node --check <file.js>` and
confirm no migrated component still contains `mixins:` / `/mixins/`.

## Notes
- READY just means a matching composable file exists; the scoped run still does
  precise gap analysis and may **patch** the composable (add missing members /
  return keys / lifecycle hooks) — that's a feature to highlight, not a problem.
- If the runner reports "Nothing to migrate" for a component, it was already
  migrated or has no composable match — pick another.
- To undo everything afterward: `git -C <project> checkout -- .` (only when the
  developer asks; the default is to leave the diff for review).
