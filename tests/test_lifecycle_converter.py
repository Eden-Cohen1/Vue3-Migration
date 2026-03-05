# tests/test_lifecycle_converter.py
"""Tests for vue3_migration.transform.lifecycle_converter."""
from vue3_migration.transform.lifecycle_converter import (
    HOOK_MAP,
    extract_hook_body,
    convert_lifecycle_hooks,
    get_required_imports,
)

MIXIN_SRC = """
export default {
  data() { return { logs: [] } },
  methods: {
    log(msg) { this.logs.push(msg) }
  },
  created() {
    this.log('created')
  },
  mounted() {
    this.log('mounted')
  },
  beforeDestroy() {
    this.log('destroy')
  },
}
"""

def test_extract_hook_body_mounted():
    body = extract_hook_body(MIXIN_SRC, "mounted")
    assert body is not None
    assert "log" in body

def test_extract_hook_body_missing_returns_none():
    body = extract_hook_body(MIXIN_SRC, "updated")
    assert body is None

def test_extract_hook_body_nested_braces():
    src = "export default { mounted() { if (x) { doA() } } }"
    body = extract_hook_body(src, "mounted")
    assert "if (x) { doA() }" in body

def test_mounted_wraps_with_onMounted():
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_SRC, ["mounted"], ref_members=["logs"], plain_members=["log"]
    )
    assert inline == []
    assert any("onMounted" in line for line in wrapped)
    assert any("log(" in line for line in wrapped)

def test_created_is_inlined_not_wrapped():
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_SRC, ["created"], ref_members=["logs"], plain_members=["log"]
    )
    assert any("log(" in line for line in inline)
    assert all("onMounted" not in line for line in wrapped)

def test_before_destroy_maps_to_onBeforeUnmount():
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_SRC, ["beforeDestroy"], ref_members=[], plain_members=["log"]
    )
    assert any("onBeforeUnmount" in line for line in wrapped)

def test_get_required_imports_excludes_inline_hooks():
    imports = get_required_imports(["mounted", "beforeDestroy", "created"])
    assert "onMounted" in imports
    assert "onBeforeUnmount" in imports
    assert "created" not in imports
    assert "onCreated" not in imports

def test_hook_map_covers_all_vue2_hooks():
    for hook in ["beforeCreate", "created", "beforeMount", "mounted",
                 "beforeUpdate", "updated", "beforeDestroy", "destroyed",
                 "activated", "deactivated", "errorCaptured"]:
        assert hook in HOOK_MAP


# --- Bug 2: lifecycle hook parameters must be preserved ---

MIXIN_WITH_ERROR_CAPTURED = """
export default {
  errorCaptured(err) {
    this.logHook('errorCaptured: ' + err.message)
    return false
  }
}
"""

def test_error_captured_preserves_params():
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_WITH_ERROR_CAPTURED, ["errorCaptured"],
        ref_members=[], plain_members=["logHook"]
    )
    joined = "\n".join(wrapped)
    assert "(err) =>" in joined, f"Expected (err) => but got: {joined}"


MIXIN_WITH_MULTI_PARAMS = """
export default {
  errorCaptured(err, vm, info) {
    this.logHook(err.message + info)
    return false
  }
}
"""

def test_error_captured_preserves_multiple_params():
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_WITH_MULTI_PARAMS, ["errorCaptured"],
        ref_members=[], plain_members=["logHook"]
    )
    joined = "\n".join(wrapped)
    assert "(err, vm, info) =>" in joined, f"Expected (err, vm, info) => but got: {joined}"


def test_hook_without_params_gets_empty_parens():
    """Hooks like mounted() that have no params should still produce () =>."""
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_SRC, ["mounted"], ref_members=["logs"], plain_members=["log"]
    )
    joined = "\n".join(wrapped)
    assert "() =>" in joined


# --- Bug 4: wrapped hook body indentation ---

MIXIN_WITH_MULTILINE_BODY = """
export default {
  mounted() {
    this.count++
    this.log('mounted')
  }
}
"""

