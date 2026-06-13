# tests/test_composable_patcher.py
from vue3_migration.models import MixinMembers
from vue3_migration.transform.composable_patcher import (
    add_keys_to_return,
    add_members_to_composable,
    generate_member_declaration,
    patch_composable,
)

COMPOSABLE_BASIC = (
    "export function useX() {\n"
    "  const a = ref(1)\n"
    "  return { a }\n"
    "}\n"
)

def test_add_keys_to_return_basic():
    result = add_keys_to_return(COMPOSABLE_BASIC, ["b"])
    assert "b" in result
    assert result.index("b") > result.index("return {")

def test_add_keys_to_return_idempotent():
    result = add_keys_to_return(COMPOSABLE_BASIC, ["a"])
    assert result.count("a") == COMPOSABLE_BASIC.count("a")

def test_add_keys_to_return_no_return_unchanged():
    src = "export function useX() { const a = ref(1) }\n"
    assert add_keys_to_return(src, ["a"]) == src

def test_add_members_inserts_before_return():
    result = add_members_to_composable(COMPOSABLE_BASIC, ["  const b = ref(2)"])
    assert result.index("const b") < result.index("return")

def test_add_members_skips_existing_name():
    result = add_members_to_composable(COMPOSABLE_BASIC, ["  const a = ref(999)"])
    assert result.count("const a") == 1

def test_patch_composable_adds_not_returned_to_return():
    """BLOCKED_NOT_RETURNED: member defined in body but missing from return."""
    src = (
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  function reset() { a.value = 0 }\n"
        "  return { a }\n"
        "}\n"
    )
    mixin = "export default { data() { return { a: 1 } }, methods: { reset() {} } }"
    members = MixinMembers(data=["a"], methods=["reset"])
    result = patch_composable(src, mixin, not_returned=["reset"], missing=[], mixin_members=members)
    return_section = result[result.index("return {"):]
    assert "reset" in return_section.split("}")[0]

def test_patch_composable_adds_missing_member():
    """BLOCKED_MISSING_MEMBERS: member absent from composable entirely."""
    src = (
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  return { a }\n"
        "}\n"
    )
    mixin = (
        "export default {\n"
        "  data() { return { a: 1 } },\n"
        "  computed: {\n"
        "    double() { return this.a * 2 }\n"
        "  }\n"
        "}\n"
    )
    members = MixinMembers(data=["a"], computed=["double"])
    result = patch_composable(src, mixin, not_returned=[], missing=["double"], mixin_members=members)
    assert "double" in result
    assert result.index("double") < result.index("return {")

def test_generate_member_declaration_data():
    mixin = "export default { data() { return { count: 0 } } }"
    members = MixinMembers(data=["count"])
    decl = generate_member_declaration("count", mixin, members, ["count"], [])
    assert "ref(" in decl
    assert "count" in decl

def test_generate_member_declaration_method():
    mixin = "export default { methods: { reset() { this.count = 0 } } }"
    members = MixinMembers(data=["count"], methods=["reset"])
    decl = generate_member_declaration("reset", mixin, members, ["count"], ["reset"])
    assert "function reset" in decl

def test_generate_member_declaration_computed():
    mixin = "export default { computed: { double() { return this.count * 2 } } }"
    members = MixinMembers(data=["count"], computed=["double"])
    decl = generate_member_declaration("double", mixin, members, ["count"], [])
    assert "computed(" in decl
    assert "double" in decl


# --- Bug 5: method body indentation in patched composables ---

def test_generate_member_declaration_method_not_double_indented():
    """Method body should have exactly 4-space (inner) indentation.

    Note: generate_member_declaration uses extract_hook_body on the full mixin
    source, which excludes methods blocks (R-2). So we test with a method-like
    function at the top level of the export default object.
    """
    mixin = """export default {
  save(data) {
    this.items.push(data)
    this.count++
  }
}"""
    members = MixinMembers(data=["items", "count"], methods=["save"])
    decl = generate_member_declaration("save", mixin, members, ["items", "count"], ["save"])
    lines = decl.splitlines()
    body_lines = [l for l in lines if "items" in l or "count" in l]
    assert len(body_lines) >= 2, f"Expected at least 2 body lines, found: {body_lines}"
    for line in body_lines:
        stripped = line.lstrip()
        indent_len = len(line) - len(stripped)
        assert indent_len == 4, (
            f"Expected 4-space indent, got {indent_len}: {repr(line)}"
        )


# ---------------------------------------------------------------------------
# Lifecycle hook patching
# ---------------------------------------------------------------------------

LOGGING_COMPOSABLE = (
    "import { ref } from 'vue'\n\n"
    "export function useLogging() {\n"
    "  const logs = ref([])\n"
    "\n"
    "  function log(message) {\n"
    "    logs.value.push({ message, time: Date.now() })\n"
    "  }\n"
    "\n"
    "  return {\n"
    "    logs,\n"
    "    log,\n"
    "  }\n"
    "}\n"
)

