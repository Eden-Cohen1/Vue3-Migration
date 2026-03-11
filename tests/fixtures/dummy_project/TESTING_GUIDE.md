# Manual Testing Guide — All 9 Tasks

This guide uses the verify fixtures (`verifyMixin.js`, `orphanMixin.js`, `VerifyFull.vue`, `VerifyEmpty.vue`) to manually confirm every bug fix and improvement.

---

## Setup

```bash
# Run full migration on the dummy project (preview only, no writes)
python -m vue3_migration all tests/fixtures/dummy_project

# Or generate a read-only report
python -m vue3_migration status tests/fixtures/dummy_project
```

Both commands produce a migration report. The `all` command also shows component diffs.

---

## Task 1: Auto-remove unused mixin imports

**What changed:** Components that import a mixin but use zero of its members get the import and `mixins` array entry automatically removed.

**How to test:**
1. Run `python -m vue3_migration all tests/fixtures/dummy_project`
2. Look at the diff for **VerifyEmpty.vue**

**What to look for in the diff:**
- `import verifyMixin from '../mixins/verifyMixin'` — **removed**
- `mixins: [verifyMixin]` — **removed**
- The rest of the component (`data()`, `<template>`) stays untouched
- No `setup()` function added (nothing to inject)

**In the report (Action Plan):**
- VerifyEmpty.vue should show an info note: "imported but unused — removed"

---

## Task 2: Better external dependency suggestions

**What changed:** External dependency warnings now list 3 alternatives instead of just "pass as composable parameter".

**How to test:**
1. Open the migration report
2. Find the **verifyMixin** section in the Action Plan
3. Look for the `external-dependency` warning about `externalItems`

**What to look for:**
The action_required text should list all 3 options:
1. Pass as a **composable parameter** (`useVerify(externalItems)`)
2. Accept as a **function argument** (if only used in one method)
3. **Import from another composable** (e.g., `useStore()`)

**In Migration Patterns section:**
- Find the "External Dependencies" pattern — it should show before/after examples for all 3 approaches

---

## Task 3: Flag unused mixins for deletion

**What changed:** Mixins not imported by any component are flagged as safe to delete.

**How to test:**
1. Open the migration report
2. Search for **orphanMixin**

**What to look for:**
- A clear warning: "No component imports 'orphanMixin'. This mixin file can be safely deleted."
- Action: "Delete the mixin file or keep it if used outside this project"
- It should appear in a dedicated section or be clearly distinguished from actively-used mixins

---

## Task 4: Report restructuring

**What changed:** Section order is now Summary → Action Plan → Migration Patterns. Summary is enhanced with friendly language.

**How to test:**
1. Open the migration report
2. Check the section order from top to bottom

**What to look for:**
- **First section after the header:** Summary with counts like:
  - "🟢 **N** can be applied as-is — no manual steps needed"
  - "🟡 **N** need manual attention before the migration is complete"
- **Second section:** Action Plan (per-component guides)
- **Last major section:** "Migration Patterns" (NOT "Migration Recipes")
- The old name "Migration Recipes" should appear **nowhere** in the report

---

## Task 5: Redesigned info section per composable

**What changed:** The messy info dump at the end of each composable step is now grouped and readable.

**How to test:**
1. Open the migration report → Action Plan
2. Find the **verifyMixin / useVerify** composable section under VerifyFull.vue

**What to look for:**
- **Unused members** grouped together: `neverUsedFlag`, `neverUsedHelper`, `neverUsedComputed` listed with "consider removing from composable return"
- **Overridden members** grouped: `status` listed with "composable version won't be used" (since VerifyFull.vue defines its own `status` in data)
- Clean formatting — no collapsed/expandable blocks, just clear bullet groups

---

## Task 6: Member usage accuracy

**What changed:** `find_used_members()` now correctly handles multiple `<script>` blocks and nested `<template>` tags.

