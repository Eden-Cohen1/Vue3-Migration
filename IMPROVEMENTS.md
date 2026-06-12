# IMPROVEMENTS.md — vue3-migration backlog

Living backlog of bugs and quality/DX improvements **in the vue3-migration tool**
(not in any project it migrates). Findings come from the `review-migration-output`
skill, from real runs, and from anything we stumble across. Add issues with the
`track-improvement` skill; **delete an issue the moment it's fixed**.

**How to pick one up (cold start):** scan the Index → read the block → follow
**Reproduce → Fix direction → Verify when fixed**. Every block is self-contained:
it names the symptom with file:line, the likely tool source, and how to confirm a
fix. Severity: 🔴 high · 🟠 med · 🟡 low.

**Conventions:** IDs are stable (prefix per category: CORR/RPT/CG/DX/PERF/TEST/DOCS) —
reference them in commits (`fix(<ID>): …`). Demo specimen for repro:
`/Users/base/Projects/dummy_vue_migration_project`.
Do not hand-edit the Index; run `track-improvement` (or `improvements.py reindex`).

## Index

<!-- INDEX:START -->
| ID | Sev | Category | Title | Status |
|----|-----|----------|-------|--------|
| [RPT-3](#rpt-3) | 🟡 low | Report Accuracy | Divergence false positives (pass-through helpers / equivalent booleans) erode trust in the section | open |
| [CG-3](#cg-3) | 🟡 low | Codegen Quality | Import removal / setup() injection leaves whitespace damage in components | open |
| [DX-1](#dx-1) | 🟡 low | DX / Ergonomics | Inline warning banner references an ambiguous, transient, un-co-located report file | open |

_3 open: 0 high, 0 med, 3 low._
<!-- INDEX:END -->

## Issues

<!-- ISSUES:START -->

<!-- ISSUE id=RPT-3 severity=low category=report status=open discovered=2026-06-08 source=review-migration-output -->
### RPT-3 · Divergence false positives (pass-through helpers / equivalent booleans) erode trust in the section

**🟡 low** · Report Accuracy · status: `open`

**Symptom**

Purely textual comparison flags behaviorally-identical code: `canCreate` — mixin `checkPermission('create')` vs composable `userPermissions.value.includes('create')`, identical because `checkPermission` is a one-line pass-through (`permissionMixin.js:43-45`). `hasError` `!!this.error` vs `error.value !== null` flagged though equivalent for the string/null error model.

**Reproduce**

See the canCreate/hasError entries in the divergence sections of the demo reports.

**Root cause / likely source**

`core/divergence_detector.py:normalize_for_comparison` does not inline trivial single-return pass-through helpers, nor normalize equivalent boolean coercions.

**Why it matters**

Noise sits next to genuinely dangerous flags (canEdit write-vs-update), lowering trust in the whole divergence list.

**Fix direction**

Inline single-`return` pass-through helpers before comparison (fixes canCreate — the clear true false positive). Optionally normalize `!!x` vs `x !== null` (lower priority; they differ on falsy-non-null values).

**Verify when fixed**

`canCreate` no longer appears as a divergence; `canEdit` (real difference) still does.
<!-- /ISSUE id=RPT-3 -->

<!-- ISSUE id=CG-3 severity=low category=codegen status=open discovered=2026-06-08 source=review-migration-output -->
### CG-3 · Import removal / setup() injection leaves whitespace damage in components

**🟡 low** · Codegen Quality · status: `open`

**Symptom**

When the mixin import was the only import: orphaned blank line right after `<script>` (`SearchBar.vue:95`) and no blank line before `export default {` (`SearchBar.vue:96-97`). `setup()` is injected with no leading blank line, so its placement varies across components (after `name` in StatsOverview, after `props` in BatchActions, after `emits` in SearchBar).

**Reproduce**

`sed -n '/<script>/,/export default/p' src/components/common/SearchBar.vue` after migration.

**Root cause / likely source**

`transform/injector.py:remove_import_line` (~L57-71) deletes the import without collapsing the orphaned blank; `add_composable_import` (~L30-54) and the no-setup branch (~L197-209) don't normalize surrounding spacing.

**Why it matters**

Whitespace churn enlarges diffs and makes the convention look inconsistent across a large codebase.

**Fix direction**

Normalize blank lines around the import block and before `export default`; emit `setup()` with a consistent leading blank line.

**Verify when fixed**

Migrated components have consistent spacing; add a golden/snapshot assertion.
<!-- /ISSUE id=CG-3 -->

<!-- ISSUE id=DX-1 severity=low category=dx status=open discovered=2026-06-08 source=review-migration-output -->
### DX-1 · Inline warning banner references an ambiguous, transient, un-co-located report file

**🟡 low** · DX / Ergonomics · status: `open`

**Symptom**

`useChart.js:1`, `usePermission.js:1`, `useSelection.js:1` all begin with `// ⚠️ N manual step(s) needed — see migration report for details`. It names no file, yet there are several timestamped, git-untracked `migration-report-*.md` at the project root, each covering different composables.

**Reproduce**

See the top comment of any patched composable after a migration.

**Root cause / likely source**

`core/warning_collector.py:inject_inline_warnings` (~L600-602) hard-codes the suffix with no filename/anchor; callers pass no path.

**Why it matters**

The actionable detail lives only in a transient, ambiguously-referenced file; once it's deleted/gitignored the banner is a dead pointer and the steps are unrecoverable.

**Fix direction**

Inline the specific step(s) in the banner (self-contained), or reference the exact report filename + anchor. The banner is regenerated idempotently, so a richer inline summary is safe.

**Verify when fixed**

The banner is self-explanatory without an external file, or names the exact report it refers to.
<!-- /ISSUE id=DX-1 -->

<!-- ISSUES:END -->
