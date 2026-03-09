"""Tests for this.$t/$tc/$te/$d/$n auto-rewriting to useI18n() composable pattern.

Task A2 Phase 2: i18n rewriting.
"""
import pytest
from vue3_migration.transform.this_rewriter import rewrite_this_i18n_refs
from vue3_migration.transform.composable_generator import generate_composable_from_mixin
from vue3_migration.transform.composable_patcher import patch_composable
from vue3_migration.models import MixinMembers


# ---------------------------------------------------------------------------
# Unit tests: rewrite_this_i18n_refs
# ---------------------------------------------------------------------------

class TestRewriteThisI18n:
    """Test individual i18n pattern rewrites."""

    def test_rewrite_this_t_to_t(self):
        code = "this.$t('key')"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == "t('key')"
        assert fns == {'t'}

    def test_rewrite_this_tc_to_t(self):
        code = "this.$tc('key', count)"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == "t('key', count)"
        assert fns == {'t'}

    def test_rewrite_this_te_to_te(self):
        code = "this.$te('key')"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == "te('key')"
        assert fns == {'te'}

    def test_rewrite_this_d_to_d(self):
        code = "this.$d(date)"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == "d(date)"
        assert fns == {'d'}

    def test_rewrite_this_n_to_n(self):
        code = "this.$n(number)"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == "n(number)"
        assert fns == {'n'}

    def test_i18n_not_rewritten_in_strings(self):
        code = """const msg = "this.$t('key')"
this.$t('real')"""
        result, fns = rewrite_this_i18n_refs(code)
        # String should be preserved, actual code rewritten
        assert "\"this.$t('key')\"" in result
        assert "t('real')" in result
        assert fns == {'t'}

    def test_i18n_not_rewritten_in_comments(self):
        code = """// this.$t('key') is the old way
this.$t('real')"""
        result, fns = rewrite_this_i18n_refs(code)
        assert "// this.$t('key')" in result
        assert "t('real')" in result
        assert fns == {'t'}

    def test_i18n_not_rewritten_in_template_literal_text(self):
        code = "`this.$t('key')`"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == code
        assert fns == set()

    def test_i18n_rewritten_in_template_literal_interpolation(self):
        code = "`${this.$t('key')}`"
        result, fns = rewrite_this_i18n_refs(code)
        assert "t('key')" in result
        assert fns == {'t'}

    def test_empty_code(self):
        result, fns = rewrite_this_i18n_refs("")
        assert result == ""
        assert fns == set()

    def test_no_i18n_patterns(self):
        code = "const x = 1 + 2"
        result, fns = rewrite_this_i18n_refs(code)
        assert result == code
        assert fns == set()

    def test_multiple_different_i18n_functions(self):
        code = """this.$t('hello')
this.$n(42)
this.$d(new Date())"""
        result, fns = rewrite_this_i18n_refs(code)
        assert "t('hello')" in result
        assert "n(42)" in result
        assert "d(new Date())" in result
        assert fns == {'t', 'n', 'd'}

    def test_multiple_same_i18n_function(self):
        code = "this.$t('a') + this.$t('b')"
        result, fns = rewrite_this_i18n_refs(code)
        assert "t('a') + t('b')" == result
        assert fns == {'t'}

    def test_i18n_only_used_functions_collected(self):
        """If only $t and $n used, only t and n should be in the set."""
        code = "this.$t('key') + this.$n(123)"
        result, fns = rewrite_this_i18n_refs(code)
        assert fns == {'t', 'n'}

    def test_does_not_affect_non_i18n_dollar(self):
        """this.$router, this.$emit etc. should NOT be touched."""
        code = "this.$router.push('/'); this.$emit('change'); this.$t('key')"
        result, fns = rewrite_this_i18n_refs(code)
        assert "this.$router" in result
        assert "this.$emit" in result
        assert "t('key')" in result
        assert fns == {'t'}


# ---------------------------------------------------------------------------
# Integration: composable_generator
# ---------------------------------------------------------------------------