**How to test:**
1. In the report, check **VerifyFull.vue**'s member analysis
2. Members used in the template: `query` (v-model), `hasResults` (v-if), `results` (interpolation), `search` (@click), `clearSearch` (@click), `status` (interpolation)

**What to look for:**
- `query`, `hasResults`, `results`, `search`, `clearSearch`, `status` should all be detected as **used**
- `neverUsedFlag`, `neverUsedHelper`, `neverUsedComputed` should be flagged as **unused** (they genuinely aren't used in VerifyFull.vue)
- No false positives — members shouldn't be incorrectly marked as used or unused

---

## Task 7: self=this inline comments on ALL usage lines

**What changed:** When `const self = this` exists, inline warning comments now appear on the declaration line AND every `self.x` usage line.

**How to test:**
1. Run `python -m vue3_migration all tests/fixtures/dummy_project`
2. Look at the generated composable for verifyMixin (usually `useVerify.js`)
3. Find the `search()` method

**What to look for in the composable code:**
- Line with `= this` → has `⚠️` inline comment (declaration)
- Line with `self.status = 'searching'` → has `⚠️` inline comment
- Line with `self.results = ...` → has `⚠️` inline comment
- Line with `self.query` → has `⚠️` inline comment
- Line with `self.status = 'done'` → has `⚠️` inline comment
- **Every single `self.` line** should have a comment like "self.x won't auto-rewrite — use direct refs"

**What should NOT happen:**
- Only the `const self = this` line getting a comment while usage lines are bare

---

## Task 8: Line references on all action plan warnings

**What changed:** Every warning in the action plan now has a clickable line reference (VS Code link format).

**How to test:**
1. Open the migration report → Action Plan
2. Find the verifyMixin section under VerifyFull.vue
3. Check each warning for line links

**What to look for — each warning type should have a line link:**

| Warning | Expected link target |
|---------|---------------------|
| `this.$emit('searched', ...)` | Line in composable or mixin showing `this.$emit` |
| `this.$router.push(...)` | Line in composable or mixin showing `this.$router` |
| `external-dependency: externalItems` | Line where `externalItems` is referenced |
| `this-alias: const self = this` | Line with `= this` declaration |
| `mixin-option: props` | Line in mixin where `props` is defined |
| `data-setup-collision: status` | Relevant line |

**Fallback behavior:**
- If the pattern can't be found in the composable (e.g., because `this_rewriter` already transformed it), the link should fall back to the **mixin source file** with label like "mixin L45"
- No warning should appear without any line reference at all

---

## Task 9: Better data-setup-collision explanation

**What changed:** The collision warning now explains Vue 3 shadowing behavior clearly.

**How to test:**
1. Open the migration report → Action Plan
2. Find VerifyFull.vue → look for the `status` collision warning

**What to look for:**
- Message explains: `status` is returned by both `setup()` and `data()`, and in Vue 3, `data()` properties **shadow** `setup()` return values
- Action tells you: remove `status` from `data()` to use the composable value, OR remove from composable if you want the component's version
- Should NOT be a cryptic technical message — should be clearly actionable

**In Migration Patterns section:**
- Find "Data / Setup Collision" pattern — should show before/after code demonstrating the fix

---

## Quick Checklist

Run this to verify everything at once:

```bash
# Generate report
python -m vue3_migration status tests/fixtures/dummy_project > /tmp/report.md

# Check in order:
# □ Task 4: Summary at top, "Migration Patterns" at bottom
# □ Task 3: orphanMixin flagged for deletion
# □ Task 5: Grouped info sections (unused/overridden)
# □ Task 9: data-setup-collision explains shadowing
# □ Task 2: external-dep shows 3 alternatives
# □ Task 8: All warnings have line links

# Run full migration (preview)
python -m vue3_migration all tests/fixtures/dummy_project

# Check diffs:
# □ Task 1: VerifyEmpty.vue — import and mixins entry removed
# □ Task 7: Composable has ⚠️ on ALL self.x lines

# Run automated tests to confirm no regressions
pytest tests/ -v
```
