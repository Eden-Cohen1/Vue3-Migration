# Manual Verification Guide — Report Accuracy Fixes

## Quick Start

```bash
python tests/fixtures/verify_report.py
```

Opens: `tests/fixtures/dummy_project/VERIFY-REPORT.md`

---

## Issue 1: `skipped-lifecycle-only` for already-converted hooks

**Fixture:** `chartMixin.js` → `useChart.js` (pre-existing composable with `onMounted`/`onBeforeUnmount`) → `ChartTest.vue`

**Look at:** Search `useChart` in VERIFY-REPORT.md

**Expect:**
- `useChart` appears with 1 step: `this.$refs` only
- NO step says `skipped-lifecycle-only`
- NO step says "Manually convert lifecycle hooks"

**Edge case:** The composable already has `onMounted()` and `onBeforeUnmount()` — these should NOT trigger a manual conversion warning.

---

## Issue 2: Report lists steps for non-existent composables

**Fixture:** `pollingMixin.js` → NO pre-existing composable → `PollingTest.vue` (uses zero members)

**Look at:** Search `usePolling` in VERIFY-REPORT.md

**Expect:**
- If `usePolling` appears, it should only show REAL warnings (e.g., `external-dependency` for `_pollCallback`)
- NO step says `skipped-lifecycle-only`
- NO "Unused members" section for a composable that was never generated

**Edge case:** pollingMixin has lifecycle hooks but PollingTest.vue uses NO members. If the tool generates a standalone composable, the entry may still appear — but `skipped-lifecycle-only` must never be a step.

---

## Issue 3: `this.$once` mislabeled as `this.$on`

**Fixture:** `eventBusMixin.js` → `EventBusTest.vue`

**Look at:** Search `useEventBus` in VERIFY-REPORT.md

**Expect:**
- Step for `this.$on` lists ONLY `$on` lines (e.g., L10, L11, L12) — NOT the `$once` line
- Step for `this.$once` appears as a SEPARATE step with its own line ref (e.g., L16)
- Recipe section has BOTH `this.$on` and `this.$once` as separate entries

**Edge case:** L16 in the composable is `this.$once(...)` — it must NOT appear in the `this.$on` step.

---

## Issue 4: `this.$watch` always references "mixin L1"

**Fixture:** `watcherMixin.js` (line 1 is a comment containing "this.$watch") → `WatcherTest.vue`

**Look at:** Search `useWatcher` in VERIFY-REPORT.md, and also check `kitchenSinkMixin` entries

**Expect:**
- `useWatcher` step for `this.$watch` shows real line numbers (L32 in composable, or mixin L28/L34/L44)
- NOT "mixin L1" (which is the comment line)
- For `kitchenSinkMixin`: `this.$watch` shows `mixin L98, mixin L101, mixin L106, mixin L109`

**Edge case:** Line 1 of watcherMixin.js is `// Issue 4: this.$watch with ALL variants` — the comment contains the pattern, but detection should skip it.

---

## Quick Checklist

```
python tests/fixtures/verify_report.py
```

Then open `tests/fixtures/dummy_project/VERIFY-REPORT.md` and check:

- [ ] Issue 1: `useChart` has NO `skipped-lifecycle-only` step
- [ ] Issue 2: `usePolling` has NO `skipped-lifecycle-only` step
- [ ] Issue 3: `useEventBus` has SEPARATE steps for `this.$on` and `this.$once`
- [ ] Issue 3: `this.$on` line refs do NOT include the `$once` line
- [ ] Issue 4: `useWatcher` line refs are NOT "mixin L1"
- [ ] Issue 4: `kitchenSinkMixin` `this.$watch` shows mixin L98, L101, L106, L109

## Cleanup

After verification, delete the generated report:

```bash
rm tests/fixtures/dummy_project/VERIFY-REPORT.md
```