LOGGING_MIXIN = (
    "export default {\n"
    "  data() { return { logs: [] } },\n"
    "  methods: {\n"
    "    log(message) { this.logs.push({ message, time: Date.now() }) },\n"
    "  },\n"
    "  created() {\n"
    "    this.log('Component created')\n"
    "  },\n"
    "  mounted() {\n"
    "    this.log('Component mounted')\n"
    "  },\n"
    "  beforeDestroy() {\n"
    "    this.log('Component will be destroyed')\n"
    "  },\n"
    "}\n"
)


def test_patch_adds_lifecycle_hooks():
    """patch_composable should add lifecycle hooks when lifecycle_hooks is passed."""
    members = MixinMembers(data=["logs"], methods=["log"])
    result = patch_composable(
        LOGGING_COMPOSABLE, LOGGING_MIXIN,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["created", "mounted", "beforeDestroy"],
    )
    # Inline hook (created) body should be present
    assert "log('Component created')" in result
    # Wrapped hooks
    assert "onMounted(" in result
    assert "onBeforeUnmount(" in result
    # Hooks before return
    assert result.index("onMounted(") < result.index("return {")
    # Vue imports added
    assert "onMounted" in result.splitlines()[0] or any(
        "onMounted" in l for l in result.splitlines() if "import" in l
    )


def test_patch_skips_existing_hooks():
    """patch_composable should not duplicate hooks already in the composable."""
    src = (
        "import { ref, onMounted } from 'vue'\n\n"
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "\n"
        "  onMounted(() => {\n"
        "    console.log('already here')\n"
        "  })\n"
        "\n"
        "  return { a }\n"
        "}\n"
    )
    mixin = "export default { data() { return { a: 1 } }, mounted() { console.log('hi') } }"
    members = MixinMembers(data=["a"])
    result = patch_composable(
        src, mixin,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["mounted"],
    )
    assert result.count("onMounted(") == 1


def test_patch_no_hooks_param_unchanged():
    """Without lifecycle_hooks param, patch_composable behaves as before."""
    result = patch_composable(
        LOGGING_COMPOSABLE, LOGGING_MIXIN,
        not_returned=[], missing=[],
        mixin_members=MixinMembers(data=["logs"], methods=["log"]),
    )
    assert "onMounted" not in result


# ---------------------------------------------------------------------------
# Phase 5: Stale comment removal (Issues #24, #25)
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_patcher import _remove_stale_comments


def test_stale_not_defined_comments_removed():
    """Stale 'NOT defined' comments should be removed when member IS defined."""
    source = '''const count = ref(0)
// MIGRATION: count is NOT defined in composable scope
function increment() { count.value++ }
return { count, increment }'''
    result = _remove_stale_comments(source)
    assert 'NOT defined' not in result
    assert 'const count' in result  # actual code preserved


def test_stale_not_returned_comments_removed():
    """Stale 'NOT returned' comments should be removed when member IS returned."""
    source = '''const count = ref(0)
// MIGRATION: count is NOT returned from composable
function increment() { count.value++ }
return { count, increment }'''
    result = _remove_stale_comments(source)
    assert 'NOT returned' not in result
    assert 'const count' in result


def test_valid_not_defined_comment_preserved():
    """'NOT defined' comment should be preserved when member truly is not defined."""
    source = '''// MIGRATION: missingFunc is NOT defined in composable scope
return { count }'''
    result = _remove_stale_comments(source)
    assert 'NOT defined' in result


def test_code_lines_preserved_when_removing_stale():
    """Non-comment lines should not be removed."""
    source = '''const count = ref(0)
// MIGRATION: count is NOT defined in composable scope
function increment() { count.value++ }
return { count, increment }'''
    result = _remove_stale_comments(source)
    assert 'function increment' in result
    assert 'return { count, increment }' in result


def test_remove_stale_comment_are_not_pattern():
    """Comments with 'X and Y are NOT defined' should be removed when both are defined."""
    src = (
        "const canDelete = ref(false)\n"
        "const hasRole = ref(false)\n"
        "// NOTE: canDelete and hasRole are NOT defined in this composable\n"
        "return { canDelete, hasRole }\n"
    )
    result = _remove_stale_comments(src)
    assert "are NOT defined" not in result


def test_remove_stale_comment_is_not_still_works():
    """Single-member 'X is NOT defined' pattern should still be removed when defined."""
    src = (
        "const count = ref(0)\n"
        "// NOTE: count is NOT defined in this composable\n"
        "return { count }\n"
    )
    result = _remove_stale_comments(src)
    assert "is NOT defined" not in result


def test_keep_stale_comment_when_not_defined():
    """Comment should be kept when the member is genuinely NOT defined."""
    src = (
        "const a = ref(1)\n"
        "// NOTE: missingThing is NOT defined in this composable\n"
        "return { a }\n"
    )
    result = _remove_stale_comments(src)
    assert "missingThing is NOT defined" in result


