# Composable Divergence Detection — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect and report meaningful logic differences between mixin members and their existing composable implementations.

**Architecture:** New `core/divergence_detector.py` module with three functions. Re-generates expected composable code via `generate_member_declaration()`, extracts actual composable member body, normalizes both, and diffs. Results stored on `MixinEntry.divergences` and rendered in the markdown report.

**Tech Stack:** Python, existing JS string parsing (`js_parser.py`), existing code generation (`composable_patcher.py`)

**Spec:** `docs/superpowers/specs/2026-03-20-composable-divergence-detection-design.md`

---

### Task 1: Data Model — Add `DivergentLine`, `MemberDivergence`, and `MixinEntry.divergences`

**Files:**
- Modify: `vue3_migration/models.py:166-192`
- Test: `tests/test_divergence_detector.py` (create)

- [ ] **Step 1: Write the test for the data model**

Create `tests/test_divergence_detector.py`:

```python
from vue3_migration.models import DivergentLine, MemberDivergence, MixinEntry, MixinMembers


def test_divergent_line_basic():
    dl = DivergentLine(line_hint="4", expected="x.value = 1", actual="x.value = 2")
    assert not dl.manual_review


def test_divergent_line_manual_review():
    dl = DivergentLine(line_hint="6", expected="this.$emit('done')", actual=None, manual_review=True)
    assert dl.manual_review


def test_member_divergence_counts():
    div = MemberDivergence(
        member_name="fetchData",
        mixin_kind="methods",
        divergent_lines=[
            DivergentLine(line_hint="4", expected="a", actual="b"),
            DivergentLine(line_hint="5", expected="c", actual=None, manual_review=True),
            DivergentLine(line_hint="6", expected="d", actual="e"),
        ],
    )
    assert div.divergent_count == 2
    assert div.manual_review_count == 1


def test_mixin_entry_divergences_default_empty():
    entry = MixinEntry(
        local_name="testMixin",
        mixin_path="fake.js",
        mixin_stem="testMixin",
        members=MixinMembers(),
    )
    assert entry.divergences == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_detector.py -v`
Expected: ImportError — `DivergentLine`, `MemberDivergence` not found; `MixinEntry` missing `divergences` field.

- [ ] **Step 3: Add the dataclasses to `models.py`**

In `vue3_migration/models.py`, add after `MemberClassification` (after line 165, before `MixinEntry`):

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
    divergent_lines: list[DivergentLine] = field(default_factory=list)

    @property
    def divergent_count(self) -> int:
        return sum(1 for d in self.divergent_lines if not d.manual_review)

    @property
    def manual_review_count(self) -> int:
        return sum(1 for d in self.divergent_lines if d.manual_review)
```

Add to `MixinEntry` (after `external_deps`, before `compute_status`):

```python
    divergences: list[MemberDivergence] = field(default_factory=list)
    """Members where composable implementation diverges from mixin."""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_divergence_detector.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Run full test suite to ensure no regressions**

Run: `pytest tests/ -x -q`
Expected: All existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add vue3_migration/models.py tests/test_divergence_detector.py
git commit -m "feat: add DivergentLine, MemberDivergence models for divergence detection"
```

---

### Task 2: `normalize_for_comparison()` — Code normalization for diffing

**Files:**
- Create: `vue3_migration/core/divergence_detector.py`
- Test: `tests/test_divergence_detector.py` (append)

- [ ] **Step 1: Write tests for normalization**

Append to `tests/test_divergence_detector.py`:

```python
from vue3_migration.core.divergence_detector import normalize_for_comparison


def test_normalize_strips_comments():
    code = "const x = ref(1) // initial value\n/* block */\nconst y = ref(2)"
    result = normalize_for_comparison(code)
    assert result == ["const x = ref(1)", "const y = ref(2)"]


def test_normalize_collapses_whitespace():
    code = "  const   x   =   ref( 1 )  "
    result = normalize_for_comparison(code)
    assert result == ["const x = ref( 1 )"]


def test_normalize_removes_empty_lines():
    code = "const x = ref(1)\n\n\nconst y = ref(2)"
    result = normalize_for_comparison(code)
    assert result == ["const x = ref(1)", "const y = ref(2)"]


def test_normalize_strips_semicolons():
    code = "const x = ref(1);\nreturn x;"
    result = normalize_for_comparison(code)
    assert result == ["const x = ref(1)", "return x"]


def test_normalize_quotes():
    code = 'const x = "hello"\nconst y = `world`'
    result = normalize_for_comparison(code)
    assert result == ["const x = 'hello'", "const y = 'world'"]


