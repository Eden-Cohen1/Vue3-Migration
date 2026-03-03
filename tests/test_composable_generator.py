# tests/test_composable_generator.py
from vue3_migration.models import MixinMembers
from vue3_migration.transform.composable_generator import (
    mixin_stem_to_composable_name,
    generate_composable_from_mixin,
)

AUTH_MIXIN = """
export default {
  data() {
    return {
      isAuthenticated: false,
      currentUser: null,
    }
  },
  computed: {
    isAdmin() {
      return this.currentUser?.role === 'admin'
    },
  },
  methods: {
    logout() {
      this.isAuthenticated = false
      this.currentUser = null
    },
    checkAuth() {
      // check stored token
    },
  },
  created() {
    this.checkAuth()
  },
}
"""

MEMBERS = MixinMembers(
    data=["isAuthenticated", "currentUser"],
    computed=["isAdmin"],
    methods=["logout", "checkAuth"],
)


# ── name conversion ───────────────────────────────────────────────────────────

def test_mixin_stem_strips_mixin_suffix():
    assert mixin_stem_to_composable_name("authMixin") == "useAuth"

def test_mixin_stem_strips_mixin_suffix_lowercase():
    assert mixin_stem_to_composable_name("selectionmixin") == "useSelection"

def test_mixin_stem_no_suffix():
    assert mixin_stem_to_composable_name("auth") == "useAuth"

def test_mixin_stem_already_camel():
    assert mixin_stem_to_composable_name("selectionMixin") == "useSelection"

def test_mixin_stem_pagination():
    assert mixin_stem_to_composable_name("paginationMixin") == "usePagination"


# ── generated file structure ──────────────────────────────────────────────────

def test_generates_export_function():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "export function useAuth()" in result

def test_generates_ref_for_data():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "const isAuthenticated = ref(" in result
    assert "const currentUser = ref(" in result

def test_generates_computed():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "const isAdmin = computed(" in result

def test_generates_method():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "function logout(" in result
    assert "function checkAuth(" in result

def test_generates_return_statement():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "return {" in result
    for name in ["isAuthenticated", "currentUser", "isAdmin", "logout", "checkAuth"]:
        assert name in result.split("return {")[1]

def test_generates_vue_imports_ref():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "import {" in result
    assert "ref" in result.split("import {")[1].split("}")[0]

def test_generates_vue_imports_computed():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    assert "computed" in result.split("import {")[1].split("}")[0]

def test_lifecycle_hook_inlined_for_created():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, ["created"])
    # created() is inlined (not wrapped in onCreated)
    assert "onCreated" not in result
    assert "checkAuth()" in result

def test_lifecycle_hook_wrapped_for_mounted():
    mixin = """
export default {
  mounted() { this.init() },
  methods: { init() {} },
}
"""
    members = MixinMembers(methods=["init"])
    result = generate_composable_from_mixin(mixin, "myMixin", members, ["mounted"])
    assert "onMounted" in result
    assert "import {" in result
    assert "onMounted" in result.split("import {")[1].split("}")[0]

def test_no_imports_when_no_vue_apis_needed():
    mixin = "export default { methods: { greet() { console.log('hi') } } }"
    members = MixinMembers(methods=["greet"])
    result = generate_composable_from_mixin(mixin, "greetMixin", members, [])
    # No ref/computed needed, no lifecycle hooks
    assert "export function useGreet()" in result
    assert "function greet(" in result

def test_this_refs_rewritten_in_methods():
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    # In logout(), this.isAuthenticated -> isAuthenticated.value
    logout_body_start = result.index("function logout(")
    logout_section = result[logout_body_start:logout_body_start + 200]
    assert "isAuthenticated.value" in logout_section


# --- Bug 5: method body indentation in generated composables ---

def test_method_body_not_double_indented():
    """Method body lines should have exactly 4-space (inner) indentation,
    not original mixin indentation stacked on top of inner."""
    result = generate_composable_from_mixin(AUTH_MIXIN, "authMixin", MEMBERS, [])
    # Find lines inside the logout() function body specifically
    lines = result.splitlines()
    in_logout = False
    body_lines = []
    for line in lines:
        if "function logout(" in line:
            in_logout = True
            continue
        if in_logout:
            if line.strip() == "}":
                break
            if line.strip():
                body_lines.append(line)
    assert len(body_lines) >= 2, f"Expected at least 2 body lines, found: {body_lines}"
    for line in body_lines:
        stripped = line.lstrip()
        indent_len = len(line) - len(stripped)
        assert indent_len == 4, (
            f"Expected 4-space indent (inner), got {indent_len}: {repr(line)}"
        )
