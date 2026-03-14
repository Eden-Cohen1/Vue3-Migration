# Test Suite Consolidation Plan

## Context
The test suite has ~945 tests across 29 files. While the count isn't inherently excessive for this project's complexity, there are ~150+ tests that can be consolidated through merging, parameterizing, or removing genuine duplicates. Goal: reduce to ~750-800 tests without losing any coverage.

## Priority 1: Remove Real Redundancy (~40-60 tests)

### 1A. Integration status-check pattern deduplication
**Files:** `test_integration.py`, `test_integration_new_fixtures.py`

**Problem:** 13+ test classes repeat the same 4-assertion pattern:
- `test_status_is_ready` / `test_status_is_blocked_*`
- `test_composable_matched`
- `test_no_truly_missing`
- `test_no_truly_not_returned`

**Action:** Create a shared helper or parameterized test:
```python
@pytest.mark.parametrize("component,mixin,expected_status,expected_missing", [
    ("SearchTest.vue", "searchMixin", MigrationStatus.READY, []),
    ("PaginatedList.vue", "paginationMixin", MigrationStatus.BLOCKED_NOT_RETURNED, []),
    ...
])
def test_component_mixin_status(component, mixin, expected_status, expected_missing):
    entry = _run(component, mixin)
    assert entry.status == expected_status
    assert entry.classification.truly_missing == expected_missing
```

**Savings:** ~20-30 tests → ~2-3 parameterized tests
**Risk:** Low. Same assertions, just restructured.

### 1B. Member-in-section tests collapse
**File:** `test_integration_new_fixtures.py`

**Problem:** `test_used_members_data`, `test_used_members_computed`, `test_used_members_methods` do identical loops with different member lists. Each calls `_run()` separately (wasted work too).

**Action:** Merge into single `test_all_used_members` per component class.

**Savings:** ~10-15 tests → ~3-5 tests
**Risk:** Low.

### 1C. Lifecycle hook test deduplication
**Files:** `test_lifecycle_converter.py`, `test_composable_generator.py`, `test_composable_patcher.py`

**Problem:** All three test `mounted → onMounted`, `created → inline`, `beforeDestroy → onBeforeUnmount` transformations independently.

**Action:** Keep lifecycle tests in `test_lifecycle_converter.py` (the dedicated unit test file). Remove overlapping lifecycle-specific assertions from generator and patcher tests — those files should test *their own* logic (generation/patching), not re-verify the converter.

**Savings:** ~8-10 tests
**Risk:** Medium. Need to verify the generator/patcher tests aren't testing integration paths unique to their context. Read each test carefully before removing.

## Priority 2: Parameterize Repetitive Patterns (~80-100 tests → ~20-30)

### 2A. `test_parser_fixes.py::TestExtractValueAt`
**13 one-liner tests** → 1 parameterized test with 13 cases.

### 2B. `test_file_resolver.py::TestComputeImportPath`
**~8 tests** with identical structure → 1 parameterized test.

### 2C. `test_composable_analyzer.py::TestExtractFunctionName`
**~5 trivial tests** → 1 parameterized test.

### 2D. `test_this_rewriter.py` simple cases
Several individual tests for `this.x → x.value`, `this.method() → method()`, etc. → parameterize the straightforward ones, keep complex edge cases as separate tests.

### 2E. `test_warning_collector.py` pattern groups
Groups of tests that check "does pattern X produce warning Y" with identical structure → parameterize within each group. Keep the overall file but reduce method count.

**Savings:** ~80-100 methods become ~20-30 parameterized tests
**Risk:** Low. Parameterization preserves every test case.

## Priority 3: Structural Consolidation (no test removal)

### 3A. `test_this_rewriter.py` + bracket notation tests from `test_parser_fixes.py`
Move `TestBracketNotation` from `test_parser_fixes.py` into `test_this_rewriter.py` since they test the same function (`rewrite_this_refs`).

### 3B. Consider merging `test_integration.py` and `test_integration_new_fixtures.py`
Both test `_run()` against `dummy_project`. The split seems historical (new fixtures were added later). A single file with clear sections would be easier to maintain.

## DO NOT TOUCH (looks duplicated but isn't)

- **`test_this_dollar.py` vs `test_this_i18n.py` vs `test_this_rewriter.py`** — Different rewrite categories, distinct code paths
- **`test_warning_collector.py`** (124 tests) — Each tests a distinct warning pattern, valuable as regression suite
- **`test_js_parser.py`** (53 tests) — Low-level parser edge cases, all needed
- **Unit tests that overlap with integration tests** — Different testing levels, both needed
- **`test_cross_flow_consistency.py`** — Unique: verifies 3 CLI modes produce identical output
- **`test_idempotency.py`** — Only 2 tests, critical safety net

## Verification

After each priority batch:
1. `pytest tests/ -v` — all tests pass
2. `pytest tests/ --co -q | wc -l` — confirm test count decreased as expected
3. `pytest tests/ --cov=vue3_migration --cov-report=term-missing` — coverage did not decrease (if coverage is set up)
4. Spot-check that parameterized tests produce the same individual results (use `-v` to see each case)

## Execution Order
1. Priority 2 first (parameterization) — safest, no coverage risk
2. Priority 1A & 1B (integration dedup) — straightforward merges
3. Priority 1C (lifecycle dedup) — requires careful reading
4. Priority 3 (structural moves) — optional, readability improvement only
