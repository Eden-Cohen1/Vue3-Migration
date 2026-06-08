---
name: review-migration-output
description: >-
  Review the vue3-migration tool's OUTPUT on the demo Vue project (default:
  /Users/base/Projects/dummy_vue_migration_project) to find bugs and developer-
  experience improvements IN THE TOOL. Reads the working-tree migration diff
  (migrated components + patched/generated composables) and the
  `migration-report-*.md` files, finds correctness/codegen/report/DX issues,
  verifies them, and ties each back to the tool's source so it's actionable.
  Run it AFTER demo-migration (or any real migration) on that repo. Triggers on:
  "analyze the migration diff", "review the tool's output", "find issues in what
  the tool generated", "what bugs does the migration have", "critique the
  migration results". NOT for running the migration (use demo-migration) and NOT
  for proving a specific fix against fixtures (use verify-migration).
---

# review-migration-output — turn the demo diff into tool-improvement findings

Goal: treat the demo project's current migration output as a **specimen of the
tool's behavior** and mine it for things to fix or improve in `vue3-migration`.
The deliverable is a prioritized, verified findings list where each item names
the symptom (with file:line in the demo repo) **and** the likely source module
in the tool — so it becomes a real backlog, not vibes.

Pairs with **demo-migration** (which produces the output) and is distinct from
**verify-migration** (which proves one change against copied fixtures).

## Principles

1. **Review the OUTPUT, not the demo repo's own code.** The demo's mixins are
   intentionally messy specimens. Findings are about what the *tool* did with
   them (codegen, patching, reporting), not about the fixtures being imperfect.
2. **Verify before reporting.** Every candidate is a hypothesis. Confirm it from
   the actual diff/report text (and, for behavior claims, from the mixin source).
   Distinguish a real bug from expected, documented behavior.
3. **Tie each finding to the tool's source.** Grep `vue3_migration/` for the
   responsible code (e.g. import spacing → `transform/injector.py`; return-key
   building → `transform/composable_patcher.py`; report wording →
   `reporting/markdown.py`; divergence logic → `core/divergence_detector.py`).
   A finding without a source pointer is half-done.
4. **Separate correctness from polish.** Rank: behavior-changing bugs >
   report-accuracy bugs > codegen quality > DX/ergonomics nits.
5. **Be honest about fixture bias.** "No issues found in this run" is a valid
   outcome; don't invent problems.

## Procedure

### 1. Collect evidence
The demo project is resolved portably ($VUE3_DEMO_PROJECT → sibling
`dummy_vue_migration_project` next to this repo → fallback); override with `--root`.
Clone `Eden-Cohen1/dummy_vue_migration_project` beside this repo to use this skill
on another machine.
```bash
python3 .claude/skills/review-migration-output/scripts/collect_evidence.py
# add --root <path> for a different project, --json for machine-readable
```
This prints the changed-file list, the full `git diff`, the reports, the mixin
sources to diff against, and **mechanical candidate findings** (formatting
regressions, leaked private members, leftover `this.`, syntax validity, and the
report "no manual steps needed" vs. "Implementation Divergences" contradiction).
Mechanical flags are starting points — verify each.

### 2. Review across dimensions
Cover all of these (fan out one reviewer per dimension when orchestration is
available — this is broad enough to parallelize; otherwise go through them in
order). For each, read the real diff/report/mixin text:

- **Codegen correctness** — Does the generated/patched composable behave like the
  mixin? Leftover `this.`; wrong/missing `.value`; missing or misordered imports;
  lifecycle conversion correctness; duplicate identifiers in `setup()`.
- **Behavior preservation** — Did the migration *drop* behavior while still
  applying? e.g. a composable member that is a **stub** vs. the mixin's real
  body; a dropped `this.$emit`; a missing `.reverse()`/filter. The tool may flag
  these as "divergences" — check whether the framing is loud enough given the
  migration was applied.
- **Divergence accuracy** — Are flagged divergences real? Any **false positives**
  (semantically-equivalent code flagged, e.g. `!!x` vs `x !== null`)? Any
  **missed** divergences (real logic difference not flagged)?
- **Report accuracy & framing** — Contradictions (divergences under "no manual
  steps needed"), wrong command names, broken `file:line` links, duplicated
  recipe blocks, confidence label vs. actual content mismatch.
- **Codegen quality** — Stray blank lines, import ordering/placement, `setup()`
  position consistency across components, **private `_member` leaked into the
  public `return`**, inline warning comments that couple a file to an external
  report.
- **Idempotency & safety** — Would re-running corrupt anything? Was a mixin
  removed without a working replacement? (Cross-check the DEVELOPMENT.md invariants.)
- **Developer experience** — Is the report actionable at a glance? Is the noise
  level right? Are next steps obvious? What would make the diff easier to trust?

### 3. Verify each candidate
Confirm the symptom in the text; for behavior claims, compare against the mixin
source the collector listed. Write a one-line proof (the exact lines that show
it). Drop anything you can't substantiate or that is documented expected behavior.

### 4. Attribute to source
For each surviving finding, grep `vue3_migration/` and name the module/function
most likely responsible, so the fix has a starting point.

### 5. Report
Produce a prioritized list. Per finding:
- **Title** + severity (correctness / report / codegen / DX).
- **Symptom** with a demo-repo `file:line` (or report excerpt).
- **Why it matters** (impact on a real migration).
- **Likely source** in `vue3_migration/...` + a suggested direction.
End with a short "quick wins vs. deeper fixes" split so the developer can triage.

## Notes
- Read DEVELOPMENT.md / ARCHITECTURE.md first — many findings map to a stated
  invariant or a known limitation (don't re-report known limitations as bugs;
  do flag invariant violations loudly).
- The collector only reads; it never edits. Reviewing does not change the demo
  diff, so the developer's review state is preserved.
- If there's no current migration diff, run `demo-migration` first (or point
  `--root` at a project that has one).
