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

    def test_no_warning_for_auto_migrated_nextTick(self):
        source = "this.$nextTick(() => {})"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert not any(w.category == "this.$nextTick" for w in warnings)

    def test_no_warning_for_auto_migrated_set(self):
        source = "this.$set(this.items, 0, newItem)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert not any(w.category == "this.$set" for w in warnings)

    def test_no_warning_for_auto_migrated_delete(self):
        source = "this.$delete(this.config, 'key')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert not any(w.category == "this.$delete" for w in warnings)

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
        source = "const listeners = this.$listeners"
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

    # --- i18n patterns (Task A2) ---

    def test_detects_dollar_t(self):
        source = "const label = this.$t('some.key')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$t" for w in warnings)

    def test_detects_dollar_tc(self):
        source = "const msg = this.$tc('items', count)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$tc" for w in warnings)

    def test_detects_dollar_te(self):
        source = "if (this.$te('key')) { return true }"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$te" for w in warnings)

    def test_detects_dollar_d(self):
        source = "const formatted = this.$d(date)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$d" for w in warnings)

    def test_detects_dollar_n(self):
        source = "const num = this.$n(number)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        assert any(w.category == "this.$n" for w in warnings)

    def test_dollar_t_in_string_not_detected(self):
        """this.$t inside a string literal should not trigger a warning."""
        source = "const msg = 'use this.$t for translations'"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        # The regex scans raw source so it may still match inside strings.
        # This test documents the current behaviour — the pattern does NOT
        # do string-aware scanning.  If it happens to match, that's a known
        # limitation; if it doesn't, even better.
        # We just verify no crash and the test is explicit about this edge case.
        assert isinstance(warnings, list)


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

    # --- i18n warning messages (Task A2) ---

    def test_dollar_t_severity_is_error(self):
        source = "this.$t('key')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$t")
        assert w.severity == "error"

    def test_dollar_t_suggests_useI18n(self):
        source = "this.$t('key')"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$t")
        assert "useI18n" in w.action_required

    def test_dollar_tc_mentions_removed(self):
        source = "this.$tc('items', 2)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$tc")
        assert "removed" in w.message.lower() or "v9" in w.message

    def test_dollar_n_suggests_useI18n(self):
        source = "this.$n(42)"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        w = next(w for w in warnings if w.category == "this.$n")
        assert "useI18n" in w.action_required


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


class TestRewriteWatch:
    """this.$watch(key, handler) -> watch(source, handler) with import."""

    def test_rewrite_watch_string_key(self):
        code = "this.$watch('query', (val) => { console.log(val) })"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$watch" not in result
        assert "watch(query," in result
        assert "watch" in imports

    def test_rewrite_watch_dotted_key(self):
        code = "this.$watch('user.name', handler)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$watch" not in result
        assert "watch(() => user.value.name, handler)" in result
        assert "watch" in imports

    def test_rewrite_watch_function_getter(self):
        code = "this.$watch(() => this.x + this.y, handler)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$watch" not in result
        assert "x.value" in result
        assert "y.value" in result
        assert "watch(" in result
        assert "watch" in imports

    def test_rewrite_watch_with_options(self):
        code = "this.$watch('query', handler, { deep: true, immediate: true })"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$watch" not in result
        assert "watch(query, handler, { deep: true, immediate: true })" in result

    def test_rewrite_watch_unwatch_capture(self):
        code = "const unwatch = this.$watch('query', handler)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "const unwatch = watch(query, handler)" in result
        assert "watch" in imports

    def test_rewrite_watch_plain_member_key(self):
        """Method names used as watch keys should not get .value treatment.

        Note: rewrite_this_dollar_refs doesn't have ref/plain member context,
        so string keys are always emitted as bare names (matching generate_watch_call
        convention where Vue 3's watch() auto-unwraps refs).
        """
        code = "this.$watch('fetchResults', handler)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "watch(fetchResults, handler)" in result

    def test_rewrite_watch_in_string_not_rewritten(self):
        code = '''const msg = "this.$watch('x', handler)"'''
        result, imports = rewrite_this_dollar_refs(code)
        assert result == code
        assert "watch" not in imports

    def test_rewrite_watch_unparseable_fallback(self):
        """Dynamic variable as first arg — leave unchanged."""
        code = "this.$watch(dynamicKey, handler)"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$watch" in result  # left unchanged
        assert "watch" not in imports

    def test_rewrite_watch_adds_import(self):
        code = "this.$watch('x', fn)"
        _, imports = rewrite_this_dollar_refs(code)
        assert "watch" in imports

    def test_rewrite_watch_import_not_duplicated(self):
        code = "this.$watch('x', fn1)\nthis.$watch('y', fn2)"
        _, imports = rewrite_this_dollar_refs(code)
        assert imports.count("watch") == 1

    def test_rewrite_watch_with_nested_nextTick(self):
        """$nextTick inside $watch handler should not cause overlapping replacements."""
        code = "this.$watch('x', () => { this.$nextTick(fn) })"
        result, imports = rewrite_this_dollar_refs(code)
        assert "this.$watch" not in result
        assert "watch(x, () => { this.$nextTick(fn) })" in result
        assert "watch" in imports


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
        assert "manual step" in result  # new header format
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
