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
| [CORR-5](#corr-5) | 🔴 high | Correctness / Behavior | Composable inline banner clobbered to "✅ 0 issues" when a shared composable is re-patched by a later component — ships crashing this.$el/$forceUpdate under a green banner | open |
| [CORR-6](#corr-6) | 🔴 high | Correctness / Behavior | Inlined lifecycle/method body keeps this.<component-prop> unconverted → silent runtime crash in the composable, no warning | open |
| [DX-2](#dx-2) | 🟡 low | DX / Ergonomics | Migration-report filenames collide at second granularity → reports silently overwritten in batch/multi-component runs | open |

_3 open: 2 high, 0 med, 1 low._
<!-- INDEX:END -->

## Issues

<!-- ISSUES:START -->

<!-- ISSUE id=CORR-5 severity=high category=correctness status=open discovered=2026-06-08 source=review-migration-output -->
### CORR-5 · Composable inline banner clobbered to "✅ 0 issues" when a shared composable is re-patched by a later component — ships crashing this.$el/$forceUpdate under a green banner

**🔴 high** · Correctness / Behavior · status: `open`

**Symptom**

After a component flow over all READY components, useTheme.js:1 carries `// ✅ 0 issues — all mixin members have composable equivalents` while its applyTheme body (useTheme.js ~L56-60) still contains `this.$el`, `this.$el.style`, and `this.$forceUpdate()` (3 occurrences) — code that throws because `this` is undefined in a composable. The early migration reports (migration-report-20260608-210820/210841/210844.md) correctly tier the SAME composable as `🔴 [useTheme] — 1 step (Replace this.$el)`. Banner (✅) and report (🔴) contradict. 8 of 13 patched composables in the run show this banner-vs-report mismatch (useChart, useComment, useExport, useFilter, useForm, useNotification, usePagination, useTheme).

**Reproduce**

From a clean clone of the demo: (1) `python3 -m vue3_migration --root <demo> component src/components/layout/ThemeSwitcher.vue` (apply) → useTheme banner is `⚠️ 1 manual step` and the code gains applyTheme with this.$el (grep -c 'this\.\$el\|this\.\$forceUpdate' src/composables/useTheme.js == 3). (2) `python3 -m vue3_migration --root <demo> component src/components/layout/AppHeader.vue` (apply) → the SAME grep is STILL 3 but `head -1 src/composables/useTheme.js` has flipped to `// ✅ 0 issues`. The clobber happens on the 2nd component that re-patches an already-covered member.

**Root cause / likely source**

transform/composable_patcher.py:765 calls core/warning_collector.py:suppress_covered_warnings (L234-266), which treats a member as "covered" (its in-body warnings "moot") when the composable merely declares AND returns it (L257 `covered = set(declared) & set(returns)`). But the patcher inlines mixin bodies VERBATIM including unconverted this.* — so "covered" ≠ "clean". On the 2nd+ component sharing the composable, applyTheme is already covered → its this.$el warning is suppressed → inject_inline_warnings (warning_collector.py:684) rebuilds the banner via build_banner_header(count_manual_steps([])) = "✅ 0 issues", clobbering the earlier ⚠️. The final reconciliation the code comments promise (warning_collector.py:682 "see _reconcile_composable_banners") does NOT exist — grep finds no such definition — so the provisional per-run banner is never reconciled against the cumulative/report tier.

**Why it matters**

The inline banner is the first thing a developer reads in the migrated file; it affirmatively says "0 issues — all mixin members have composable equivalents" on a composable that throws at runtime, and contradicts the report. This is a regression of the RPT-1 "banner and report never disagree" invariant, but only in the multi-component case (a composable shared by ≥2 migrated components) — which is the common case at project scale, so the banner is unreliable exactly when it matters most.

**Fix direction**

Either (a) implement the promised final reconciliation pass: after all components are processed, recompute each composable's banner from the cumulative warning set / final report tier (single source of truth), or (b) make suppression body-aware — in suppress_covered_warnings, do NOT suppress a covered member's warning if that member's body in the on-disk composable still contains the unconvertible construct (re-scan the composable member body, not just check declared+returned). Keep RPT-1's shared count_manual_steps but feed it the body-verified, cumulative warnings.

**Verify when fixed**

tests/test_composable_patcher.py (or integration): patch a composable adding a member whose body has this.$el (expect banner ⚠️ / report 🔴); patch the SAME composable again from a second component that already-covers that member; assert the banner is STILL ⚠️ (not ✅) and equals the report tier. Add a warning_collector unit test: suppress_covered_warnings must NOT drop a warning whose line is inside a covered member whose composable body still contains the construct.
<!-- /ISSUE id=CORR-5 -->

<!-- ISSUE id=CORR-6 severity=high category=correctness status=open discovered=2026-06-08 source=review-migration-output -->
### CORR-6 · Inlined lifecycle/method body keeps this.<component-prop> unconverted → silent runtime crash in the composable, no warning

**🔴 high** · Correctness / Behavior · status: `open`

**Symptom**

Migrating TaskComments.vue patches useComment.js with a generated onMounted (useComment.js ~L75-79): `onMounted(() => { if (this.entityId) { loadComments(this.entityId) } })`. `entityId` is a COMPONENT PROP (TaskComments.vue:205 `props: { entityId }`), not a mixin member, so it was left as raw `this.entityId`. In a composable `this` is undefined → the onMounted callback throws `Cannot read properties of undefined (reading 'entityId')` on mount. There is NO report manual-step, NO inline `// ⚠️` annotation on the line, and the file banner reads `✅ 0 issues`. (Contrast: this.$el/$forceUpdate at least get a report step + recipe; a bare this.<prop> is fully silent.)

**Reproduce**

`python3 -m vue3_migration --root <demo> component src/components/tasks/TaskComments.vue` (apply). Then `sed -n '/onMounted/,/})/p' src/composables/useComment.js` shows `if (this.entityId)`. Source of the hook: commentMixin.js:107-110 `mounted() { if (this.entityId) this.loadComments(this.entityId) }`. `grep -rn entityId migration-report-*.md | grep -iE 'step|warn|⚠'` returns nothing → unflagged.

**Root cause / likely source**

transform/this_rewriter.py:rewrite_this_refs (L171) only rewrites `this.<X>` for X in the known mixin members; its own docstring (L180) states `this.unknown -> this.unknown (best-effort: left unchanged)`. A `this.<identifier>` resolving to a component prop/data (external to the mixin) is left verbatim AND no warning is emitted — core/warning_collector.py has detectors for this.$emit/$refs/$el/external-dependency but none for a residual bare `this.<componentMember>` in an inlined hook/member body. The mounted() body is inlined via the generator/patcher hook path without resolving or flagging this.entityId.

**Why it matters**

Generated composable code crashes at runtime with zero warning and a ✅ banner — a silent violation of the "never ship code you can't replace" invariant. Any mixin lifecycle hook or method that reads a component prop / injected value produces this; lifecycle hooks are worst because they run on mount.

**Fix direction**

After this-rewriting an inlined hook/member body, scan for any residual `this.<identifier>` that is non-$ and not a known mixin member. Emit an error/warning-severity warning ("this.<x> refers to component-provided state not available in a composable — pass it as a parameter") + an inline annotation, and feed it into the banner/report count. Optionally hoist such identifiers into the composable's parameter list (e.g. `useComment(entityId)`).

**Verify when fixed**

tests/test_this_rewriter.py / test_warning_collector.py: a mixin mounted() that reads a non-mixin `this.foo` yields a warning and the residual line is annotated. Integration assertion on TaskComments → useComment: the generated onMounted this.entityId is flagged (not silent), banner is not ✅.
<!-- /ISSUE id=CORR-6 -->

<!-- ISSUE id=DX-2 severity=low category=dx status=open discovered=2026-06-08 source=review-migration-output -->
### DX-2 · Migration-report filenames collide at second granularity → reports silently overwritten in batch/multi-component runs

**🟡 low** · DX / Ergonomics · status: `open`

**Symptom**

A component flow over 84 READY components produced only 76 `migration-report-*.md` files — 8 were silently overwritten. Reports are named `migration-report-YYYYMMDD-HHMMSS.md`; any two migrations that finish in the same wall-clock second resolve to the same path and the later clobbers the earlier. Lost reports = lost audit trail (e.g. the early `🔴 useTheme` tiering now survives in only 3 of the themeMixin runs' reports).

**Reproduce**

From a clean demo, run the component command across many components quickly: `python3 .claude/skills/demo-migration/scripts/run_demo.py --components 200`, then `ls migration-report-*.md | wc -l` is LESS than the number of MIGRATED runs reported in the log (76 vs 81 here).

**Root cause / likely source**

reporting/diff.py:177-178 — `timestamp = now.strftime("%Y%m%d-%H%M%S")` then `report_path = project_root / f"migration-report-{timestamp}.md"`. No uniqueness suffix and no collision guard, so same-second writes overwrite. (cli.py:530 builds the same second-granularity stamp for the status report.)

**Why it matters**

In batch/CI/scripted usage the migration report — a primary deliverable carrying warnings, manual steps, and divergences — is silently lost, and there is no signal that a report was clobbered. Undermines the "the report is the deliverable" model the demo/skills rely on.

**Fix direction**

Make the filename collision-proof in reporting/diff.py: if the path exists, append a short counter (`-002`) or use sub-second precision (`-HHMMSS-mmm`); never overwrite an existing report. Alternatively, for a multi-component invocation, write one consolidated report. Apply the same guard to the status report path in cli.py:530.

**Verify when fixed**

Unit test: writing two reports within the same second yields two distinct files (no overwrite). Integration: N migrations produce N distinct report files.
<!-- /ISSUE id=DX-2 -->

<!-- ISSUES:END -->
