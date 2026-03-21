# Composable Divergence Detection

## Problem

When a composable already implements a member from a mixin, the tool silently accepts it and injects it into the component's `setup()`. There is no verification that the composable's implementation actually matches the mixin's logic. A developer may have ported a method incorrectly — missing error handling, wrong conditional, forgotten emit — and the tool gives no signal.

## Goal

Detect meaningful implementation differences between mixin members and their composable counterparts. Surface them in the migration report so developers can verify correctness before migrating.

### Constraints

- **No false positives from syntax differences** — `this.x` vs `x.value`, `this.$emit` vs `emit()`, etc. are expected and must not be flagged.
- **No overwhelming noise** — only show lines that actually differ after accounting for Vue 2→3 syntax transforms.
- **Actionable output** — show the developer exactly which lines diverge, not vague "these are different" messages.
- **Minimal new code** — reuse `generate_member_declaration()`, `rewrite_this_refs()`, and existing parsing infrastructure.

## Approach: Re-generate and Diff

For each mixin member that the composable already covers (i.e., in `injectable`, not in `missing` or `not_returned`):

1. **Re-generate** what the composable member should look like using the existing `generate_member_declaration()` from `composable_patcher.py`
2. **Extract** the actual member body from the composable source
3. **Normalize** both sides to eliminate style noise
4. **Diff** line-by-line to find real divergences
5. **Classify** non-convertible lines (patterns the generator can't handle) as "manual review" items

### Why this approach

`generate_member_declaration()` already encodes all Vue 2→3 transformations the tool knows about (`this.x` → `x.value`, `this.$set` → direct assignment, lifecycle hooks, etc.). By comparing its output against the actual composable code, all expected syntax differences are automatically accounted for. Any remaining difference is a genuine divergence.

## Data Model

### New dataclasses in `models.py`

```python
@dataclass
class DivergentLine:
    """A single line that differs between expected and actual composable code."""
    line_hint: str              # Line number or range (e.g., "4" or "5-9")
    expected: str               # What the generator would produce
    actual: str | None          # What the composable has (None = missing)
    manual_review: bool = False # True for non-convertible patterns

@dataclass
class MemberDivergence:
    """Divergence analysis for a single mixin member vs its composable implementation."""
    member_name: str
    mixin_kind: str                      # "data" | "computed" | "methods" | "watch"
    divergent_lines: list[DivergentLine]

    @property
    def divergent_count(self) -> int:
        """Number of real divergences (excludes manual-review-only lines)."""
        return sum(1 for d in self.divergent_lines if not d.manual_review)

    @property
    def manual_review_count(self) -> int:
        return sum(1 for d in self.divergent_lines if d.manual_review)
```

### New field on `MixinEntry`

```python
@dataclass
class MixinEntry:
    # ... existing fields ...
    divergences: list[MemberDivergence] = field(default_factory=list)
    """Members where composable implementation diverges from mixin."""
```

## Core Algorithm

### New module: `core/divergence_detector.py`

This module is the only new file. It contains:

#### `detect_divergences(mixin_source, composable_source, mixin_members, covered_members, ref_members, plain_members) -> list[MemberDivergence]`

Main entry point. For each member in `covered_members`:

1. Call `generate_member_declaration(name, mixin_source, mixin_members, ref_members, plain_members, indent="")` to get the expected code (pass empty indent so normalization doesn't need to handle nested indentation from `indent + indent` in generated bodies)
2. Call `extract_composable_member_body(composable_source, name)` to get the actual code
3. Normalize both with `normalize_for_comparison(code)`
4. Diff normalized lines
5. Classify diff lines — if a line contains a non-convertible pattern, mark as `manual_review`
6. If any divergent lines remain, create a `MemberDivergence`

#### `extract_composable_member_body(source, member_name) -> str | None`

Extract the declaration body for a named member from composable source. Handles:

- `const name = ref(...)` → extract the full declaration
- `const name = computed(() => ...)` → extract including the computed body
- `function name(...) { ... }` → extract the full function body
- `const name = computed(() => { ... })` → extract multi-line computed

Uses the existing `extract_brace_block()` from `core/js_parser.py` for brace-balanced extraction. Pattern: find the declaration start via regex, then extract through the balanced closing.

Also handles arrow function methods (`const doSomething = (arg) => { ... }`) — these are valid composable patterns even though the generator produces `function` declarations.

#### `normalize_for_comparison(code) -> list[str]`

Normalize code for comparison. Rules:

- Strip single-line (`//`) and block (`/* */`) comments
- Collapse runs of whitespace to single space
- Strip leading/trailing whitespace per line
- Remove empty lines
- Remove trailing semicolons
- Normalize `const`/`let`/`var` → `const` (canonical form)
- Normalize quote style: `"` and backticks (simple, no interpolation) → `'`
- Remove trailing commas
- **Do not** normalize `const`/`let`/`var` globally — only for top-level `ref()`/`computed()` declarations where the generator always uses `const`. Inside method bodies, `let` vs `const` may indicate a real difference.

Returns a list of normalized lines.

#### Non-convertible pattern detection

Reuse the same patterns from `warning_collector.py`. A line is "non-convertible" if it contains:

- `this.$emit` / `emit(` — emit patterns
- `this.$refs` / `$refs` references
- `this.$router` / `useRouter()` / `router.`
- `this.$store` / `useStore()` / `store.`
- `this.$t` / `t(` — i18n
- `this.$watch` — programmatic watchers (note: do NOT include `watch(` as non-convertible — `generate_member_declaration()` produces `watch()` calls for simple watchers, so those are valid comparisons)
- Any remaining `this.$` prefix

These lines are included in the output but marked `manual_review = True` so the report can present them differently.

## Integration Point

### In `_analyze_mixin_silent()` (`auto_migrate_workflow.py`)

After classification is computed (line 125) and the composable exists, before `compute_status()` (line 175):

```python
# After line 125 (entry.classification = coverage.classify_members(...))
# Detect divergences for covered members
if entry.classification and entry.composable:
    covered = [
        m for m in entry.used_members
        if m not in entry.classification.missing
        and m not in entry.classification.not_returned
    ]
    if covered:
        # Same pattern as patch_composable() in composable_patcher.py:618-619
        ref_members = members.data + members.computed + members.watch
        plain_members = members.methods
        entry.divergences = detect_divergences(
            mixin_source=mixin_source,
            composable_source=comp_source,
            mixin_members=members,
            covered_members=covered,
            ref_members=ref_members,
            plain_members=plain_members,
        )
```

Key: `comp_source` is already read at line 111 — reuse it, don't read again. Note that `comp_source` is reassigned at line 154 for warning suppression, so the divergence call must be placed before that point (between lines 125 and 142).

`ref_members` and `plain_members` computation follows the exact same pattern used in `patch_composable()` (`composable_patcher.py:618-619`): `data + computed + watch` for refs, `methods` for plain.

## Report Rendering

### In `reporting/markdown.py`

Add a new helper function and integrate it into `_append_composable_steps()`.

#### New function: `_build_divergence_section(entry, composable_path, project_root) -> str`

For each `MemberDivergence` in `entry.divergences`, render:

```markdown
<details>
<summary><b>memberName</b> — N divergent lines</summary>

| Line | Mixin (expected) | Composable (actual) |
|------|-----------------|---------------------|
| 4    | `results.value = res.data.items.filter(i => i.active);` | `results.value = res.data.items;` |
| 5-9  | `} catch (err) { error.value = err.message; }` | *(missing)* |
| 6    | `emit('search-error', err);` | *(missing — manual review)* :warning: |

</details>
```

Members with zero divergences get: `**memberName** — matches mixin`

#### Integration into the report

In `_append_composable_steps()`, after the existing warning steps, add divergence output:

```python
if entry.divergences:
    divergence_section = _build_divergence_section(entry, comp_path, project_root)
    a(divergence_section)
```

#### Section header in the action plan

When any entries have divergences, add a subsection header in `build_action_plan()`:

```markdown
### Implementation Divergences

> The following composable members were already implemented but differ from the mixin logic.
> Verify these differences are intentional.
```

With file links: `> [useSearch.js](src/composables/useSearch.js) · [searchMixin.js](src/mixins/searchMixin.js)`

## Edge Cases

### 1. Data members (`const x = ref(...)`)

Data members are single-line declarations. Comparison is just the initial value. If mixin has `data() { return { count: 0 } }` and composable has `const count = ref(1)`, that's a divergence: different initial value.

### 2. Getter/setter computed properties

`generate_member_declaration()` already handles these (line 519-523 of `composable_patcher.py`). If it falls back to a `// TODO` comment, treat the entire member as "manual review" — can't compare.

### 3. Watch members

`generate_member_declaration()` generates `watch()` calls or falls back to `// watch: name — migrate manually`. For the fallback case, mark as "manual review".

### 4. Members the generator can't classify

`generate_member_declaration()` returns `// name — could not classify, migrate manually` (line 563). Skip these — no meaningful comparison possible.

### 5. Composable member not extractable

If `extract_composable_member_body()` can't find the member (e.g., it's dynamically generated or uses an unusual pattern), skip it silently — no divergence reported.

