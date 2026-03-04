"""Tests for this.$ detection (warnings) and auto-rewriting ($nextTick, $set, $delete).

Plan 2: this.$ Detection & Rewriting
"""
import pytest
from vue3_migration.models import MigrationWarning, MixinMembers
from vue3_migration.core.warning_collector import collect_mixin_warnings


# ---------------------------------------------------------------------------
# Part 1: Warning detection for ALL this.$ patterns
# ---------------------------------------------------------------------------

class TestThisDollarWarningDetection:
    """Test that collect_mixin_warnings detects all this.$ patterns."""

    # --- Already-implemented patterns (regression) ---

    def test_detects_dollar_router(self):
        source = "this.$router.push('/home')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$router" for w in warnings)

    def test_detects_dollar_route(self):
        source = "const path = this.$route.path"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$route" for w in warnings)

    def test_detects_dollar_store(self):
        source = "this.$store.dispatch('load')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$store" for w in warnings)

    def test_detects_dollar_emit(self):
        source = "this.$emit('change', val)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$emit" for w in warnings)

    def test_detects_dollar_refs(self):
        source = "this.$refs.input.focus()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$refs" for w in warnings)

    def test_detects_dollar_nextTick(self):
        source = "this.$nextTick(() => {})"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$nextTick" for w in warnings)

    def test_detects_dollar_set(self):
        source = "this.$set(this.items, 0, newItem)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$set" for w in warnings)

    def test_detects_dollar_delete(self):
        source = "this.$delete(this.config, 'key')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$delete" for w in warnings)

    def test_detects_dollar_on(self):
        source = "this.$on('event', handler)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$on" for w in warnings)

    def test_detects_dollar_off(self):
        source = "this.$off('event', handler)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$off" for w in warnings)

    def test_detects_dollar_once(self):
        source = "this.$once('hook:beforeDestroy', cleanup)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$once" for w in warnings)

    # --- NEW patterns (Plan 2 additions) ---

    def test_detects_dollar_el(self):
        source = "const rect = this.$el.getBoundingClientRect()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$el" for w in warnings)

    def test_detects_dollar_parent(self):
        source = "this.$parent.someMethod()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$parent" for w in warnings)

    def test_detects_dollar_children(self):
        source = "this.$children.forEach(c => c.update())"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$children" for w in warnings)

    def test_detects_dollar_listeners(self):
        source = "v-on='this.$listeners'"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$listeners" for w in warnings)

    def test_detects_dollar_attrs(self):
        source = "const id = this.$attrs.id"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$attrs" for w in warnings)

    def test_detects_dollar_slots(self):
        source = "const slot = this.$slots.default"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$slots" for w in warnings)

    def test_detects_dollar_forceUpdate(self):
        source = "this.$forceUpdate()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$forceUpdate" for w in warnings)

    def test_detects_dollar_watch(self):
        source = "this.$watch('value', handler)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$watch" for w in warnings)


class TestThisDollarWarningMessages:
    """Verify warning messages and action_required are informative."""

    def test_el_warning_message(self):
        source = "this.$el.getBoundingClientRect()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$el")
        assert "no composable equivalent" in w.message.lower() or "$el" in w.message
        assert w.action_required  # non-empty

    def test_parent_warning_message(self):
        source = "this.$parent.method()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$parent")
        assert "provide/inject" in w.action_required.lower() or "avoid" in w.message.lower()

    def test_children_warning_message(self):
        source = "this.$children[0]"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$children")
        assert "removed" in w.message.lower() or "vue 3" in w.message.lower()

    def test_forceUpdate_warning_message(self):
        source = "this.$forceUpdate()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$forceUpdate")
        assert "rarely needed" in w.message.lower() or "forceUpdate" in w.message

    def test_watch_warning_suggests_vue_import(self):
        source = "this.$watch('x', handler)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$watch")
        assert "watch()" in w.action_required or "watch" in w.action_required.lower()

    def test_attrs_warning_suggests_useAttrs(self):
        source = "this.$attrs.id"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$attrs")
        assert "useAttrs" in w.action_required

    def test_slots_warning_suggests_useSlots(self):
        source = "this.$slots.default"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$slots")
        assert "useSlots" in w.action_required


class TestThisDollarDeduplication:
    """Verify that multiple occurrences of the same pattern produce one warning."""

    def test_multiple_router_refs_produce_one_warning(self):
        source = "this.$router.push('/'); this.$router.replace('/login')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        router_warnings = [w for w in warnings if w.category == "this.$router"]
        assert len(router_warnings) == 1


