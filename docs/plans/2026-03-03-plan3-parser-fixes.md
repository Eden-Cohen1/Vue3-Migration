# Plan 3: Parser & Extraction Fixes

**Depends on:** Plan 1 (Warning Infrastructure)
**Estimated scope:** ~5-6 files modified

## Goal

Fix parsing bugs and gaps that cause silently broken output. These are correctness fixes to existing logic — they don't add new features, they make existing features work on more real-world code patterns.

## Cases to Fix

### Fix 1: Data Default Extraction (CRITICAL)

**Problem:** `_extract_data_default()` in `composable_patcher.py` uses `[^,\n}]+` regex which truncates at commas:
- `items: [1, 2, 3]` → extracts `[1` (broken syntax)
- `config: { a: 1, b: 2 }` → extracts `{ a: 1` (broken syntax)
- `label: 'hello, world'` → extracts `'hello` (broken syntax)

**Fix:** Use brace/bracket/string-aware value extraction:
1. From the position after `name:`, walk forward using `skip_non_code` for strings
2. Track `[]` and `{}` depth
3. Stop at a `,` or `}` only when depth is 0 and not inside a string

**Implementation:**
- Add `extract_value_at(source, pos) -> str` to `js_parser.py` — returns the full value expression starting at `pos`, respecting nested brackets, braces, and strings
- Replace the regex in `_extract_data_default()` with a call to `extract_value_at()`
- Same fix needed in `composable_generator.py` which calls `_extract_data_default()`

### Fix 2: Named Import Parsing

**Problem:** `parse_imports()` only matches `import X from 'path'`. Named imports like `import { authMixin } from './mixins'` are invisible.

**Fix:** Add a second regex pattern:
```python
# Named imports: import { X } from 'path' or import { X as Y } from 'path'
for match in re.finditer(
    r"""import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]""",
    component_source
):
    names_str = match.group(1)
    path = match.group(2)
    for name_part in names_str.split(','):
        name_part = name_part.strip()
        if ' as ' in name_part:
            _, local = name_part.split(' as ', 1)
            imports[local.strip()] = path
        else:
            imports[name_part] = path
```

Also handle the corresponding `remove_import_line()` in `injector.py` — currently only removes default imports. Need to handle removing a name from a named import (or the whole line if it's the only name).

### Fix 3: Bracket Notation `this['prop']`

**Problem:** `rewrite_this_refs()` only matches `this.xxx` with dot notation. `this['count']` and `this["count"]` are left unchanged.

**Fix:** Add a second pass in `rewrite_this_refs()`:
```python
# After the main this.xxx pass, also handle this['xxx'] and this["xxx"]
bracket_pattern = re.compile(
    r"\bthis\[(['\"])(" + "|".join(re.escape(m) for m in all_members) + r")\1\]"
)
```
Replace with `name.value` or `name` depending on membership, same as dot notation.

### Fix 4: `this` Aliasing Detection (Warn Only)

**Problem:** Code like `const self = this; setTimeout(() => { self.count++ })` — `self.count` is never rewritten.

**Fix:** In `warning_collector.py`, add detection:
```python
def detect_this_aliasing(mixin_source) -> list[MigrationWarning]:
    pattern = r'\b(?:const|let|var)\s+(self|that|vm|_this|_self)\s*=\s*this\b'
    # ...emit warning with alias name
```

This is warn-only — auto-rewriting `self.x` would require tracking alias scope, which is too complex and error-prone.

### Fix 5: TypeScript Annotation Handling

**Problem:** Method params like `foo(arg: string, count: number)` get extracted with type annotations included. The generated composable then has `function foo(arg: string, count: number)` which is fine for `.ts` files but may indicate the composable should also be `.ts`.

More critically, `data(): DataType { return {...} }` — the return type annotation between `)` and `{` may confuse the `data\s*\(\s*\)\s*\{` regex.

**Fix:**
- Update `data` regex to allow optional type annotation: `data\s*\(\s*\)\s*(?::\s*\w+(?:<[^>]*>)?\s*)?\{`
- For param extraction, leave type annotations as-is (they're valid in `.ts` composables)
- Add warning if mixin file is `.ts` but composable output target is `.js`

## Implementation Steps

### Step 1: `extract_value_at()` in js_parser.py

- New function that walks from a position, tracking `[]{}()` depth and skipping strings/comments
- Returns the full value expression
- Add comprehensive tests for arrays, objects, strings with commas, nested structures

### Step 2: Fix `_extract_data_default()` in composable_patcher.py

- Replace regex with call to new `extract_value_at()`
- Verify with test: `items: [1, 2, 3]` → extracts `[1, 2, 3]`

### Step 3: Extend `parse_imports()` in component_analyzer.py

- Add named import regex
- Handle `as` aliases
- Update `remove_import_line()` in injector.py to handle named imports

### Step 4: Bracket notation in this_rewriter.py

- Add second regex pass for `this['name']` and `this["name"]`
- Skip non-code spans same as dot notation
- Add tests

### Step 5: `this` aliasing detection in warning_collector.py

- Detect `const self = this` pattern
- Emit warning with alias name

### Step 6: TypeScript data() regex fix

- Update data regex in mixin_analyzer.py and composable_patcher.py
- Handle optional return type annotation

### Step 7: Tests

File: `tests/test_parser_fixes.py` (new)
- `extract_value_at()` with arrays, objects, strings, nested structures
- `_extract_data_default()` with complex defaults
- `parse_imports()` with named imports, aliased imports
- `rewrite_this_refs()` with bracket notation
- `detect_this_aliasing()` with various alias patterns
- TypeScript data() with return type annotation

## Files Modified

| File | Change |
|------|--------|
| `vue3_migration/core/js_parser.py` | Add `extract_value_at()` |
| `vue3_migration/transform/composable_patcher.py` | Fix `_extract_data_default()` to use `extract_value_at()` |
| `vue3_migration/core/component_analyzer.py` | Extend `parse_imports()` for named imports |
| `vue3_migration/transform/injector.py` | Fix `remove_import_line()` for named imports |
| `vue3_migration/transform/this_rewriter.py` | Add bracket notation handling |
| `vue3_migration/core/warning_collector.py` | Add `detect_this_aliasing()` |
| `vue3_migration/core/mixin_analyzer.py` | TypeScript data() regex fix |
| `tests/test_parser_fixes.py` | **New** — all parser fix tests |
