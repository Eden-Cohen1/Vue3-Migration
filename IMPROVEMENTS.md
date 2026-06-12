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
| [RPT-2](#rpt-2) | 🟠 med | Report Accuracy | Divergence 'composable Lxx' vscode links are off by the inserted header/import line count | open |
| [RPT-3](#rpt-3) | 🟡 low | Report Accuracy | Divergence false positives (pass-through helpers / equivalent booleans) erode trust in the section | open |
| [CG-1](#cg-1) | 🟠 med | Codegen Quality | Private `_`-prefixed scratch state leaked into the composable's public `return {}` | open |
| [CG-2](#cg-2) | 🟡 low | Codegen Quality | Propagated mixin import lands above `vue` with two stray blank lines | open |
| [CG-3](#cg-3) | 🟡 low | Codegen Quality | Import removal / setup() injection leaves whitespace damage in components | open |
| [DX-1](#dx-1) | 🟡 low | DX / Ergonomics | Inline warning banner references an ambiguous, transient, un-co-located report file | open |

_6 open: 0 high, 2 med, 4 low._
<!-- INDEX:END -->

## Issues

<!-- ISSUES:START -->

<!-- ISSUE id=RPT-2 severity=med category=report status=open discovered=2026-06-08 source=review-migration-output -->
### RPT-2 · Divergence 'composable Lxx' vscode links are off by the inserted header/import line count

**🟠 med** · Report Accuracy · status: `open`

**Symptom**

Composable line links in divergence sections are computed pre-patch, but the header (`// ⚠️ ...`) and rewritten imports are prepended afterward. e.g. report links `prepareChartData` to 'composable L23-33' but it is at `useChart.js:27-37` (off by 4); `canEdit` 'L11' → `usePermission.js:12` (off by 1). Mixin-side links are correct.

**Reproduce**

Open a migration-report divergence link for a PATCHED composable; it lands a few lines above the actual member.

**Root cause / likely source**

`divergence_detector.py:detect_divergences` records `composable_lines` from the pre-patch read (`auto_migrate_workflow.py:176`); `warning_collector.py:inject_inline_warnings` prepends header lines later; `reporting/markdown.py:_build_divergence_section` (~L1616-1619) applies no offset.

**Why it matters**

The report's headline value is clickable jump-to-member; every composable link opens the wrong line, eroding trust in the report.

**Fix direction**

Offset `composable_lines` by the number of lines the patcher prepends (header + propagated imports), or compute links against the final on-disk file.

**Verify when fixed**

A patched composable's divergence link resolves to the member's actual post-patch line.
<!-- /ISSUE id=RPT-2 -->

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

<!-- ISSUE id=CG-1 severity=med category=codegen status=open discovered=2026-06-08 source=review-migration-output -->
### CG-1 · Private `_`-prefixed scratch state leaked into the composable's public `return {}`

**🟠 med** · Codegen Quality · status: `open`

**Symptom**

`useChart.js` declares `const _debouncedResize = ref(null)` and returns `_debouncedResize` — mixin-internal scratch (only used inside lifecycle hooks); no component references it.

**Reproduce**

Migrate StatsOverview, then `grep -n '_debouncedResize' src/composables/useChart.js` shows it in the `return {}`.

**Root cause / likely source**

`transform/composable_patcher.py:add_keys_to_return` (~L688) adds every lifecycle dependency to the return with no underscore/usage filtering. Same unfiltered behavior in `transform/composable_generator.py` (~L419).

**Why it matters**

Widens the public API surface with an internal, violates the underscore-private convention, and is silent in the report.

**Fix direction**

Filter `_`-prefixed and/or component-unused members out of the return set in `add_keys_to_return` (and apply the generator's component-scoping to the patch path); keep them function-local consts.

**Verify when fixed**

After migration `_debouncedResize` is declared but NOT returned; the component still works.
<!-- /ISSUE id=CG-1 -->

<!-- ISSUE id=CG-2 severity=low category=codegen status=open discovered=2026-06-08 source=review-migration-output -->
### CG-2 · Propagated mixin import lands above `vue` with two stray blank lines

**🟡 low** · Codegen Quality · status: `open`

**Symptom**

`useChart.js:1-5` — header, `import { debounce } from '@/utils/helpers'`, two blank lines, then `import { ... } from 'vue'`. The propagated import is placed ABOVE the framework import.

**Reproduce**

`sed -n '1,6p' src/composables/useChart.js` after migrating a component whose mixin imports a helper.

**Root cause / likely source**

`core/mixin_analyzer.py` (~L347) import regex ends with `\s*;?` and the `\s*` swallows the trailing `\n\n`; `transform/composable_patcher.py` (~L749) does `content = rewritten_line + "\n" + content`, adding another newline and always prepending to the file top.

**Why it matters**

Ships orphaned whitespace + non-conventional import order; trips Prettier / no-multiple-empty-lines.

**Fix direction**

`rstrip()` the captured import line (re-add a single `\n`), and MERGE the propagated import into the existing import block instead of prepending to the file top.

**Verify when fixed**

Migrated composable has a single import block (vue first or sensibly grouped) and no double blank lines.
<!-- /ISSUE id=CG-2 -->

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
