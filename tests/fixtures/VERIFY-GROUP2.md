# Manual Verification: Group 2 — Code Generation & Detection Bugs

Run each test from the project root (`c:\Users\eden7\projects\vue3-migration`).

---

## Bug 1: Factory Function Parameters (sortMixin)

**Run:**
```bash
echo "y" | python -m vue3_migration mixin sortMixin tests/fixtures/dummy_project
```

**Look at:** `tests/fixtures/dummy_project/src/composables/useSort.js`

**Expect:**
- Line ~4: `export function useSort(defaultKey = 'name')` — params forwarded from factory function
- Line ~5: `const sortKey = ref(defaultKey)` — variable wrapped in `ref()`, NOT `let sortKey = defaultKey`
- Line ~6: `const sortOrder = ref('asc')` — literal values still wrapped correctly
- All `this.sortKey` rewritten to `sortKey.value` (check `toggleSort`, `clearSort`)

**Should NOT appear:**
- `let sortKey = defaultKey` (plain variable without ref)
- `export function useSort()` (empty params)

**Clean up:**
```bash
rm tests/fixtures/dummy_project/src/composables/useSort.js
rm migration-report-*.md
```

---

## Bug 2: Method Body Extraction (eventBusMixin)

**Run:**
```bash
rm -f tests/fixtures/dummy_project/src/composables/useEventBus.js
echo "y" | python -m vue3_migration mixin eventBusMixin tests/fixtures/dummy_project
```

**Look at:** `tests/fixtures/dummy_project/src/composables/useEventBus.js`

**Expect:**
- `function handleDataUpdate(payload)` body contains `receivedEvents.value.push({ type: 'data-updated', payload })`
- `function handleUserAction(action)` body contains `receivedEvents.value.push({ type: 'user-action', payload: action })`

**Should NOT appear:**
- `'data-updated': handleDataUpdate,` inside `handleUserAction` body (object-literal syntax)
- `'user-action': handleUserAction` as the body of any function

**Edge case:** The `registerEvents()` method contains `this.eventHandlers = { 'data-updated': this.handleDataUpdate, 'user-action': this.handleUserAction }` — the extraction must skip these references and find the real method declarations.

**Clean up:**
```bash
rm tests/fixtures/dummy_project/src/composables/useEventBus.js
git checkout -- tests/fixtures/dummy_project/src/components/EventBusTest.vue
rm migration-report-*.md
```

---

## Bug 3: String Literal False Positives (stringContainsCodeMixin)

**Run:**
```bash
echo "y" | python -m vue3_migration mixin stringContainsCodeMixin tests/fixtures/dummy_project
```

**Look at:** `tests/fixtures/dummy_project/src/composables/useStringContainsCode.js`

**Expect:**
- Line 1: `// ✅ 0 issues` — zero warnings, NOT `// ⚠️ 5 manual steps needed`
- No `// ❌` inline comments anywhere in the file
- String literals preserved as-is: `'Call this.$emit("update") to notify parent components'`

**Also check the migration report** (printed path at end of run):
- The `useStringContainsCode` section should show **0 steps**, not 5

**Should NOT appear:**
- `// ❌ not available in composable` on any line
- `// ❌ removed in Vue 3` on any line
- Report steps mentioning `this.$emit`, `this.$refs`, `this.$router`, `this.$store` for this mixin

**Clean up:**
```bash
rm tests/fixtures/dummy_project/src/composables/useStringContainsCode.js
rm migration-report-*.md
```

---

## Quick Checklist

- [ ] Bug 1: `useSort.js` has `export function useSort(defaultKey = 'name')` with `ref(defaultKey)`
- [ ] Bug 2: `useEventBus.js` has correct `handleUserAction` body with `receivedEvents.value.push`, no object-literal syntax
- [ ] Bug 3: `useStringContainsCode.js` has `✅ 0 issues` header, zero `// ❌` comments