### 6. Mixin members with complex `this` usage

The generator may produce code with remaining `this.` references (for patterns it can't rewrite). These lines should be marked "manual review" using the same non-convertible pattern detection.

### 7. Indentation differences

Normalization strips all leading whitespace, so indentation style (2 spaces vs 4 spaces vs tabs) is irrelevant.

### 8. Member exists but empty

If the composable has a stub like `function fetchResults() {}` and the mixin has a full body, every line of the mixin body shows as "missing" in the composable — clear divergence.

## Files Modified

| File | Change |
|------|--------|
| `models.py` | Add `DivergentLine`, `MemberDivergence` dataclasses; add `divergences` field to `MixinEntry` |
| `core/divergence_detector.py` | **New file** — `detect_divergences()`, `extract_composable_member_body()`, `normalize_for_comparison()` |
| `auto_migrate_workflow.py` | Call `detect_divergences()` in `_analyze_mixin_silent()` after classification |
| `reporting/markdown.py` | Add `_build_divergence_section()`; integrate into `_append_composable_steps()` and `build_action_plan()` |

## Verification

### Unit tests

1. **Identical implementation** — mixin and composable have same logic → no divergences
2. **Missing error handling** — mixin has try/catch, composable doesn't → flags the missing lines
3. **Missing emit** — mixin has `this.$emit(...)`, composable has no `emit()` → flags as manual review
4. **Different initial value** — data member with different default → flags
5. **Style-only differences** — different quotes, semicolons, indentation → no divergences (normalization)
6. **Stub implementation** — composable has empty function body → flags all mixin lines as missing
7. **Non-convertible patterns** — `this.$router` in mixin → marked manual review, not hard divergence

### Integration test

Run against `tests/fixtures/dummy_project/`:

```bash
# Status report should now include divergence sections
python -m vue3_migration status tests/fixtures/dummy_project

# Full migration report should show divergences in action plan
python -m vue3_migration all tests/fixtures/dummy_project
```

Verify:
- Report renders without errors
- Divergence sections appear only for members that actually differ
- Collapsible `<details>` sections work in rendered markdown
- File links point to correct composable/mixin paths
- No divergence noise for members that match after normalization
