# Plan 1: Warning Infrastructure + Confidence Scoring

**Depends on:** Nothing (foundation for Plans 2-4)
**Estimated scope:** ~6-8 files modified, 1-2 new files

## Goal

Build the framework for detecting, collecting, and surfacing migration warnings across all three output channels: inline code comments, terminal summary, and markdown report. All subsequent plans plug into this infrastructure.

## Data Model

### New: `MigrationWarning` (in `models.py`)

```python
@dataclass
class MigrationWarning:
    mixin_stem: str           # Which mixin triggered this
    category: str             # e.g. "this.$router", "watch", "mixin-option"
    message: str              # Human-readable description
    action_required: str      # What the developer must do
    line_hint: str | None     # Source line context (for inline comment)
    severity: str             # "error" | "warning" | "info"
```

### Extend: `MixinEntry` (in `models.py`)

Add field:
```python
warnings: list[MigrationWarning] = field(default_factory=list)
```

### New: `ConfidenceLevel` enum (in `models.py`)

```python
class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"       # 0 remaining this., 0 TODOs, 0 warnings
    MEDIUM = "MEDIUM"   # has TODOs or warnings but no remaining this.
    LOW = "LOW"         # has remaining this.$, unbalanced brackets, or structural warnings
```

## Implementation Steps

### Step 1: Add data models

File: `vue3_migration/models.py`
- Add `MigrationWarning` dataclass
- Add `ConfidenceLevel` enum
- Add `warnings: list[MigrationWarning]` field to `MixinEntry`

### Step 2: Build warning collector module

New file: `vue3_migration/core/warning_collector.py`

Functions:
- `collect_mixin_warnings(mixin_source, mixin_members, lifecycle_hooks) -> list[MigrationWarning]`
  - Scans mixin source for known problematic patterns
  - Returns warning objects (does NOT modify source)
  - Initially stub — just scans for remaining `this.$` references
  - Plans 2-4 add specific detectors here

- `compute_confidence(composable_source, warnings) -> ConfidenceLevel`
  - Scans generated composable for:
    - Remaining `this.` references → LOW
    - Unbalanced brackets/braces → LOW
    - `// TODO` or `// ⚠ MIGRATION` count > 0 → MEDIUM
    - No issues → HIGH

### Step 3: Inline comment injection

File: `vue3_migration/transform/composable_generator.py`
- After generating composable, call `collect_mixin_warnings()`
- For each warning with a `line_hint`, insert `// ⚠ MIGRATION: {message}` above the relevant line
- Add confidence comment at top of generated file:
  ```javascript
  // Migration confidence: MEDIUM (2 warnings — see migration report)
  ```

File: `vue3_migration/transform/composable_patcher.py`
- Same logic when patching existing composables

### Step 4: Post-generation self-check

New function in `warning_collector.py`:
- `post_generation_check(composable_source) -> list[MigrationWarning]`
  - Scan for remaining `\bthis\.` references (should be zero)
  - Check bracket/brace balance
  - Count `// TODO` markers
  - These are added to the warning list after generation

### Step 5: Terminal warning summary

File: `vue3_migration/workflows/auto_migrate_workflow.py`
- After planning changes, before confirmation prompt:
  - Print per-mixin warning summary with counts
  - Show confidence level per composable
  - Example:
    ```
    ✓ useAuth — MEDIUM confidence (2 warnings)
      ⚠ this.$router used → needs useRouter()
      ⚠ watch handler 'isLoggedIn' not auto-converted
    ✓ useSelection — HIGH confidence
    ```

### Step 6: Markdown report warnings section

File: `vue3_migration/reporting/markdown.py`
- Add `## Migration Warnings` section to generated report
- Group by mixin, show table: Line | Issue | Action Required
- Show confidence score per composable

### Step 7: Tests

New file: `tests/test_warning_collector.py`
- Test `collect_mixin_warnings` with mixin source containing `this.$emit`, `this.$router`, etc.
- Test `compute_confidence` with various composable sources
- Test `post_generation_check` with remaining `this.` references
- Test that inline comments are properly inserted in generated composables
- Test that warnings appear in terminal output and markdown report

## Key Design Decisions

1. **Warnings are collected, not thrown** — they accumulate in `MixinEntry.warnings` and are surfaced at the end. The tool never aborts due to warnings.
2. **Inline comments use `// ⚠ MIGRATION:` prefix** — grep-able across the codebase.
3. **Confidence is computed AFTER generation** — it's a post-check, not a pre-check.
4. **Warning collector is a separate module** — Plans 2-4 add detectors to it without touching the generator/patcher.

## Files Modified

| File | Change |
|------|--------|
| `vue3_migration/models.py` | Add `MigrationWarning`, `ConfidenceLevel`, extend `MixinEntry` |
| `vue3_migration/core/warning_collector.py` | **New** — collection + confidence scoring |
| `vue3_migration/transform/composable_generator.py` | Call warning collector, inject inline comments |
| `vue3_migration/transform/composable_patcher.py` | Call warning collector, inject inline comments |
| `vue3_migration/workflows/auto_migrate_workflow.py` | Terminal warning summary |
| `vue3_migration/reporting/markdown.py` | Warnings section in report |
| `tests/test_warning_collector.py` | **New** — warning collection tests |
