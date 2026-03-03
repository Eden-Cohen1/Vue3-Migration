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
