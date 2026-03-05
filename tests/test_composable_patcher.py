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