# ---------------------------------------------------------------------------
# Part 2: Auto-rewriting tests ($nextTick, $set, $delete)
# ---------------------------------------------------------------------------

from vue3_migration.transform.this_rewriter import rewrite_this_dollar_refs


class TestRewriteNextTick:
    """this.$nextTick(cb) -> nextTick(cb) with import."""

    def test_basic_nextTick(self):
        code = "this.$nextTick(() => { console.log('done') })"
        result, imports = rewrite_this_dollar_refs(code)
        assert "nextTick(" in result
        assert "this.$nextTick" not in result
        assert "nextTick" in imports

    def test_nextTick_with_callback_variable(self):
        code = "this.$nextTick(callback)"
        result, imports = rewrite_this_dollar_refs(code)
        assert result == "nextTick(callback)"
        assert "nextTick" in imports

    def test_nextTick_then_chain(self):
        code = "this.$nextTick().then(() => {})"
        result, imports = rewrite_this_dollar_refs(code)
        assert "nextTick().then" in result
        assert "this.$nextTick" not in result

    def test_no_nextTick_no_import(self):
        code = "this.doSomething()"
        result, imports = rewrite_this_dollar_refs(code)
        assert "nextTick" not in imports


class TestRewriteSet:
    """this.$set(obj, key, val) -> obj[key] = val."""

    def test_basic_set(self):
        code = "this.$set(this.items, 0, newItem)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$set" not in result
        assert "this.items[0] = newItem" in result

    def test_set_with_string_key(self):
        code = "this.$set(this.config, 'theme', 'dark')"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$set" not in result
        assert "this.config['theme'] = 'dark'" in result

    def test_set_with_nested_obj(self):
        code = "this.$set(this.data.nested, 'key', value)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$set" not in result
        assert "this.data.nested['key'] = value" in result

    def test_set_adds_no_import(self):
        code = "this.$set(this.items, 0, val)"
        _, imports = rewrite_this_dollar_refs(code)
        assert "nextTick" not in imports  # $set needs no imports


class TestRewriteDelete:
    """this.$delete(obj, key) -> delete obj[key]."""

    def test_basic_delete(self):
        code = "this.$delete(this.config, 'key')"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$delete" not in result
        assert "delete this.config['key']" in result

    def test_delete_with_variable_key(self):
        code = "this.$delete(this.items, idx)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$delete" not in result
        assert "delete this.items[idx]" in result

    def test_delete_adds_no_import(self):
        code = "this.$delete(this.config, 'key')"
        _, imports = rewrite_this_dollar_refs(code)
        assert "nextTick" not in imports


class TestRewriteMultiplePatterns:
    """Multiple dollar patterns in the same code."""

    def test_nextTick_and_set_together(self):
        code = """this.$set(this.items, 0, val)
this.$nextTick(() => { console.log('updated') })"""
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$set" not in result
        assert "this.$nextTick" not in result
        assert "nextTick" in imports

    def test_all_three_patterns(self):
        code = """this.$set(this.obj, 'a', 1)
this.$delete(this.obj, 'b')
this.$nextTick(cb)"""
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$set" not in result
        assert "this.$delete" not in result
        assert "this.$nextTick" not in result
        assert "nextTick" in imports

    def test_non_rewritable_patterns_left_alone(self):
        """this.$router, this.$emit etc. should NOT be rewritten."""
        code = "this.$router.push('/'); this.$emit('change')"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$router" in result
        assert "this.$emit" in result
        assert len(imports) == 0


class TestRewriteEdgeCases:
    """Edge cases for auto-rewriting."""

    def test_empty_code(self):
        result, imports = rewrite_this_dollar_refs("")
        assert result == ""
        assert imports == []

    def test_no_dollar_patterns(self):
        code = "const x = 1 + 2"
        result, imports = rewrite_this_dollar_refs(code)
        assert result == code
        assert imports == []

    def test_dollar_in_string_not_rewritten(self):
        code = """const msg = "this.$nextTick is deprecated"
this.$nextTick(fn)"""
        result, imports = rewrite_this_dollar_refs(code)
        # The string should be preserved, but the actual code should be rewritten
        assert "nextTick(fn)" in result
        assert "nextTick" in imports

    def test_dollar_in_comment_not_rewritten(self):
        code = """// this.$set(obj, key, val) is removed in Vue 3
this.$set(this.items, 0, val)"""
        result, imports = rewrite_this_dollar_refs(code)
        # Comment preserved, code rewritten
        assert "// this.$set" in result
        assert "this.items[0] = val" in result


