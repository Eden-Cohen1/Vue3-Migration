---
name: track-improvement
description: >-
  Record or resolve entries in IMPROVEMENTS.md — the vue3-migration tool's
  improvement backlog (bugs, codegen/report/DX issues to fix in the tool). Use
  this to ADD a new issue with enough context that a future cold session can pick
  it up and start working, and to CLOSE (delete) an issue the moment it's fixed.
  Triggers on: "log an improvement", "add this to the backlog / IMPROVEMENTS",
  "track this bug", "record what we found", "mark CORR-1 fixed", "close/remove
  that issue", "what's in the backlog". After the review-migration-output skill,
  use this to persist its findings. NOT for running or reviewing a migration.
---

# track-improvement — maintain IMPROVEMENTS.md

`IMPROVEMENTS.md` (repo root) is the durable backlog of things to fix **in the
vue3-migration tool**. It survives across sessions, so each entry must be
self-contained enough to pick up cold. This skill adds entries in that structure
and **deletes them when solved** — open issues only ever live in the file.

All operations go through the manager script so IDs stay stable and the Index
stays in sync:
```
python3 .claude/skills/track-improvement/scripts/improvements.py <cmd>
```

## The non-negotiables

1. **Delete-on-solve.** When an issue is fixed, run `close <ID>` — it removes the
   block AND its Index row. A "Done/Closed" section is NOT kept; git history is
   the record. The backlog only contains open work.
2. **Every issue is pickup-ready cold.** A future session with zero context must
   be able to act from the block alone. All six fields are required:
   `symptom` (with concrete `file:line`), `repro` (exact commands), `root_cause`
   (the tool module/function — grep `vue3_migration/` to name it), `impact`,
   `fix` (a direction, not just "fix it"), `verify` (how to confirm + the test to add).
3. **Tool issues only.** Bugs/improvements in `vue3_migration/`, not in any demo
   project. The demo (`/Users/base/Projects/dummy_vue_migration_project`) is only
   the repro specimen.
4. **Never hand-edit the Index.** It is regenerated; run the script.

## Add an issue

1. Gather the six fields. If you don't yet have a `root_cause`, grep the tool
   source to find the responsible code before recording — a finding without a
   source pointer is half-done. Pick a `category`
   (`correctness|report|codegen|dx|perf|test|docs`) and `severity`
   (`high|med|low`).
2. Build a JSON object (or an array for several) and pipe it in — the script
   assigns the next stable ID, inserts it in category order, and reindexes:
```bash
echo '{"category":"codegen","severity":"low","title":"...",
  "symptom":"... file.vue:42 ...","repro":"run ...","root_cause":"transform/injector.py:remove_import_line",
  "impact":"...","fix":"...","verify":"add test ...","source":"manual"}' \
| python3 .claude/skills/track-improvement/scripts/improvements.py add --stdin
```
   (Use `--file path.json` for a prepared batch; `source` defaults to `manual`,
   date defaults to today.)
3. Confirm with `validate` and `list`.

## Close an issue (when fixed)

```bash
python3 .claude/skills/track-improvement/scripts/improvements.py close CORR-1
# multiple at once: ... close CORR-1 CG-2
```
Then reference the ID in the fix commit: `fix(CORR-1): …`.

## Other commands
- `list [--category C]` — overview (id · sev · category · status · title).
- `get <ID>` — print one full block (use before starting work on it).
- `status <ID> <open|wip|blocked>` — mark progress (e.g. `wip` when you start).
- `reindex` — rebuild the Index if it ever drifts.
- `validate` — parse all blocks, check unique IDs + required sections (run after edits).

## Notes
- Persisting `review-migration-output` findings: have that skill emit each finding
  as the JSON spec above and batch-`add` them. Skip anything already in the file
  (check `list` first to avoid duplicates).
- Format is one file, machine-parseable via `<!-- ISSUE id=… -->` … `<!-- /ISSUE id=… -->`
  delimiters with a regenerated `<!-- INDEX -->` table. The block body is plain
  markdown; humans read it directly, the script edits by ID.
