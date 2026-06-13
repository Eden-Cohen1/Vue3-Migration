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
| [DX-2](#dx-2) | 🟡 low | DX / Ergonomics | Migration-report filenames collide at second granularity → reports silently overwritten in batch/multi-component runs | open |

_1 open: 0 high, 0 med, 1 low._
<!-- INDEX:END -->

## Issues

<!-- ISSUES:START -->

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