class TestGeneratorI18nRewriting:
    """Verify that generate_composable_from_mixin applies i18n rewrites."""

    def test_i18n_import_added(self):
        source = """
export default {
    methods: {
        greet() {
            return this.$t('hello')
        }
    }
}
"""
        members = MixinMembers(methods=["greet"])
        result = generate_composable_from_mixin(source, "greetMixin", members, [])
        assert "import { useI18n } from 'vue-i18n'" in result

    def test_i18n_destructuring_added(self):
        source = """
export default {
    methods: {
        greet() {
            return this.$t('hello')
        }
    }
}
"""
        members = MixinMembers(methods=["greet"])
        result = generate_composable_from_mixin(source, "greetMixin", members, [])
        assert "const { t } = useI18n()" in result

    def test_i18n_only_used_functions_destructured(self):
        source = """
export default {
    methods: {
        format() {
            return this.$t('key') + this.$n(42)
        }
    }
}
"""
        members = MixinMembers(methods=["format"])
        result = generate_composable_from_mixin(source, "formatMixin", members, [])
        assert "const { n, t } = useI18n()" in result

    def test_composable_generation_with_i18n(self):
        """End-to-end: mixin with this.$t produces composable with useI18n."""
        source = """
export default {
    data() {
        return { name: '' }
    },
    computed: {
        greeting() {
            return this.$t('hello', { name: this.name })
        }
    },
    methods: {
        checkExists(key) {
            return this.$te(key)
        }
    }
}
"""
        members = MixinMembers(data=["name"], computed=["greeting"], methods=["checkExists"])
        result = generate_composable_from_mixin(source, "i18nMixin", members, [])
        # Has i18n import
        assert "import { useI18n } from 'vue-i18n'" in result
        # Has destructuring with both t and te
        assert "const { t, te } = useI18n()" in result
        # Rewrites happened in code (not in comments)
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        code_text = "\n".join(code_lines)
        assert "this.$t(" not in code_text
        assert "this.$te(" not in code_text
        assert "t('hello'" in code_text
        assert "te(key)" in code_text

    def test_no_i18n_when_not_used(self):
        """No i18n import/destructuring when no i18n patterns present."""
        source = """
export default {
    methods: {
        doStuff() {
            console.log('hello')
        }
    }
}
"""
        members = MixinMembers(methods=["doStuff"])
        result = generate_composable_from_mixin(source, "plainMixin", members, [])
        assert "useI18n" not in result
        assert "vue-i18n" not in result

    def test_i18n_import_separate_from_vue_import(self):
        """i18n import should be a separate line from the Vue import."""
        source = """
export default {
    data() { return { x: 1 } },
    methods: {
        greet() { return this.$t('hi') }
    }
}
"""
        members = MixinMembers(data=["x"], methods=["greet"])
        result = generate_composable_from_mixin(source, "testMixin", members, [])
        lines = result.splitlines()
        vue_import_lines = [l for l in lines if "from 'vue'" in l]
        i18n_import_lines = [l for l in lines if l.strip().startswith("import") and "from 'vue-i18n'" in l]
        assert len(vue_import_lines) >= 1
        assert len(i18n_import_lines) == 1
        # They should be different lines
        assert vue_import_lines[0] != i18n_import_lines[0]

    def test_i18n_warnings_suppressed_after_rewrite(self):
        """i18n warnings should NOT appear when auto-rewrite adds useI18n()."""
        source = """
export default {
    methods: {
        greet() { return this.$t('hello') },
        count() { return this.$tc('items', 5) },
        check() { return this.$te('key') },
        fmt() { return this.$n(42) },
        date() { return this.$d(new Date()) }
    }
}
"""
        members = MixinMembers(methods=["greet", "count", "check", "fmt", "date"])
        result = generate_composable_from_mixin(source, "i18nMixin", members, [])
        # No i18n warnings should remain — they're all auto-resolved
        for cat in ["this.$t", "this.$tc", "this.$te", "this.$n", "this.$d"]:
            assert cat not in result, f"Warning for {cat} should be suppressed after auto-rewrite"

    def test_tc_rewritten_in_generated_composable(self):
        """this.$tc should be rewritten to t() (merged in vue-i18n v9)."""
        source = """
export default {
    methods: {
        count() {
            return this.$tc('items', 5)
        }
    }
}
"""
        members = MixinMembers(methods=["count"])
        result = generate_composable_from_mixin(source, "countMixin", members, [])
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        code_text = "\n".join(code_lines)
        assert "this.$tc" not in code_text
        assert "t('items', 5)" in code_text


# ---------------------------------------------------------------------------
# Integration: composable_patcher
# ---------------------------------------------------------------------------

class TestPatcherI18nRewriting:
    """Verify that patch_composable applies i18n rewrites."""

    def test_i18n_rewritten_in_patched_composable(self):
        composable = """
import { ref } from 'vue'

export function useGreet() {
  const name = ref('')
  return { name }
}
"""
        mixin = """
export default {
    data() { return { name: '' } },
    methods: {
        greet() {
            return this.$t('hello')
        }
    }
}
"""
        members = MixinMembers(data=["name"], methods=["greet"])
        result = patch_composable(composable, mixin, [], ["greet"], members)
        code_lines = [l for l in result.splitlines() if not l.lstrip().startswith("//")]
        code_text = "\n".join(code_lines)
        assert "this.$t" not in code_text
        assert "t('hello')" in code_text
        assert "import { useI18n } from 'vue-i18n'" in result
        assert "useI18n()" in result

    def test_patcher_no_i18n_when_not_needed(self):
        composable = """
import { ref } from 'vue'

export function useStuff() {
  const x = ref(0)
  return { x }
}
"""
        mixin = """
export default {
    data() { return { x: 0 } },
    methods: {
        inc() { this.x++ }
    }
}
"""
        members = MixinMembers(data=["x"], methods=["inc"])
        result = patch_composable(composable, mixin, [], ["inc"], members)
        assert "useI18n" not in result
        assert "vue-i18n" not in result