def test_remove_stale_comment_not_returned_pattern():
    """'X is NOT returned' comments should also be removed when X is returned."""
    src = (
        "const foo = ref(1)\n"
        "// NOTE: foo is NOT returned from this composable\n"
        "return { foo }\n"
    )
    result = _remove_stale_comments(src)
    assert "is NOT returned" not in result


# ---------------------------------------------------------------------------
# Phase 6: Return formatting improvements (Issue #27)
# ---------------------------------------------------------------------------

def test_return_formatting_multiline_when_long():
    """When adding keys would exceed 80 chars, return should become multi-line."""
    source = '''export function useTest() {
  const a = ref(0)
  return { a }
}'''
    result = add_keys_to_return(source, ['longVariableName', 'anotherLongName', 'yetAnotherName', 'extraVariable'])
    # All members should be in the return
    assert 'a' in result
    assert 'longVariableName' in result
    assert 'anotherLongName' in result
    assert 'yetAnotherName' in result
    assert 'extraVariable' in result


def test_return_formatting_multiline_existing():
    """When existing return is multi-line, new keys should be on their own lines."""
    source = '''export function useTest() {
  const a = ref(0)
  return {
    a,
  }
}'''
    result = add_keys_to_return(source, ['b', 'c'])
    # All members should be in the return
    assert 'a' in result
    assert 'b' in result
    assert 'c' in result
    # New keys should be on their own lines
    lines = result.splitlines()
    b_lines = [l for l in lines if l.strip() == 'b,']
    c_lines = [l for l in lines if l.strip() == 'c,']
    assert len(b_lines) >= 1, "b should be on its own line"
    assert len(c_lines) >= 1, "c should be on its own line"


def test_return_formatting_short_stays_single_line():
    """When adding keys keeps line under 80 chars, return stays single-line."""
    source = '''export function useTest() {
  const a = ref(0)
  return { a }
}'''
    result = add_keys_to_return(source, ['b'])
    # Should stay on one line
    return_line = [l for l in result.splitlines() if 'return' in l][0]
    assert 'a' in return_line
    assert 'b' in return_line


# ---------------------------------------------------------------------------
# Phase 6: Computed arrow shorthand in patcher (Issue #26)
# ---------------------------------------------------------------------------

def test_generate_member_declaration_computed_arrow_shorthand():
    """Computed with single return should use arrow shorthand in patcher too."""
    mixin = "export default { computed: { double() { return this.count * 2 } } }"
    members = MixinMembers(data=["count"], computed=["double"])
    decl = generate_member_declaration("double", mixin, members, ["count"], [])
    assert "computed(() => count.value * 2)" in decl
    assert "{ return" not in decl


# ---------------------------------------------------------------------------
# Task 2: Trailing comma fix in add_keys_to_return (multi-line)
# ---------------------------------------------------------------------------

COMPOSABLE_MULTILINE_NO_TRAILING_COMMA = (
    "export function useX() {\n"
    "  const a = ref(1)\n"
    "  const b = ref(2)\n"
    "  return {\n"
    "    a,\n"
    "    b\n"
    "  }\n"
    "}\n"
)

def test_add_keys_multiline_adds_comma_to_last_member():
    """When appending to multi-line return, a comma must be added after the last existing member."""
    result = add_keys_to_return(COMPOSABLE_MULTILINE_NO_TRAILING_COMMA, ["c"])
    lines = result.split('\n')
    b_line = [l for l in lines if l.strip().startswith('b') and 'ref' not in l][0]
    assert b_line.rstrip().endswith(','), f"Expected trailing comma on b line: '{b_line}'"