def test_normalize_preserves_template_interpolation():
    code = "const x = `hello ${name}`"
    result = normalize_for_comparison(code)
    assert result == ["const x = `hello ${name}`"]


def test_normalize_removes_trailing_commas():
    code = "return { a, b, }"
    result = normalize_for_comparison(code)
    assert result == ["return { a, b }"]


def test_normalize_const_let_var_only_for_ref_computed():
    """const/let/var normalization only for ref()/computed() declarations."""
    code = "let x = ref(1)\nvar y = computed(() => 2)\nlet z = something()"
    result = normalize_for_comparison(code)
    # ref/computed declarations: normalize to const
    # other: preserve let/var
    assert result == ["const x = ref(1)", "const y = computed(() => 2)", "let z = something()"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_detector.py::test_normalize_strips_comments -v`
Expected: ImportError — `divergence_detector` module doesn't exist.

- [ ] **Step 3: Implement `normalize_for_comparison`**

Create `vue3_migration/core/divergence_detector.py`:

```python
"""Divergence detection between mixin members and composable implementations.

Compares what the generator would produce against what the composable
actually contains, surfacing meaningful logic differences.
"""

import re


def normalize_for_comparison(code: str) -> list[str]:
    """Normalize code for comparison, stripping style noise.

    Returns a list of non-empty normalized lines.
    """
    # Strip block comments
    text = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    # Strip single-line comments (but not inside strings — simplified: only at line level)
    text = re.sub(r"//[^\n]*", "", text)

    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Remove trailing semicolons
        line = line.rstrip(";")
        # Collapse whitespace
        line = re.sub(r"\s+", " ", line)
        # Remove trailing commas before } or )
        line = re.sub(r",\s*([}\)])", r"\1", line)
        # Normalize quotes: double quotes → single (but not template literals with interpolation)
        line = re.sub(r'"([^"]*)"', r"'\1'", line)
        # Backticks without interpolation → single quotes
        if "`" in line and "${" not in line:
            line = re.sub(r"`([^`]*)`", r"'\1'", line)
        # Normalize const/let/var only for ref()/computed()/reactive()/shallowRef()/toRef()/toRefs() declarations
        line = re.sub(
            r"\b(let|var)\s+(\w+\s*=\s*(?:ref|computed|reactive|shallowRef|shallowReactive|toRef|toRefs|customRef)\s*\()",
            r"const \2",
            line,
        )
        if line:
            lines.append(line)
    return lines
```

- [ ] **Step 4: Run normalization tests**

Run: `pytest tests/test_divergence_detector.py -k "normalize" -v`
Expected: All 8 normalization tests PASS.

- [ ] **Step 5: Commit**

```bash
git add vue3_migration/core/divergence_detector.py tests/test_divergence_detector.py
git commit -m "feat: add normalize_for_comparison for divergence detection"
```

---

### Task 3: `extract_composable_member_body()` — Extract member declarations from composable source

**Files:**
- Modify: `vue3_migration/core/divergence_detector.py`
- Test: `tests/test_divergence_detector.py` (append)

- [ ] **Step 1: Write tests for member body extraction**

Append to `tests/test_divergence_detector.py`:

```python
from vue3_migration.core.divergence_detector import extract_composable_member_body


COMPOSABLE_SOURCE = """\
import { ref, computed, onMounted } from 'vue'

export function useSearch() {
  const loading = ref(false)
  const results = ref([])
  const count = computed(() => results.value.length)

  async function fetchResults(query) {
    loading.value = true
    const res = await http.get('/api/search', { params: { q: query } })
    results.value = res.data.items
    loading.value = false
  }

  const reset = (arg) => {
    results.value = []
    loading.value = false
  }

  return { loading, results, count, fetchResults, reset }
}
"""


def test_extract_ref_member():
    body = extract_composable_member_body(COMPOSABLE_SOURCE, "loading")
    assert body is not None
    assert "ref(false)" in body


def test_extract_computed_member():
    body = extract_composable_member_body(COMPOSABLE_SOURCE, "count")
    assert body is not None
    assert "computed" in body
    assert "results.value.length" in body


def test_extract_function_member():
    body = extract_composable_member_body(COMPOSABLE_SOURCE, "fetchResults")
    assert body is not None
    assert "loading.value = true" in body
    assert "http.get" in body


def test_extract_arrow_function_member():
    body = extract_composable_member_body(COMPOSABLE_SOURCE, "reset")
    assert body is not None
    assert "results.value = []" in body


def test_extract_nonexistent_member():
    body = extract_composable_member_body(COMPOSABLE_SOURCE, "nonexistent")
    assert body is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_detector.py::test_extract_ref_member -v`
Expected: ImportError — `extract_composable_member_body` not found.

- [ ] **Step 3: Implement `extract_composable_member_body`**

Add to `vue3_migration/core/divergence_detector.py`:

```python
from .js_parser import extract_brace_block


def extract_composable_member_body(source: str, member_name: str) -> str | None:
    """Extract the full declaration of a named member from composable source.

    Handles:
      const name = ref(...)
      const name = computed(() => ...)
      const name = computed(() => { ... })
      function name(...) { ... }
      async function name(...) { ... }
      const name = (...) => { ... }
      const name = (...) => expr
    """
    esc = re.escape(member_name)

    # Pattern 1: function declaration — function name(...) { ... }
    fn_match = re.search(rf"\b(?:async\s+)?function\s+{esc}\s*\(", source)
    if fn_match:
        # Find the opening brace
        rest = source[fn_match.start():]
        brace_pos = rest.find("{")
        if brace_pos >= 0:
            abs_brace = fn_match.start() + brace_pos
            inner = extract_brace_block(source, abs_brace)
            return source[fn_match.start():abs_brace + 1 + len(inner) + 1]

    # Pattern 2: const/let/var name = ...
    decl_match = re.search(rf"\b(?:const|let|var)\s+{esc}\s*=\s*", source)
    if decl_match:
        after_eq = source[decl_match.end():]
        # Check if followed by something with braces (computed block, arrow with block, etc.)
        # or a simple expression ending at newline

        # Sub-pattern 2a: arrow function with block body — (...) => { ... }
        arrow_block = re.match(r"(?:async\s+)?\([^)]*\)\s*=>\s*\{", after_eq)
        if arrow_block:
            brace_start = decl_match.end() + after_eq.index("{")
            inner = extract_brace_block(source, brace_start)
            return source[decl_match.start():brace_start + 1 + len(inner) + 1]

        # Sub-pattern 2b: computed/ref/reactive with nested braces
        call_with_brace = re.match(r"\w+\s*\(\s*(?:\([^)]*\)\s*=>\s*)?\{", after_eq)
        if call_with_brace:
            brace_start = decl_match.end() + after_eq.index("{")
            inner = extract_brace_block(source, brace_start)
            # Continue past the closing brace to capture the closing parens
            end_pos = brace_start + 1 + len(inner) + 1
            # Eat any trailing ) characters
            while end_pos < len(source) and source[end_pos] in ") \t":
                end_pos += 1
            return source[decl_match.start():end_pos]

        # Sub-pattern 2c: simple single-line expression (ref(x), computed(() => expr), etc.)
        # Take everything up to the next newline
        newline_pos = after_eq.find("\n")
        if newline_pos >= 0:
            return source[decl_match.start():decl_match.end() + newline_pos].rstrip()
        return source[decl_match.start():].rstrip()

    return None
```

- [ ] **Step 4: Run extraction tests**

Run: `pytest tests/test_divergence_detector.py -k "extract" -v`
Expected: All 5 extraction tests PASS.

- [ ] **Step 5: Commit**

```bash
git add vue3_migration/core/divergence_detector.py tests/test_divergence_detector.py
git commit -m "feat: add extract_composable_member_body for divergence detection"
```

---

### Task 4: `detect_divergences()` — Main divergence detection logic

**Files:**
- Modify: `vue3_migration/core/divergence_detector.py`
- Test: `tests/test_divergence_detector.py` (append)

- [ ] **Step 1: Write tests for divergence detection**

Append to `tests/test_divergence_detector.py`:

```python
from vue3_migration.core.divergence_detector import detect_divergences
from vue3_migration.models import MixinMembers


# --- Mixin: method with try/catch and emit ---
MIXIN_WITH_ERROR_HANDLING = """\
export default {
  data() {
    return { loading: false, results: [], error: null }
  },
  methods: {
    async fetchResults(query) {
      this.loading = true
      try {
        const res = await this.$http.get('/api/search', { params: { q: query } })
        this.results = res.data.items
        this.$emit('search-complete', this.results.length)
      } catch (err) {
        this.error = err.message
        this.$emit('search-error', err)
      } finally {
        this.loading = false
      }
    }
  }
}
"""

# --- Composable: missing error handling ---
COMPOSABLE_MISSING_ERROR = """\
import { ref } from 'vue'

export function useSearch() {
  const loading = ref(false)
  const results = ref([])
  const error = ref(null)

  async function fetchResults(query) {
    loading.value = true
    const res = await http.get('/api/search', { params: { q: query } })
    results.value = res.data.items
    loading.value = false
  }

  return { loading, results, error, fetchResults }
}
"""

# --- Composable: identical logic ---
COMPOSABLE_MATCHING = """\
import { ref } from 'vue'

export function useSearch() {
  const loading = ref(false)
  const results = ref([])
  const error = ref(null)

  async function fetchResults(query) {
    loading.value = true
    try {
      const res = await http.get('/api/search', { params: { q: query } })
      results.value = res.data.items
    } catch (err) {
      error.value = err.message
    } finally {
      loading.value = false
    }
  }

  return { loading, results, error, fetchResults }
}
"""


def _make_members():
    return MixinMembers(
        data=["loading", "results", "error"],
        methods=["fetchResults"],
    )


def test_detect_divergences_identical():
    """No divergence when composable matches mixin logic."""
    members = _make_members()
    divs = detect_divergences(
        mixin_source=MIXIN_WITH_ERROR_HANDLING,
        composable_source=COMPOSABLE_MATCHING,
        mixin_members=members,
        covered_members=["fetchResults"],
        ref_members=members.data,
        plain_members=members.methods,
    )
    # fetchResults should have no real divergences
    # (emit lines may show as manual_review but not as hard divergences)
    real_divs = [d for d in divs if d.divergent_count > 0]
    assert real_divs == []


def test_detect_divergences_missing_error_handling():
    """Flags missing try/catch as divergence."""
    members = _make_members()
    divs = detect_divergences(
        mixin_source=MIXIN_WITH_ERROR_HANDLING,
        composable_source=COMPOSABLE_MISSING_ERROR,
        mixin_members=members,
        covered_members=["fetchResults"],
        ref_members=members.data,
        plain_members=members.methods,
    )
    assert len(divs) == 1
    assert divs[0].member_name == "fetchResults"
    assert divs[0].divergent_count > 0


def test_detect_divergences_data_member_different_default():
    """Flags different initial value for data members."""
    mixin_src = "export default { data() { return { count: 0 } } }"
    comp_src = "export function useX() {\n  const count = ref(42)\n  return { count }\n}"
    members = MixinMembers(data=["count"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["count"],
        ref_members=["count"],
        plain_members=[],
    )
    assert len(divs) == 1
    assert divs[0].member_name == "count"


def test_detect_divergences_data_member_same_default():
    """No divergence when data default matches."""
    mixin_src = "export default { data() { return { count: 0 } } }"
    comp_src = "export function useX() {\n  const count = ref(0)\n  return { count }\n}"
    members = MixinMembers(data=["count"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["count"],
        ref_members=["count"],
        plain_members=[],
    )
    assert divs == []


def test_detect_divergences_style_only_no_flag():
    """Style differences (quotes, semicolons) should not trigger divergence."""
    mixin_src = """\
export default {
  methods: {
    greet(name) {
      return "hello " + name
    }
  }
}"""
    comp_src = """\
export function useX() {
  function greet(name) {
    return 'hello ' + name;
  }
  return { greet }
}"""
    members = MixinMembers(methods=["greet"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["greet"],
        ref_members=[],
        plain_members=["greet"],
    )
    assert divs == []


def test_detect_divergences_skips_unclassifiable():
    """Members the generator can't classify are skipped."""
    mixin_src = "export default { }"
    comp_src = "export function useX() {\n  const foo = ref(1)\n  return { foo }\n}"
    members = MixinMembers()  # foo not in any category
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["foo"],
        ref_members=[],
        plain_members=[],
    )
    assert divs == []


def test_detect_divergences_emit_is_manual_review():
    """Emit patterns should be flagged as manual_review, not hard divergence."""
    mixin_src = """\
export default {
  methods: {
    doIt() {
      this.$emit('done')
    }
  }
}"""
    comp_src = """\
export function useX() {
  function doIt() {
    emit('done')
  }
  return { doIt }
}"""
    members = MixinMembers(methods=["doIt"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["doIt"],
        ref_members=[],
        plain_members=["doIt"],
    )
    # Should either be empty or all lines manual_review
    for d in divs:
        assert d.divergent_count == 0


def test_detect_divergences_getter_setter_computed_skipped():
    """Getter/setter computed that the generator can't handle → skipped."""
    mixin_src = """\
export default {
  computed: {
    fullName: {
      get() { return this.first + ' ' + this.last },
      set(val) { this.first = val.split(' ')[0] }
    }
  }
}"""
    comp_src = """\
export function useX() {
  const fullName = computed({
    get: () => first.value + ' ' + last.value,
    set: (val) => { first.value = val.split(' ')[0] }
  })
  return { fullName }
}"""
    members = MixinMembers(computed=["fullName"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["fullName"],
        ref_members=["fullName"],
        plain_members=[],
    )
    # Generator produces TODO comment for getter/setter → should be skipped
    assert divs == []


def test_detect_divergences_watch_fallback_skipped():
    """Watch members the generator can't handle → skipped."""
    mixin_src = """\
export default {
  watch: {
    query: {
      deep: true,
      handler(val) { this.results = [] }
    }
  }
}"""
    comp_src = """\
export function useX() {
  watch(query, (val) => { results.value = [] }, { deep: true })
  return { query, results }
}"""
    members = MixinMembers(watch=["query"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["query"],
        ref_members=["query", "results"],
        plain_members=[],
    )
    # If generator produces a watch() call, comparison proceeds normally.
    # If it falls back to "migrate manually", it's skipped.
    # Either way, no false divergence.
    for d in divs:
        assert d.member_name == "query"


def test_detect_divergences_stub_implementation():
    """Empty function body in composable → flags all mixin lines as missing."""
    mixin_src = """\
export default {
  methods: {
    fetchData(id) {
      this.loading = true
      const res = this.$http.get('/api/' + id)
      this.data = res.data
      this.loading = false
    }
  }
}"""
    comp_src = """\
export function useX() {
  function fetchData(id) {}
  return { fetchData }
}"""
    members = MixinMembers(data=["loading", "data"], methods=["fetchData"])
    divs = detect_divergences(
        mixin_source=mixin_src,
        composable_source=comp_src,
        mixin_members=members,
        covered_members=["fetchData"],
        ref_members=["loading", "data"],
        plain_members=["fetchData"],
    )
    assert len(divs) == 1
    assert divs[0].member_name == "fetchData"
    # Should have multiple divergent lines (the entire mixin body is missing)
    assert divs[0].divergent_count + divs[0].manual_review_count > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_detector.py -k "detect_divergences" -v`
Expected: ImportError — `detect_divergences` not found.

- [ ] **Step 3: Implement `detect_divergences` and non-convertible pattern detection**

Add to `vue3_migration/core/divergence_detector.py`:

```python
from ..models import DivergentLine, MemberDivergence, MixinMembers
from ..transform.composable_patcher import generate_member_declaration


# Patterns that the generator can't auto-convert — lines with these are "manual review"
_NON_CONVERTIBLE_PATTERNS = [
    re.compile(r"this\.\$emit\b"),
    re.compile(r"\bemit\s*\("),
    re.compile(r"this\.\$refs\b"),
    re.compile(r"\$refs\b"),
    re.compile(r"this\.\$router\b"),
    re.compile(r"\buseRouter\s*\("),
    re.compile(r"\brouter\."),
    re.compile(r"this\.\$store\b"),
    re.compile(r"\buseStore\s*\("),
    re.compile(r"\bstore\."),
    re.compile(r"this\.\$t\b"),
    re.compile(r"this\.\$tc\b"),
    re.compile(r"this\.\$watch\b"),
    re.compile(r"this\.\$"),  # catch-all for remaining this.$X
]


def _is_non_convertible(line: str) -> bool:
    """Check if a normalized line contains a non-convertible pattern."""
    return any(p.search(line) for p in _NON_CONVERTIBLE_PATTERNS)


def _determine_mixin_kind(name: str, mixin_members: MixinMembers) -> str:
    if name in mixin_members.data:
        return "data"
    if name in mixin_members.computed:
        return "computed"
    if name in mixin_members.methods:
        return "methods"
    if name in mixin_members.watch:
        return "watch"
    return "unknown"


def detect_divergences(
    mixin_source: str,
    composable_source: str,
    mixin_members: MixinMembers,
    covered_members: list[str],
    ref_members: list[str],
    plain_members: list[str],
) -> list[MemberDivergence]:
    """Detect meaningful divergences between mixin members and composable implementations.

    For each covered member, re-generates expected code using the existing
    generator, extracts the actual composable code, normalizes both, and
    diffs to find real logic differences.
    """
    divergences: list[MemberDivergence] = []

    for name in covered_members:
        kind = _determine_mixin_kind(name, mixin_members)
        if kind == "unknown":
            continue

        # Generate what the composable member should look like
        expected_raw = generate_member_declaration(
            name, mixin_source, mixin_members, ref_members, plain_members, indent="",
        )

        # Skip members the generator can't handle (TODO / manual migration comments)
        if "// TODO" in expected_raw or "migrate manually" in expected_raw:
            continue

        # Extract what the composable actually has
        actual_raw = extract_composable_member_body(composable_source, name)
        if actual_raw is None:
            continue

        # Normalize both sides
        expected_lines = normalize_for_comparison(expected_raw)
        actual_lines = normalize_for_comparison(actual_raw)

        # Diff
        divergent_lines = _diff_lines(expected_lines, actual_lines)

        if divergent_lines:
            divergences.append(MemberDivergence(
                member_name=name,
                mixin_kind=kind,
                divergent_lines=divergent_lines,
            ))

    return divergences


def _diff_lines(
    expected: list[str], actual: list[str],
) -> list[DivergentLine]:
    """Compare normalized line lists and produce divergent lines.

    Uses difflib for sequence matching to handle insertions/deletions.
    """
    import difflib

    result: list[DivergentLine] = []
    matcher = difflib.SequenceMatcher(None, expected, actual)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue

        if tag == "replace":
            for k in range(max(i2 - i1, j2 - j1)):
                exp = expected[i1 + k] if i1 + k < i2 else None
                act = actual[j1 + k] if j1 + k < j2 else None
                manual = False
                if exp and _is_non_convertible(exp):
                    manual = True
                if act and _is_non_convertible(act):
                    manual = True
                line_hint = str(i1 + k + 1) if exp else str(j1 + k + 1)
                result.append(DivergentLine(
                    line_hint=line_hint,
                    expected=exp or "",
                    actual=act,
                    manual_review=manual,
                ))

        elif tag == "delete":
            for k in range(i1, i2):
                manual = _is_non_convertible(expected[k])
                result.append(DivergentLine(
                    line_hint=str(k + 1),
                    expected=expected[k],
                    actual=None,
                    manual_review=manual,
                ))

        elif tag == "insert":
            for k in range(j1, j2):
                manual = _is_non_convertible(actual[k])
                result.append(DivergentLine(
                    line_hint=str(k + 1),
                    expected="",
                    actual=actual[k],
                    manual_review=manual,
                ))

    return result
```

- [ ] **Step 4: Run divergence detection tests**

Run: `pytest tests/test_divergence_detector.py -k "detect_divergences" -v`
Expected: All 11 detection tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add vue3_migration/core/divergence_detector.py tests/test_divergence_detector.py
git commit -m "feat: implement detect_divergences with line-level diffing"
```

---

### Task 5: Integrate divergence detection into `_analyze_mixin_silent()`

**Files:**
- Modify: `vue3_migration/workflows/auto_migrate_workflow.py:125-141`
- Test: `tests/test_divergence_detector.py` (append)

- [ ] **Step 1: Write integration test**

Append to `tests/test_divergence_detector.py`:

```python
import tempfile
from pathlib import Path


def test_analyze_mixin_populates_divergences(tmp_path):
    """Integration: _analyze_mixin_silent fills entry.divergences."""
    from vue3_migration.workflows.auto_migrate_workflow import _analyze_mixin_silent

    # Create a mixin with a method
    mixin_dir = tmp_path / "src" / "mixins"
    mixin_dir.mkdir(parents=True)
    mixin_file = mixin_dir / "searchMixin.js"
    mixin_file.write_text("""\
export default {
  data() {
    return { loading: false }
  },
  methods: {
    fetchResults(query) {
      this.loading = true
      const res = this.$http.get(query)
      this.loading = false
      return res
    }
  }
}
""")

    # Create a composable with a DIFFERENT implementation
    comp_dir = tmp_path / "src" / "composables"
    comp_dir.mkdir(parents=True)
    comp_file = comp_dir / "useSearch.js"
    comp_file.write_text("""\
import { ref } from 'vue'

export function useSearch() {
  const loading = ref(false)

  function fetchResults(query) {
    loading.value = true
    return null
  }

  return { loading, fetchResults }
}
""")

    # Create a component that uses the mixin
    comp_component = tmp_path / "src" / "components" / "SearchTest.vue"
    comp_component.parent.mkdir(parents=True)
    comp_component.write_text("""\
<script>
import searchMixin from '../mixins/searchMixin'
export default {
  mixins: [searchMixin],
  methods: {
    doSearch() {
      this.fetchResults('test')
      console.log(this.loading)
    }
  }
}
</script>
""")

    component_source = comp_component.read_text()
    entry = _analyze_mixin_silent(
        local_name="searchMixin",
        import_path_str="../mixins/searchMixin",
        component_path=comp_component,
        component_source=component_source,
        composable_dirs=[comp_dir],
        project_root=tmp_path,
        component_own_members={"doSearch"},
    )

    assert entry is not None
    assert entry.composable is not None
    # fetchResults should have divergences since the composable is different
    assert len(entry.divergences) > 0
    assert any(d.member_name == "fetchResults" for d in entry.divergences)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_divergence_detector.py::test_analyze_mixin_populates_divergences -v`
Expected: FAIL — `entry.divergences` is empty because integration hasn't been wired up yet.

- [ ] **Step 3: Wire up divergence detection in `_analyze_mixin_silent()`**

In `vue3_migration/workflows/auto_migrate_workflow.py`, after line 140 (end of kind-mismatch block) and before line 142 (`# Collect migration warnings`), insert:

```python
            # Detect divergences for covered members
            covered = [
                m for m in used
                if m not in entry.classification.missing
                and m not in entry.classification.not_returned
            ]
            if covered:
                from ..core.divergence_detector import detect_divergences
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

Note: This must be inside the `if fn_name:` block (which starts at line 113), after classification (line 125) and kind-mismatch warnings (lines 127-140), and before `comp_source` gets reassigned at line 154.

- [ ] **Step 4: Run integration test**

Run: `pytest tests/test_divergence_detector.py::test_analyze_mixin_populates_divergences -v`
Expected: PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass (existing tests unaffected — divergence data is additive).

- [ ] **Step 6: Commit**

```bash
git add vue3_migration/workflows/auto_migrate_workflow.py tests/test_divergence_detector.py
git commit -m "feat: wire divergence detection into analysis pipeline"
```

---

### Task 6: Report rendering — `_build_divergence_section()` and integration

**Files:**
- Modify: `vue3_migration/reporting/markdown.py`
- Test: `tests/test_divergence_detector.py` (append)

- [ ] **Step 1: Write test for report rendering**

Append to `tests/test_divergence_detector.py`:

```python
from vue3_migration.models import DivergentLine, MemberDivergence


def test_build_divergence_section_renders_table():
    from vue3_migration.reporting.markdown import _build_divergence_section
    from vue3_migration.models import MixinEntry, MixinMembers

    entry = MixinEntry(
        local_name="searchMixin",
        mixin_path=Path("src/mixins/searchMixin.js"),
        mixin_stem="searchMixin",
        members=MixinMembers(),
        divergences=[
            MemberDivergence(
                member_name="fetchResults",
                mixin_kind="methods",
                divergent_lines=[
                    DivergentLine(line_hint="4", expected="results.value = res.data.items.filter(i => i.active)", actual="results.value = res.data.items"),
                    DivergentLine(line_hint="5-9", expected="} catch (err) { error.value = err.message }", actual=None),
                    DivergentLine(line_hint="6", expected="emit('search-error', err)", actual=None, manual_review=True),
                ],
            ),
        ],
    )

    result = _build_divergence_section(
        entry,
        composable_path=Path("src/composables/useSearch.js"),
        project_root=Path("project"),
    )

    assert "<details>" in result
    assert "fetchResults" in result
    assert "Mixin (expected)" in result
    assert "Composable (actual)" in result
    assert "results.value = res.data.items" in result
    assert "*(missing)*" in result
    assert "manual review" in result


def test_build_divergence_section_no_divergences():
    from vue3_migration.reporting.markdown import _build_divergence_section
    from vue3_migration.models import MixinEntry, MixinMembers

    entry = MixinEntry(
        local_name="testMixin",
        mixin_path=Path("fake.js"),
        mixin_stem="testMixin",
        members=MixinMembers(),
        divergences=[],
    )

    result = _build_divergence_section(entry, Path("fake.js"), Path("project"))
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_divergence_detector.py::test_build_divergence_section_renders_table -v`
Expected: ImportError — `_build_divergence_section` not found.

- [ ] **Step 3: Implement `_build_divergence_section`**

Add to `vue3_migration/reporting/markdown.py` (near other helper functions, before `_append_composable_steps`):

```python
def _build_divergence_section(
    entry: "MixinEntry",
    composable_path: "Path | None",
    project_root: "Path | None",
) -> str:
    """Build a markdown section showing divergences between mixin and composable members."""
    if not entry.divergences:
        return ""

    lines: list[str] = []
    # Reuse existing _rel_link() helper (markdown.py:612) for file links
    comp_link = _rel_link(composable_path, project_root) if project_root and composable_path else f"`{composable_path}`"
    mixin_link = _rel_link(entry.mixin_path, project_root) if project_root else f"`{entry.mixin_path}`"

    lines.append(f"\n#### Implementation Divergences")
    lines.append(f"> {comp_link} · {mixin_link}\n")

    for div in entry.divergences:
        total = div.divergent_count + div.manual_review_count
        summary_parts = []
        if div.divergent_count:
            summary_parts.append(f"{div.divergent_count} divergent line{'s' if div.divergent_count != 1 else ''}")
        if div.manual_review_count:
            summary_parts.append(f"{div.manual_review_count} manual review")
        summary = ", ".join(summary_parts)

        lines.append(f"<details>")
        lines.append(f"<summary><b>{div.member_name}</b> — {summary}</summary>\n")
        lines.append(f"| Line | Mixin (expected) | Composable (actual) |")
        lines.append(f"|------|-----------------|---------------------|")

        for dl in div.divergent_lines:
            expected_cell = f"`{dl.expected}`" if dl.expected else ""
            if dl.actual is None:
                actual_cell = "*(missing — manual review)* :warning:" if dl.manual_review else "*(missing)*"
            elif dl.manual_review:
                actual_cell = f"`{dl.actual}` :warning:"
            else:
                actual_cell = f"`{dl.actual}`"
            lines.append(f"| {dl.line_hint} | {expected_cell} | {actual_cell} |")

        lines.append(f"\n</details>\n")

    return "\n".join(lines)
```

Note: Do NOT create a `_relative_path` helper — reuse the existing `_rel_link()` function at `markdown.py:612` which already generates markdown links with relative paths.

- [ ] **Step 4: Add `project_root` parameter to `_append_composable_steps` and integrate divergence section**

`project_root` is NOT currently available inside `_append_composable_steps()`. It must be added as a parameter.

In `vue3_migration/reporting/markdown.py`, modify the signature at line 1581:

```python
def _append_composable_steps(
    a: "callable",
    entry: MixinEntry,
    dot: str,
    composable_content_map: "dict[Path, str] | None" = None,
    composable_path_by_stem: "dict[str, Path] | None" = None,
    component_content_map: "dict[Path, str] | None" = None,
    project_root: "Path | None" = None,  # NEW
) -> None:
```

Update both call sites in `build_action_plan()` (lines 1238 and 1244) to pass `project_root`:

```python
# Line 1238:
_append_composable_steps(a, entry, "\U0001f7e1", composable_content_map, composable_path_by_stem, component_content_map, project_root)
# Line 1244:
_append_composable_steps(a, entry, "\U0001f534", composable_content_map, composable_path_by_stem, component_content_map, project_root)
```

Then at the end of `_append_composable_steps()`, after the existing warning steps, add:

```python
    # Divergence section
    if entry.divergences:
        a(_build_divergence_section(entry, comp_path, project_root))
```

- [ ] **Step 5: Run report rendering tests**

Run: `pytest tests/test_divergence_detector.py -k "build_divergence" -v`
Expected: Both tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add vue3_migration/reporting/markdown.py tests/test_divergence_detector.py
git commit -m "feat: render divergence detection results in migration report"
```

---

### Task 7: End-to-end verification against dummy project

**Files:**
- No new files — verification only

- [ ] **Step 1: Create a test fixture with a known divergence**

In `tests/fixtures/dummy_project/`, find a composable that covers a mixin member and intentionally modify one line to create a divergence. Or create a small standalone mixin + composable pair with a deliberate difference.

- [ ] **Step 2: Run status report**

Run: `python -m vue3_migration status tests/fixtures/dummy_project`
Expected: Report generates without errors. Check that divergence sections appear for the fixture with the known divergence.

- [ ] **Step 3: Run full migration**

Run: `python -m vue3_migration all tests/fixtures/dummy_project`
Expected: Report includes the divergence sections in the action plan. No crashes or errors.

- [ ] **Step 4: Verify no false positives**

Review the report output. Composable members that match their mixin equivalents should NOT have divergence entries. Only the deliberately different member should be flagged.

- [ ] **Step 5: Run full test suite one final time**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 6: Commit any fixture changes**

```bash
git add tests/fixtures/
git commit -m "test: add divergence detection fixture for e2e verification"
```