# ---------------------------------------------------------------------------
# Part 3: Integration — generator applies dollar rewrites
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_generator import generate_composable_from_mixin


class TestGeneratorDollarRewriting:
    """Verify that generate_composable_from_mixin applies this.$ rewrites."""

    def test_nextTick_rewritten_in_generated_composable(self):
        source = """
export default {
    methods: {
        refresh() {
            this.$nextTick(() => { console.log('done') })
        }
    }
}
"""
        members = MixinMembers(methods=["refresh"])
        result = generate_composable_from_mixin(source, "updateMixin", members, [])
        # Check code lines only (skip comments which may contain the original pattern in warnings)
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        assert not any("this.$nextTick" in l for l in code_lines)
        assert "nextTick(" in result
        assert "import" in result and "nextTick" in result

    def test_set_rewritten_in_generated_composable(self):
        source = """
export default {
    data() { return { items: [] } },
    methods: {
        update() {
            this.$set(this.items, 0, 'new')
        }
    }
}
"""
        members = MixinMembers(data=["items"], methods=["update"])
        result = generate_composable_from_mixin(source, "listMixin", members, [])
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        assert not any("this.$set" in l for l in code_lines)

    def test_delete_rewritten_in_generated_composable(self):
        source = """
export default {
    data() { return { config: {} } },
    methods: {
        removeKey() {
            this.$delete(this.config, 'old')
        }
    }
}
"""
        members = MixinMembers(data=["config"], methods=["removeKey"])
        result = generate_composable_from_mixin(source, "configMixin", members, [])
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        assert not any("this.$delete" in l for l in code_lines)
        assert "delete" in result

    def test_router_warning_still_emitted_after_dollar_rewrite(self):
        """Non-rewritable patterns should still produce warnings."""
        source = """
export default {
    methods: {
        go() {
            this.$nextTick(() => {})
            this.$router.push('/')
        }
    }
}
"""
        members = MixinMembers(methods=["go"])
        result = generate_composable_from_mixin(source, "navMixin", members, [])
        # $nextTick rewritten in code, $router warned
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        assert not any("this.$nextTick" in l for l in code_lines)
        assert "// ⚠ MIGRATION:" in result
        assert "$router" in result

    def test_nextTick_import_added_to_vue_imports(self):
        """nextTick should be in the vue import line."""
        source = """
export default {
    methods: {
        refresh() {
            this.$nextTick(fn)
        }
    }
}
"""
        members = MixinMembers(methods=["refresh"])
        result = generate_composable_from_mixin(source, "refreshMixin", members, [])
        # Should have nextTick in the import line
        import_line = [l for l in result.splitlines() if l.startswith("import")][0]
        assert "nextTick" in import_line


# ---------------------------------------------------------------------------
# Part 4: Integration — patcher applies dollar rewrites
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_patcher import patch_composable


class TestPatcherDollarRewriting:
    """Verify that patch_composable applies this.$ rewrites for missing members."""

    def test_nextTick_rewritten_in_patched_composable(self):
        composable = """
import { ref } from 'vue'

export function useUpdate() {
  const items = ref([])
  return { items }
}
"""
        mixin = """
export default {
    data() { return { items: [] } },
    methods: {
        refresh() {
            this.$nextTick(() => { console.log('done') })
        }
    }
}
"""
        members = MixinMembers(data=["items"], methods=["refresh"])
        result = patch_composable(composable, mixin, [], ["refresh"], members)
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        assert not any("this.$nextTick" in l for l in code_lines)
        assert "nextTick(" in result

    def test_set_rewritten_in_patched_composable(self):
        composable = """
import { ref } from 'vue'

export function useList() {
  const items = ref([])
  return { items }
}
"""
        mixin = """
export default {
    data() { return { items: [] } },
    methods: {
        update() {
            this.$set(this.items, 0, 'new')
        }
    }
}
"""
        members = MixinMembers(data=["items"], methods=["update"])
        result = patch_composable(composable, mixin, [], ["update"], members)
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        assert not any("this.$set" in l for l in code_lines)