def test_add_keys_multiline_no_duplicate_comma():
    """When last member already has a trailing comma, don't add another."""
    src = (
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  return {\n"
        "    a,\n"
        "  }\n"
        "}\n"
    )
    result = add_keys_to_return(src, ["b"])
    lines = result.split('\n')
    a_line = [l for l in lines if l.strip().startswith('a') and 'ref' not in l][0]
    assert a_line.strip() == 'a,', f"Expected exactly one comma: '{a_line.strip()}'"

def test_add_keys_multiline_produces_valid_syntax():
    """Every member line in the return block should end with a comma."""
    result = add_keys_to_return(COMPOSABLE_MULTILINE_NO_TRAILING_COMMA, ["c", "d"])
    ret_start = result.index("return {")
    ret_end = result.index("}", ret_start + len("return {")) + 1
    ret_block = result[ret_start:ret_end]
    inner_lines = ret_block.split('\n')[1:-1]
    for line in inner_lines:
        stripped = line.strip()
        if stripped:
            assert stripped.endswith(','), f"Line missing comma: '{stripped}'"


# ---------------------------------------------------------------------------
# Bug 1: add_keys_to_return destroys closing braces
# ---------------------------------------------------------------------------

COMPOSABLE_TWO_CLOSING_BRACES = (
    "export function usePermission() {\n"
    "  const userPermissions = ref([])\n"
    "\n"
    "  function requestPermission(action) {\n"
    "    userPermissions.value.push(action)\n"
    "  }\n"
    "\n"
    "  return {\n"
    "    userPermissions,\n"
    "    requestPermission\n"
    "  }\n"
    "}\n"
)


def test_add_keys_preserves_both_closing_braces():
    """Adding keys must preserve both the return } and the function }."""
    result = add_keys_to_return(COMPOSABLE_TWO_CLOSING_BRACES, ["canDelete"])
    lines = result.strip().splitlines()
    # Must have exactly 2 closing-brace-only lines at the end
    tail = [l.strip() for l in lines[-2:]]
    assert tail == ["}", "}"], f"Expected ['}}', '}}'], got {tail}"


def test_add_keys_correct_indentation():
    """New keys must have the same indentation as existing members (4 spaces)."""
    result = add_keys_to_return(COMPOSABLE_TWO_CLOSING_BRACES, ["canDelete"])
    cd_line = next(l for l in result.splitlines() if "canDelete" in l)
    indent = len(cd_line) - len(cd_line.lstrip())
    assert indent == 4, f"Expected 4-space indent, got {indent}: {repr(cd_line)}"


def test_add_keys_no_blank_line_before_close():
    """There should be no blank line between last member and closing }."""
    result = add_keys_to_return(COMPOSABLE_TWO_CLOSING_BRACES, ["canDelete"])
    lines = result.splitlines()
    close_idx = next(i for i in range(len(lines) - 1, -1, -1) if lines[i].strip() == "}")
    prev_line = lines[close_idx - 1].strip()
    assert prev_line != "", f"Blank line before closing brace: {lines[close_idx-2:close_idx+1]}"


# ---------------------------------------------------------------------------
# Bug 2: add_members_to_composable inserts at nested return
# ---------------------------------------------------------------------------

COMPOSABLE_WITH_NESTED_RETURN = (
    "import { ref, computed } from 'vue'\n"
    "\n"
    "export function useChart() {\n"
    "  const chartData = ref(null)\n"
    "  const isChartReady = ref(false)\n"
    "\n"
    "  const formattedChartData = computed(() => {\n"
    "    if (!chartData.value) return null\n"
    "    return {\n"
    "      labels: chartData.value.labels || [],\n"
    "      datasets: chartData.value.datasets || []\n"
    "    }\n"
    "  })\n"
    "\n"
    "  function updateChart() {\n"
    "    isChartReady.value = true\n"
    "  }\n"
    "\n"
    "  return {\n"
    "    chartData,\n"
    "    isChartReady,\n"
    "    formattedChartData,\n"
    "    updateChart,\n"
    "  }\n"
    "}\n"
)


def test_add_members_uses_last_return_not_nested():
    """Members must be inserted before the top-level return, not a nested one."""
    hook = "  onMounted(() => {\n    resizeChart()\n  })"
    result = add_members_to_composable(COMPOSABLE_WITH_NESTED_RETURN, [hook])
    # onMounted must come AFTER the computed block, before the final return
    assert "onMounted" in result
    computed_end = result.index("})")  # end of computed(() => { ... })
    onmounted_pos = result.index("onMounted")
    last_return_pos = result.rfind("return {")
    assert onmounted_pos > computed_end, "onMounted should be after computed block"
    assert onmounted_pos < last_return_pos, "onMounted should be before final return"


# ---------------------------------------------------------------------------
# Bug 3: Lifecycle hooks reference undefined methods
# ---------------------------------------------------------------------------

MODAL_COMPOSABLE = (
    "import { ref, computed } from 'vue'\n\n"
    "export function useModal() {\n"
    "  const isOpen = ref(false)\n"
    "  const modalData = ref(null)\n"
    "  const modalOptions = ref({})\n\n"
    "  const modalTitle = computed(() => modalOptions.value.title || 'Modal')\n"
    "  const hasData = computed(() => modalData.value !== null)\n\n"
    "  function openModal(data, options) {\n"
    "    modalData.value = data\n"
    "    modalOptions.value = options || {}\n"
    "    isOpen.value = true\n"
    "  }\n\n"
    "  function closeModal() {\n"
    "    isOpen.value = false\n"
    "    modalData.value = null\n"
    "    modalOptions.value = {}\n"
    "  }\n\n"
    "  function confirmModal() {\n"
    "    const callback = modalOptions.value.onConfirm\n"
    "    if (typeof callback === 'function') {\n"
    "      callback(modalData.value)\n"
    "    }\n"
    "    closeModal()\n"
    "  }\n\n"
    "  return {\n"
    "    isOpen,\n"
    "    modalData,\n"
    "    modalOptions,\n"
    "    modalTitle,\n"
    "    hasData,\n"
    "    openModal,\n"
    "    closeModal,\n"
    "    confirmModal,\n"
    "  }\n"
    "}\n"
)

MODAL_MIXIN = (
    "export default {\n"
    "  data() {\n"
    "    return { isOpen: false, modalData: null, modalOptions: {} }\n"
    "  },\n"
    "  computed: {\n"
    "    modalTitle() { return this.modalOptions.title || 'Modal' },\n"
    "    hasData() { return !!this.modalData },\n"
    "  },\n"
    "  methods: {\n"
    "    openModal(data, options) { this.modalData = data; this.isOpen = true },\n"
    "    closeModal() { this.isOpen = false; this.modalData = null },\n"
    "    confirmModal() { this.closeModal() },\n"
    "    _handleEscapeKey(event) {\n"
    "      if (event.key === 'Escape' && this.isOpen) {\n"
    "        this.closeModal()\n"
    "      }\n"
    "    },\n"
    "  },\n"
    "  mounted() {\n"
    "    document.addEventListener('keydown', this._handleEscapeKey)\n"
    "  },\n"
    "  beforeUnmount() {\n"
    "    document.removeEventListener('keydown', this._handleEscapeKey)\n"
    "  },\n"
    "}\n"
)


def test_patch_generates_methods_referenced_by_lifecycle_hooks():
    """When lifecycle hooks reference a mixin method not in the composable,
    the patcher must generate that method before adding the hooks."""
    members = MixinMembers(
        data=["isOpen", "modalData", "modalOptions"],
        computed=["modalTitle", "hasData"],
        methods=["openModal", "closeModal", "confirmModal", "_handleEscapeKey"],
    )
    result = patch_composable(
        MODAL_COMPOSABLE, MODAL_MIXIN,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["mounted", "beforeUnmount"],
    )
    assert "function _handleEscapeKey" in result, (
        "_handleEscapeKey should be generated since lifecycle hooks reference it"
    )
    assert "onMounted(" in result
    assert "onBeforeUnmount(" in result
    # _handleEscapeKey must be defined BEFORE onMounted uses it
    assert result.index("function _handleEscapeKey") < result.index("onMounted(")


# ---------------------------------------------------------------------------
# Mixin import propagation
# ---------------------------------------------------------------------------

from pathlib import Path

def test_patch_skips_already_inlined_created_hook():
    """Running patch_composable twice should not duplicate created hook content."""
    members = MixinMembers(data=["logs"], methods=["log"])
    # First run
    first = patch_composable(
        LOGGING_COMPOSABLE, LOGGING_MIXIN,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["created"],
    )
    # Second run on already-patched output
    second = patch_composable(
        first, LOGGING_MIXIN,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["created"],
    )
    # The created hook body should appear exactly once
    count = second.count("log('Component created')")
    assert count == 1, f"Expected 1 occurrence, got {count}"


def test_patch_composable_adds_mixin_imports():
    """Patching a composable should add mixin imports used by new members."""
    composable_src = (
        "import { ref } from 'vue'\n\n"
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  return { a }\n"
        "}\n"
    )
    mixin_src = (
        "import { helperUtil } from '../utils/helpers'\n"
        "import { unusedLib } from '../lib/unused'\n\n"
        "export default {\n"
        "  data() { return { a: 1 } },\n"
        "  methods: {\n"
        "    doWork() { return helperUtil(this.a) },\n"
        "  },\n"
        "}\n"
    )
    members = MixinMembers(data=["a"], methods=["doWork"])
    result = patch_composable(
        composable_content=composable_src,
        mixin_content=mixin_src,
        not_returned=[],
        missing=["doWork"],
        mixin_members=members,
        mixin_path=Path("/project/src/mixins/xMixin.js"),
        composable_path=Path("/project/src/composables/useX.js"),
    )
    assert "import { helperUtil } from '../utils/helpers'" in result
    assert "unusedLib" not in result

def test_patch_composable_no_duplicate_imports():
    """If the composable already has the import, don't add it again."""
    composable_src = (
        "import { helperUtil } from '../utils/helpers'\n"
        "import { ref } from 'vue'\n\n"
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  return { a }\n"
        "}\n"
    )
    mixin_src = (
        "import { helperUtil } from '../utils/helpers'\n\n"
        "export default {\n"
        "  data() { return { a: 1 } },\n"
        "  methods: {\n"
        "    doWork() { return helperUtil(this.a) },\n"
        "  },\n"
        "}\n"
    )
    members = MixinMembers(data=["a"], methods=["doWork"])
    result = patch_composable(
        composable_content=composable_src,
        mixin_content=mixin_src,
        not_returned=[],
        missing=["doWork"],
        mixin_members=members,
        mixin_path=Path("/project/src/mixins/xMixin.js"),
        composable_path=Path("/project/src/composables/useX.js"),
    )
    # Count import lines containing helperUtil (not function calls)
    import_lines = [l for l in result.split("\n") if l.strip().startswith("import") and "helperUtil" in l]
    assert len(import_lines) == 1


def test_add_members_skips_duplicate_unnamed_lines():
    """add_members_to_composable should not re-add lines already in the composable."""
    composable = (
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  doSomething()\n"
        "\n"
        "  return { a }\n"
        "}\n"
    )
    result = add_members_to_composable(composable, ["  doSomething()"])
    assert result.count("doSomething()") == 1


# ---------------------------------------------------------------------------
# Indirect return support (const obj = { ... }; return obj)
# ---------------------------------------------------------------------------

COMPOSABLE_INDIRECT_RETURN = (
    "import { ref } from 'vue'\n\n"
    "export function useSearch() {\n"
    "  function search() {\n"
    "    console.log('searching')\n"
    "  }\n\n"
    "  const api = { search }\n"
    "  return api\n"
    "}\n"
)


def test_add_keys_to_indirect_return():
    """add_keys_to_return should add keys to the variable's object literal."""
    result = add_keys_to_return(COMPOSABLE_INDIRECT_RETURN, ["query"])
    assert "query" in result
    # Key should be in the api object, not a bare return {
    assert "{ search, query }" in result


def test_add_keys_to_indirect_return_idempotent():
    """Keys already in the object literal should not be duplicated."""
    result = add_keys_to_return(COMPOSABLE_INDIRECT_RETURN, ["search"])
    assert result.count("search") == COMPOSABLE_INDIRECT_RETURN.count("search")


def test_add_keys_to_indirect_return_multiline():
    """Indirect return with multi-line object literal should work."""
    src = (
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  const result = {\n"
        "    a,\n"
        "  }\n"
        "  return result\n"
        "}\n"
    )
    patched = add_keys_to_return(src, ["b"])
    assert "b," in patched
    assert "return result" in patched


def test_add_members_to_composable_indirect_return():
    """add_members_to_composable should insert before an indirect return."""
    result = add_members_to_composable(
        COMPOSABLE_INDIRECT_RETURN, ["  const query = ref('')"]
    )
    assert "const query" in result
    assert result.index("const query") < result.index("return api")


def test_patch_composable_indirect_return_missing_member():
    """Full patch_composable should handle indirect returns end-to-end."""
    mixin = "export default { data() { return { query: '' } }, methods: { search() {} } }"
    members = MixinMembers(data=["query"], methods=["search"])
    result = patch_composable(
        COMPOSABLE_INDIRECT_RETURN, mixin,
        not_returned=[], missing=["query"],
        mixin_members=members,
    )
    assert "const query = ref(" in result
    assert "query" in result.split("const api")[1].split("}")[0]


def test_patch_composable_indirect_return_not_returned():
    """patch_composable should add not-returned keys to indirect return object."""
    src = (
        "import { ref } from 'vue'\n\n"
        "export function useX() {\n"
        "  const a = ref(1)\n"
        "  function reset() { a.value = 0 }\n"
        "  const api = { a }\n"
        "  return api\n"
        "}\n"
    )
    mixin = "export default { data() { return { a: 1 } }, methods: { reset() {} } }"
    members = MixinMembers(data=["a"], methods=["reset"])
    result = patch_composable(
        src, mixin,
        not_returned=["reset"], missing=[],
        mixin_members=members,
    )
    # reset should be added to the api object
    api_section = result.split("const api")[1].split("}")[0]
    assert "reset" in api_section


# ---------------------------------------------------------------------------
# Bug: add_keys_to_return fails after add_members_to_composable inserts
# function declarations (naive brace counter finds wrong closing brace)
# ---------------------------------------------------------------------------

COMPOSABLE_EXPORT = (
    "import { ref } from 'vue'\n\n"
    "export function useExport() {\n"
    "  const exportData = ref(null)\n\n"
    "  function exportToCSV() {\n"
    "    console.log('export to csv')\n"
    "  }\n\n"
    "  function downloadFile(data) {\n"
    "    const blob = new Blob([data], { type: 'text/csv' })\n"
    "    console.log('downloading', blob)\n"
    "  }\n\n"
    "  return {\n"
    "    exportData,\n"
    "    exportToCSV,\n"
    "    downloadFile,\n"
    "  }\n"
    "}\n"
)


def test_add_keys_to_return_after_add_members():
    """add_keys_to_return must work after add_members_to_composable inserts
    function declarations containing braces (the naive brace counter bug)."""
    # Step 1: add a new function (exportToPDF) to the body
    new_func = "  function exportToPDF() {\n    console.log('export to pdf')\n  }"
    content = add_members_to_composable(COMPOSABLE_EXPORT, [new_func])
    assert "function exportToPDF" in content

    # Step 2: add the key to the return
    result = add_keys_to_return(content, ["exportToPDF"])

    # The key MUST appear in the return block
    return_start = result.rfind("return {")
    assert return_start != -1, "return statement not found"
    return_section = result[return_start:]
    close_brace = return_section.index("}")
    return_keys = return_section[:close_brace]
    assert "exportToPDF" in return_keys, (
        f"exportToPDF not found in return block. Return section:\n{return_section[:200]}"
    )


def test_add_keys_to_return_with_strings_containing_braces():
    """Naive brace counting is fooled by braces inside string literals."""
    src = (
        "export function useTest() {\n"
        "  const msg = ref('hello { world }')\n"
        "  function doStuff() {\n"
        "    const template = `Result: ${msg.value}`\n"
        "  }\n"
        "  return {\n"
        "    msg,\n"
        "    doStuff,\n"
        "  }\n"
        "}\n"
    )
    result = add_keys_to_return(src, ["newKey"])
    return_start = result.rfind("return {")
    return_section = result[return_start:]
    close_brace = return_section.index("}")
    assert "newKey" in return_section[:close_brace], (
        f"newKey not in return block: {return_section[:200]}"
    )


def test_add_keys_to_return_string_with_unbalanced_braces():
    """A string containing an unbalanced brace should not fool the brace counter.

    This is the core scenario: a comment with an unmatched '{' inside the return
    block makes the naive brace counter think there's extra nesting, so it finds
    the WRONG closing brace (overshoots to the function's '}').
    """
    src = (
        "export function useTest() {\n"
        "  function format(x) {\n"
        "    return x\n"
        "  }\n"
        "\n"
        "  return {\n"
        "    format, // returns { data\n"
        "  }\n"
        "}\n"
    )
    result = add_keys_to_return(src, ["newKey"])
    return_start = result.rfind("return {")
    return_section = result[return_start:]
    close_brace = return_section.index("}")
    assert "newKey" in return_section[:close_brace], (
        f"newKey not in return block: {return_section[:200]}"
    )


# ---------------------------------------------------------------------------
# RPT-1: the inline banner's "manual steps" count must use the same covered-
# member suppression as the migration report, so the two never contradict
# (e.g. banner "2 manual steps needed" vs report "no manual steps needed").
# ---------------------------------------------------------------------------

_FORM_MIXIN = (
    "export default {\n"
    "  data() { return { formData: {}, isSubmitting: false } },\n"
    "  methods: {\n"
    "    initForm(data) { this.formData = data },\n"
    "    submitForm() {\n"
    "      this.isSubmitting = true\n"
    "      if (this.$refs.form) { this.$refs.form.reportValidity() }\n"
    "      this.$emit('form-submitted', this.formData)\n"
    "    }\n"
    "  }\n"
    "}\n"
)
_FORM_MEMBERS = MixinMembers(data=["formData", "isSubmitting"],
                             methods=["initForm", "submitForm"])


def test_banner_suppresses_covered_member_warnings():
    """A covered member (declared AND returned) whose mixin body uses $refs/$emit
    must not inflate the banner — the composable replaced that implementation."""
    src = (
        "export function useForm() {\n"
        "  const formData = ref({})\n"
        "  function initForm(data) { formData.value = { ...data } }\n"
        "  function submitForm() { return true }\n"
        "  return { formData, initForm, submitForm }\n"
        "}\n"
    )
    result = patch_composable(src, _FORM_MIXIN, not_returned=[], missing=[],
                              mixin_members=_FORM_MEMBERS)
    banner = result.splitlines()[0]
    assert "manual step" not in banner, f"covered $refs/$emit leaked into banner: {banner}"


def test_banner_keeps_uncovered_member_warnings():
    """The same mixin member, when NOT covered by the composable, must still be
    counted as a manual step — matching the report, which also keeps it."""
    src = (
        "export function useForm() {\n"
        "  const formData = ref({})\n"
        "  function initForm(data) { formData.value = { ...data } }\n"
        "  return { formData, initForm }\n"
        "}\n"
    )
    result = patch_composable(src, _FORM_MIXIN, not_returned=[], missing=[],
                              mixin_members=_FORM_MEMBERS)
    banner = result.splitlines()[0]
    assert "manual step" in banner, f"uncovered $refs/$emit missing from banner: {banner}"


# ---------------------------------------------------------------------------
# CG-1: `_`-prefixed lifecycle scratch must not be added to the return on patch
# ---------------------------------------------------------------------------

def test_patch_keeps_underscore_scratch_private():
    from vue3_migration.transform.composable_patcher import patch_composable
    from vue3_migration.models import MixinMembers
    mixin = """export default {
  data() { return { chartData: [], _debouncedResize: null } },
  methods: { renderChart() { return this.chartData } },
  mounted() {
    this._debouncedResize = () => this.renderChart()
    window.addEventListener('resize', this._debouncedResize)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this._debouncedResize)
  }
}
"""
    existing = (
        "import { ref } from 'vue'\n\n"
        "export function useChart() {\n"
        "  const chartData = ref([])\n"
        "  function renderChart() { return chartData.value }\n"
        "  return { chartData, renderChart }\n}\n"
    )
    members = MixinMembers(data=["chartData", "_debouncedResize"], methods=["renderChart"])
    out = patch_composable(existing, mixin, [], [], members, ["mounted", "beforeUnmount"])
    assert "_debouncedResize" in out  # declared inside the composable
    return_block = out.split("return {")[-1]
    assert "_debouncedResize" not in return_block  # but kept private

    # Idempotent: patching again does not duplicate the declaration.
    out2 = patch_composable(out, mixin, [], [], members, ["mounted", "beforeUnmount"])
    assert out2.count("const _debouncedResize") == 1


# ---------------------------------------------------------------------------
# CG-2: propagated mixin import groups into the import block (not above `vue`)
# ---------------------------------------------------------------------------

def test_propagated_import_grouped_below_vue_no_blank_damage(tmp_path):
    from vue3_migration.transform.composable_patcher import patch_composable
    from vue3_migration.models import MixinMembers
    (tmp_path / "mixins").mkdir()
    (tmp_path / "composables").mkdir()
    mixin_path = tmp_path / "mixins" / "chartMixin.js"
    mixin_path.write_text(
        "import { debounce } from '@/utils/helpers'\n\n"
        "export default {\n"
        "  data() { return { chartData: [] } },\n"
        "  methods: { renderChart() { return this.chartData } },\n"
        "  mounted() { this.handler = debounce(() => this.renderChart(), 100) }\n}\n"
    )
    comp_path = tmp_path / "composables" / "useChart.js"
    existing = (
        "import { ref } from 'vue'\n\n"
        "export function useChart() {\n"
        "  const chartData = ref([])\n"
        "  function renderChart() { return chartData.value }\n"
        "  return { chartData, renderChart }\n}\n"
    )
    members = MixinMembers(data=["chartData"], methods=["renderChart"])
    out = patch_composable(
        existing, mixin_path.read_text(), [], [], members, ["mounted"],
        mixin_path=mixin_path, composable_path=comp_path,
    )
    lines = out.splitlines()
    vue_idx = next(i for i, l in enumerate(lines) if "from 'vue'" in l)
    helper_idx = next(i for i, l in enumerate(lines) if "@/utils/helpers" in l)
    # Propagated import sits AFTER the vue import (grouped), not above it.
    assert helper_idx > vue_idx
    # No stray blank-line damage in the import block.
    assert "\n\n\n" not in out
    assert lines[vue_idx + 1].startswith("import { debounce }")


# ---------------------------------------------------------------------------
# CORR-5: a shared composable re-patched by a 2nd component must not flip its
# banner to "✅ 0 issues" while its body still contains a crashing this.$el.
# CORR-6: an inlined hook/method body that reads a component-provided this.<prop>
# must be flagged, not shipped silently under a green banner.
# ---------------------------------------------------------------------------

THEME_MIXIN = (
    "export default {\n"
    "  data() { return { theme: 'light' } },\n"
    "  methods: {\n"
    "    applyTheme() {\n"
    "      this.$el.style.background = this.theme\n"
    "      this.$forceUpdate()\n"
    "    },\n"
    "  },\n"
    "}\n"
)


def test_corr5_banner_warns_when_adding_member_with_this_el():
    """First component to patch applyTheme in: banner must warn (not ✅)."""
    comp = (
        "import { ref } from 'vue'\n\n"
        "export function useTheme() {\n"
        "  const theme = ref('light')\n"
        "  return { theme }\n"
        "}\n"
    )
    members = MixinMembers(data=["theme"], methods=["applyTheme"])
    out = patch_composable(comp, THEME_MIXIN, [], ["applyTheme"], members)
    assert "this.$el" in out  # construct is inlined verbatim
    assert out.splitlines()[0].startswith("// ⚠️")  # ⚠️ banner
    assert not out.splitlines()[0].startswith("// ✅")     # never ✅


def test_corr5_banner_stays_warning_when_member_already_covered():
    """Re-patching a composable that ALREADY covers applyTheme (declared+returned)
    must keep the ⚠️ banner — the body still has this.$el, so it is NOT clean."""
    covered = (
        "import { ref } from 'vue'\n\n"
        "export function useTheme() {\n"
        "  const theme = ref('light')\n"
        "  function applyTheme() {\n"
        "    this.$el.style.background = theme.value\n"
        "    this.$forceUpdate()\n"
        "  }\n"
        "  return { theme, applyTheme }\n"
        "}\n"
    )
    members = MixinMembers(data=["theme"], methods=["applyTheme"])
    # missing=[]/not_returned=[]: applyTheme is already covered.
    out = patch_composable(covered, THEME_MIXIN, [], [], members)
    assert "this.$el" in out
    banner = out.splitlines()[0]
    assert banner.startswith("// ⚠️"), f"banner clobbered: {banner!r}"
    assert not banner.startswith("// ✅")


def test_corr6_component_prop_in_inlined_hook_is_flagged():
    """An inlined mounted() that reads a component prop (this.entityId) must be
    flagged with an inline annotation and a non-✅ banner, not shipped silently."""
    mixin = (
        "export default {\n"
        "  methods: { loadComments(id) { return id } },\n"
        "  mounted() { if (this.entityId) this.loadComments(this.entityId) },\n"
        "}\n"
    )
    comp = (
        "export function useComment() {\n"
        "  function loadComments(id) { return id }\n"
        "  return { loadComments }\n"
        "}\n"
    )
    members = MixinMembers(methods=["loadComments"])
    out = patch_composable(comp, mixin, [], [], members, lifecycle_hooks=["mounted"])
    # The component prop survives verbatim in the generated hook ...
    assert "this.entityId" in out
    # ... and must be flagged: banner not ✅, and the line carries a ❌ annotation.
    assert not out.splitlines()[0].startswith("// ✅")
    assert any("this.entityId" in l and "❌" in l for l in out.splitlines()), out