def test_wrapped_hook_body_dedented():
    """Wrapped hook body lines should have exactly inner (4 spaces) indentation,
    not original mixin indentation stacked on top."""
    inline, wrapped = convert_lifecycle_hooks(
        MIXIN_WITH_MULTILINE_BODY, ["mounted"],
        ref_members=["count"], plain_members=["log"]
    )
    body_lines = [l for l in wrapped if "count" in l or "log(" in l]
    assert len(body_lines) == 2
    for line in body_lines:
        assert line.startswith("    "), f"Expected 4-space indent, got: {repr(line)}"
        assert not line.startswith("      "), f"Over-indented (6+ spaces): {repr(line)}"


# --- Bug fix regression: Issue #2 — lifecycle hooks not inside computed ---

def test_lifecycle_hooks_not_inside_computed():
    """Lifecycle hooks must be at top-level scope, not nested inside computed."""
    mixin = '''
    export default {
        computed: {
            fullName() {
                return this.firstName + ' ' + this.lastName
            }
        },
        mounted() {
            console.log('mounted')
        }
    }
    '''
    hooks = ['mounted']
    inline_lines, wrapped_lines = convert_lifecycle_hooks(mixin, hooks, [], [], "  ")
    output = "\n".join(wrapped_lines)
    assert "onMounted" in output
    # onMounted should not be inside computed(() =>
    assert "computed" not in output


# --- Bug fix regression: Issue #3 — beforeDestroy hook converted ---

def test_before_destroy_hook_converted():
    """Both mounted and beforeDestroy should be converted."""
    mixin = '''
    export default {
        mounted() {
            window.addEventListener('resize', this.onResize)
        },
        beforeDestroy() {
            window.removeEventListener('resize', this.onResize)
        }
    }
    '''
    hooks = ['mounted', 'beforeDestroy']
    inline_lines, wrapped_lines = convert_lifecycle_hooks(mixin, hooks, [], ['onResize'], "  ")
    output = "\n".join(wrapped_lines)
    assert "onMounted" in output
    assert "onBeforeUnmount" in output


def test_before_destroy_fallback_when_missing_from_hooks_list():
    """If mounted is listed but beforeDestroy is not, fallback scan should find it."""
    mixin = '''
    export default {
        mounted() {
            window.addEventListener('resize', this.onResize)
        },
        beforeDestroy() {
            window.removeEventListener('resize', this.onResize)
        }
    }
    '''
    # Only mounted in the hooks list — beforeDestroy is "missing" from detection
    hooks = ['mounted']
    inline_lines, wrapped_lines = convert_lifecycle_hooks(mixin, hooks, [], ['onResize'], "  ")
    output = "\n".join(wrapped_lines)
    assert "onMounted" in output
    assert "onBeforeUnmount" in output, "Fallback should have found beforeDestroy"


def test_only_before_destroy_without_mounted():
    """beforeDestroy alone (without mounted) should still convert."""
    mixin = '''
    export default {
        beforeDestroy() {
            clearInterval(this.timer)
        }
    }
    '''
    hooks = ['beforeDestroy']
    inline_lines, wrapped_lines = convert_lifecycle_hooks(mixin, hooks, [], ['timer'], "  ")
    output = "\n".join(wrapped_lines)
    assert "onBeforeUnmount" in output


def test_get_required_imports_with_fallback():
    """get_required_imports should find destroy hook imports via fallback scan."""
    mixin = '''
    export default {
        mounted() {
            window.addEventListener('resize', this.onResize)
        },
        beforeDestroy() {
            window.removeEventListener('resize', this.onResize)
        }
    }
    '''
    # Only mounted in hooks list
    imports = get_required_imports(['mounted'], mixin)
    assert "onMounted" in imports
    assert "onBeforeUnmount" in imports


def test_before_unmount_maps_correctly():
    """Vue 3's beforeUnmount should also map to onBeforeUnmount."""
    assert HOOK_MAP.get("beforeUnmount") == "onBeforeUnmount"
