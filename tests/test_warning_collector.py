"""Tests for the warning infrastructure: models, collection, and confidence scoring."""
from pathlib import Path

import pytest
from vue3_migration.models import (
    ConfidenceLevel,
    MigrationWarning,
    MixinEntry,
    MixinMembers,
)


# ---------------------------------------------------------------------------
# Step 1: Data model tests
# ---------------------------------------------------------------------------

class TestMigrationWarning:
    def test_create_warning(self):
        w = MigrationWarning(
            mixin_stem="authMixin",
            category="this.$router",
            message="this.$router needs useRouter()",
            action_required="Replace with useRouter()",
            line_hint="this.$router.push('/login')",
            severity="warning",
        )
        assert w.mixin_stem == "authMixin"
        assert w.category == "this.$router"
        assert w.severity == "warning"
        assert w.line_hint == "this.$router.push('/login')"

    def test_warning_with_no_line_hint(self):
        w = MigrationWarning(
            mixin_stem="authMixin",
            category="watch",
            message="watch handler not auto-converted",
            action_required="Convert manually",
            line_hint=None,
            severity="info",
        )
        assert w.line_hint is None


class TestConfidenceLevel:
    def test_enum_values(self):
        assert ConfidenceLevel.HIGH == "HIGH"
        assert ConfidenceLevel.MEDIUM == "MEDIUM"
        assert ConfidenceLevel.LOW == "LOW"

    def test_is_string_enum(self):
        assert isinstance(ConfidenceLevel.HIGH, str)


class TestMixinEntryWarnings:
    def test_mixin_entry_has_empty_warnings_by_default(self):
        entry = MixinEntry(
            local_name="authMixin",
            mixin_path="fake/path.js",
            mixin_stem="authMixin",
            members=MixinMembers(),
        )
        assert entry.warnings == []

    def test_mixin_entry_warnings_are_independent(self):
        """Each MixinEntry should have its own warnings list (no shared default)."""
        e1 = MixinEntry(
            local_name="a", mixin_path="a.js", mixin_stem="a", members=MixinMembers(),
        )
        e2 = MixinEntry(
            local_name="b", mixin_path="b.js", mixin_stem="b", members=MixinMembers(),
        )
        e1.warnings.append(
            MigrationWarning("a", "test", "msg", "act", None, "warning")
        )
        assert len(e2.warnings) == 0


# ---------------------------------------------------------------------------
# Step 2: Warning collector tests
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import (
    collect_mixin_warnings,
    compute_confidence,
)


class TestCollectMixinWarnings:
    def test_detects_this_dollar_router(self):
        source = """
        export default {
            methods: {
                go() {
                    this.$router.push('/home')
                }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["go"]), [])
        assert any(w.category == "this.$router" for w in warnings)

    def test_detects_this_dollar_emit(self):
        source = """
        export default {
            methods: {
                submit() {
                    this.$emit('done')
                }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["submit"]), [])
        assert any(w.category == "this.$emit" for w in warnings)

    def test_detects_this_dollar_store(self):
        source = """
        export default {
            computed: {
                user() {
                    return this.$store.state.user
                }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(computed=["user"]), [])
        assert any(w.category == "this.$store" for w in warnings)

    def test_detects_this_dollar_refs(self):
        source = """
        export default {
            methods: {
                focus() {
                    this.$refs.input.focus()
                }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["focus"]), [])
        assert any(w.category == "this.$refs" for w in warnings)

    def test_no_warnings_for_clean_mixin(self):
        source = """
        export default {
            data() {
                return { count: 0 }
            },
            methods: {
                increment() {
                    this.count++
                }
            }
        }
        """
        warnings = collect_mixin_warnings(
            source, MixinMembers(data=["count"], methods=["increment"]), []
        )
        assert len(warnings) == 0

    def test_detects_multiple_dollar_patterns(self):
        source = """
        export default {
            methods: {
                doStuff() {
                    this.$router.push('/')
                    this.$emit('change')
                    this.$store.dispatch('load')
                }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["doStuff"]), [])
        categories = {w.category for w in warnings}
        assert "this.$router" in categories
        assert "this.$emit" in categories
        assert "this.$store" in categories

    def test_warning_fields_are_populated(self):
        source = """
        export default {
            methods: {
                go() { this.$router.push('/') }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["go"]), [])
        w = [w for w in warnings if w.category == "this.$router"][0]
        assert w.mixin_stem == ""  # stem provided by caller, not set here
        assert w.action_required  # non-empty
        assert w.severity in ("error", "warning", "info")
        assert w.message  # non-empty

    def test_no_warning_for_auto_migrated_nextTick(self):
        source = """
        export default {
            methods: {
                update() { this.$nextTick(() => {}) }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["update"]), [])
        assert not any(w.category == "this.$nextTick" for w in warnings)


class TestThisDollarSeverityClassification:
    """Verify that this.$ patterns have correct severity levels."""

    @pytest.mark.parametrize("pattern,expected_severity", [
        ("this.$emit('done')", "error"),
        ("this.$refs.input.focus()", "error"),
        ("this.$on('event', handler)", "error"),
        ("this.$off('event', handler)", "error"),
        ("this.$once('event', handler)", "error"),
        ("this.$children[0]", "error"),
        ("this.$listeners", "error"),
        ("this.$el.querySelector('div')", "error"),
        ("this.$parent.doSomething()", "error"),
    ])
    def test_error_severity_patterns(self, pattern, expected_severity):
        source = f"""
        export default {{
            methods: {{
                doIt() {{ {pattern} }}
            }}
        }}
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["doIt"]), [])
        this_dollar_warnings = [w for w in warnings if w.category.startswith("this.$")]
        assert len(this_dollar_warnings) >= 1, f"No this.$ warning for {pattern}"
        assert this_dollar_warnings[0].severity == expected_severity, (
            f"Expected {expected_severity} for {pattern}, got {this_dollar_warnings[0].severity}"
        )

    @pytest.mark.parametrize("pattern,expected_severity", [
        ("this.$router.push('/')", "error"),
        ("this.$route.params.id", "error"),
        ("this.$store.state.user", "error"),
        ("this.$attrs.class", "warning"),
        ("this.$slots.default", "warning"),
        ("this.$watch('x', handler)", "warning"),
    ])
    def test_warning_severity_patterns(self, pattern, expected_severity):
        source = f"""
        export default {{
            methods: {{
                doIt() {{ {pattern} }}
            }}
        }}
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["doIt"]), [])
        this_dollar_warnings = [w for w in warnings if w.category.startswith("this.$")]
        assert len(this_dollar_warnings) >= 1, f"No this.$ warning for {pattern}"
        assert this_dollar_warnings[0].severity == expected_severity, (
            f"Expected {expected_severity} for {pattern}, got {this_dollar_warnings[0].severity}"
        )

    def test_force_update_is_info(self):
        source = """
        export default {
            methods: {
                refresh() { this.$forceUpdate() }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["refresh"]), [])
        fu_warnings = [w for w in warnings if w.category == "this.$forceUpdate"]
        assert len(fu_warnings) == 1
        assert fu_warnings[0].severity == "info"


class TestComputeConfidence:
    def test_high_confidence_clean_composable(self):
        source = """
import { ref } from 'vue'

export function useAuth() {
  const token = ref(null)
  function login() { token.value = 'abc' }
  return { token, login }
}
"""
        assert compute_confidence(source, []) == ConfidenceLevel.HIGH

    def test_low_confidence_remaining_this(self):
        source = """
export function useAuth() {
  function go() { this.$router.push('/') }
  return { go }
}
"""
        assert compute_confidence(source, []) == ConfidenceLevel.LOW

    def test_medium_confidence_has_todos(self):
        source = """
export function useAuth() {
  const x = computed(() => null) // TODO: implement
  return { x }
}
"""
        assert compute_confidence(source, []) == ConfidenceLevel.MEDIUM

    def test_medium_confidence_has_migration_comments(self):
        # Old box format still triggers MEDIUM (backward compat)
        source_old = """
export function useAuth() {
  // ┌─ MIGRATION WARNINGS ─────────────────────────────
  // │ ⚠️ this.$router needs useRouter()
  // │    → Use useRouter()
  // └─────────────────────────────────────────────────
  function go() { useRouter().push('/') }
  return { go }
}
"""
        assert compute_confidence(source_old, []) == ConfidenceLevel.MEDIUM

        # New header format also triggers MEDIUM
        source_new = """
// ⚠ 1 manual step needed — see migration report for details
export function useAuth() {
  function go() { useRouter().push('/') }
  return { go }
}
"""
        assert compute_confidence(source_new, []) == ConfidenceLevel.MEDIUM

    def test_low_confidence_unbalanced_braces(self):
        source = """
export function useAuth() {
  function go() {
    if (true) {
      return 1
  }
  return { go }
}
"""
        assert compute_confidence(source, []) == ConfidenceLevel.LOW

    def test_error_severity_warning_produces_low_confidence(self):
        """A warning with severity='error' should produce LOW confidence even without this. in source."""
        source = """
export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        warnings = [MigrationWarning("auth", "this.$emit", "msg", "act", None, "error")]
        assert compute_confidence(source, warnings) == ConfidenceLevel.LOW

    def test_warning_severity_still_medium(self):
        """A warning with severity='warning' should produce MEDIUM (not LOW)."""
        source = """
export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        warnings = [MigrationWarning("auth", "this.$router", "msg", "act", None, "warning")]
        assert compute_confidence(source, warnings) == ConfidenceLevel.MEDIUM

    def test_info_severity_still_medium(self):
        """A warning with severity='info' should produce MEDIUM (has warnings, none are errors)."""
        source = """
export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        warnings = [MigrationWarning("auth", "todo-marker", "msg", "act", None, "info")]
        assert compute_confidence(source, warnings) == ConfidenceLevel.MEDIUM

    def test_remaining_this_overrides_warnings_to_low(self):
        source = """
export function useAuth() {
  function go() { this.something }
  return { go }
}
"""
        warnings = [MigrationWarning("auth", "test", "msg", "act", None, "warning")]
        assert compute_confidence(source, warnings) == ConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# Step 3: Inline comment injection tests
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import inject_inline_warnings


class TestInjectInlineWarnings:
    def test_adds_suffix_icon_and_hint_on_matching_line(self):
        source = "  function go() { this.$router.push('/') }\n"
        warnings = [
            MigrationWarning(
                "auth", "this.$router",
                "this.$router needs useRouter()",
                "Use useRouter()",
                "this.$router.push('/')",
                "warning",
            ),
        ]
        result = inject_inline_warnings(source, warnings)
        code_line = [l for l in result.splitlines() if "this.$router.push" in l][0]
        # Suffix should have icon + short hint
        assert "use useRouter()" in code_line
        # No box art
        assert "\u250c" not in result
        assert "\u2502" not in result
        assert "\u2514" not in result

    def test_no_box_for_unplaced_warnings(self):
        """Warnings with no line_hint should NOT produce boxes — they only show in report."""
        source = "  function go() { doSomething() }\n"
        warnings = [
            MigrationWarning("auth", "test", "msg", "act", None, "warning"),
        ]
        result = inject_inline_warnings(source, warnings)
        # No box art should be present
        assert "MIGRATION WARNINGS" not in result
        assert "\u250c" not in result

    def test_no_injection_when_no_warnings(self):
        source = "  const x = ref(0)\n"
        result = inject_inline_warnings(source, [])
        assert result == source

    def test_adds_header_with_action_count(self):
        source = "export function useAuth() {\n  return {}\n}\n"
        warnings = [
            MigrationWarning("x", "this.$emit", "msg", "act", None, "error"),
            MigrationWarning("x", "this.$router", "msg", "act", None, "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=2
        )
        assert "// \u26a0\ufe0f 2 manual steps needed" in result
        assert "see migration report" in result

    def test_no_header_when_confidence_not_provided(self):
        source = "export function useAuth() {\n  return {}\n}\n"
        result = inject_inline_warnings(source, [])
        assert "manual step" not in result

    def test_unplaced_warnings_dont_produce_inline_comments(self):
        """Warnings with line_hint=None are silently skipped (report-only)."""
        source = "import { ref } from 'vue'\n\nexport function useX() {\n  return {}\n}\n"
        warnings = [
            MigrationWarning("x", "structural:nested-mixins",
                             "Mixin uses nested mixins", "Check transitive", None, "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=1,
        )
        lines = result.splitlines()
        # Header should be present
        assert "manual step" in lines[0]
        # No box or inline comment for unplaced warning
        assert "Mixin uses nested mixins" not in result

    def test_placed_warning_gets_suffix_unplaced_is_silent(self):
        """Placed warning gets suffix; unplaced is silent (report-only)."""
        source = (
            "import { ref } from 'vue'\n"
            "\n"
            "export function useX() {\n"
            "  function go() { this.$router.push('/') }\n"
            "  return { go }\n"
            "}\n"
        )
        warnings = [
            MigrationWarning("x", "this.$router",
                             "this.$router not available", "Use useRouter()",
                             "this.$router.push('/')",
                             "warning"),
            MigrationWarning("x", "structural:nested-mixins",
                             "Nested mixins", "Check", None, "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=2,
        )
        lines = result.splitlines()
        # Header
        assert "manual steps needed" in lines[0]
        # Suffix on matched line
        code_line = [l for l in lines if "this.$router.push" in l][0]
        assert "use useRouter()" in code_line
        # Unplaced warning NOT in output (report-only)
        assert "Nested mixins" not in result

    def test_error_severity_uses_error_icon_with_hint(self):
        source = "  function submit() { this.$emit('done') }\n"
        warnings = [
            MigrationWarning("x", "this.$emit", "not available", "Use defineEmits",
                             "this.$emit('done')", "error"),
        ]
        result = inject_inline_warnings(source, warnings)
        code_line = [l for l in result.splitlines() if "this.$emit" in l][0]
        assert "use defineEmits or emit param" in code_line

    def test_warning_severity_uses_warning_icon_with_hint(self):
        source = "  function go() { this.$router.push('/') }\n"
        warnings = [
            MigrationWarning("x", "this.$router", "not available", "Use useRouter()",
                             "this.$router.push('/')", "warning"),
        ]
        result = inject_inline_warnings(source, warnings)
        code_line = [l for l in result.splitlines() if "this.$router" in l][0]
        assert "use useRouter()" in code_line

    def test_info_severity_uses_info_icon_with_hint(self):
        source = "  function refresh() { this.$forceUpdate() }\n"
        warnings = [
            MigrationWarning("x", "this.$forceUpdate", "rarely needed", "Review logic",
                             "this.$forceUpdate()", "info"),
        ]
        result = inject_inline_warnings(source, warnings)
        code_line = [l for l in result.splitlines() if "this.$forceUpdate" in l][0]
        assert "// \u2139\ufe0f rarely needed in Vue 3" in code_line

    def test_external_dep_this_items_gets_icon_and_hint_on_all_lines(self):
        """Non-underscore external dep (this.items) gets ❌ + hint on every occurrence."""
        source = (
            "export function useX() {\n"
            "  function go() { return this.items }\n"
            "  function reset() { this.items = [] }\n"
            "  return { go, reset }\n"
            "}\n"
        )
        warnings = [
            MigrationWarning("x", "external-dependency",
                             "'items' — external dep, not available in composable scope",
                             "Accept 'items' as a composable parameter and rewrite this.items",
                             "return this.items",
                             "error"),
        ]
        result = inject_inline_warnings(source, warnings)
        lines = result.splitlines()
        items_lines = [l for l in lines if "this.items" in l and not l.lstrip().startswith("//")]
        assert len(items_lines) == 2, f"Expected 2 code lines with this.items, got {len(items_lines)}"
        for l in items_lines:
            assert "// \u274c external dep" in l and "as param" in l, f"Missing icon+hint on line: {l}"

    def test_rewritten_internal_prop_gets_icon_and_hint(self):
        """After internal_props rewriting (this._searchTimeout -> _searchTimeout),
        the bare name should still get a ❌ icon + hint via fallback matching."""
        source = (
            "export function useX() {\n"
            "  let _searchTimeout = null\n"
            "  function search() { clearTimeout(_searchTimeout) }\n"
            "  function debounce() { _searchTimeout = setTimeout(go, 300) }\n"
            "  return { search, debounce }\n"
            "}\n"
        )
        warnings = [
            MigrationWarning("x", "external-dependency",
                             "'_searchTimeout' — external dep, not available in composable scope",
                             "Accept '_searchTimeout' as a composable parameter and rewrite this._searchTimeout",
                             "clearTimeout(this._searchTimeout)",
                             "error"),
        ]
        result = inject_inline_warnings(source, warnings)
        lines = result.splitlines()
        bare_lines = [l for l in lines if "_searchTimeout" in l
                      and not l.lstrip().startswith("//")
                      and "let _searchTimeout" not in l]
        assert len(bare_lines) >= 2, f"Expected >=2 code lines with _searchTimeout, got {len(bare_lines)}"
        for l in bare_lines:
            assert "// \u274c external dep" in l and "as param" in l, f"Missing icon+hint on line: {l}"

    def test_no_duplicate_icons_on_same_line(self):
        """Each line should get at most one suffix icon."""
        source = (
            "export function useX() {\n"
            "  function go() { this.$router.push('/') }\n"
            "  function back() { this.$router.back() }\n"
            "  return { go, back }\n"
            "}\n"
        )
        warnings = [
            MigrationWarning("x", "this.$router",
                             "this.$router not available", "Use useRouter()",
                             "this.$router.push('/')",
                             "error"),
        ]
        result = inject_inline_warnings(source, warnings)
        lines = result.splitlines()
        router_lines = [l for l in lines if "this.$router" in l and not l.lstrip().startswith("//")]
        assert len(router_lines) == 2
        for l in router_lines:
            assert l.count("// \u274c") == 1, f"Expected exactly 1 icon on: {l}"


class TestThisAliasInlineWarnings:
    """Verify that self=this inline comments appear on ALL alias usage lines."""

    def test_alias_usage_lines_annotated(self):
        """self.x usage lines should get inline warning comments."""
        source = (
            "export function useFoo() {\n"
            "  const self = this\n"
            "  function doWork() {\n"
            "    self.count++\n"
            "    self.getData()\n"
            "    console.log('done')\n"
            "  }\n"
            "  return { doWork }\n"
            "}\n"
        )
        warnings = [MigrationWarning(
            mixin_stem="fooMixin",
            category="this-alias",
            message="'this' is aliased as 'self' — references via self.x won't be auto-rewritten",
            action_required="Manually replace self.x with composable equivalents",
            line_hint="const self = this",
            severity="warning",
        )]
        result = inject_inline_warnings(source, warnings)
        lines = result.splitlines()
        # Declaration line should be annotated
        decl_line = next(l for l in lines if "= this" in l and not l.lstrip().startswith("//"))
        assert "// \u26a0\ufe0f" in decl_line
        # Both self.x usage lines should be annotated
        usage_lines = [l for l in lines if "self." in l and not l.lstrip().startswith("//")]
        assert len(usage_lines) >= 2, f"Expected at least 2 annotated self.x lines, got {len(usage_lines)}"
        for l in usage_lines:
            assert "// \u26a0\ufe0f" in l, f"Missing annotation on: {l}"
        # Non-alias line should NOT be annotated
        console_line = next(l for l in lines if "console.log" in l)
        assert "// \u26a0\ufe0f" not in console_line

    def test_alias_vm_usage_annotated(self):
        """var vm = this should also annotate vm.x usage lines."""
        source = (
            "export function useBar() {\n"
            "  var vm = this\n"
            "  vm.refresh()\n"
            "}\n"
        )
        warnings = [MigrationWarning(
            mixin_stem="barMixin",
            category="this-alias",
            message="'this' is aliased as 'vm' — references via vm.x won't be auto-rewritten",
            action_required="Manually replace vm.x with composable equivalents",
            line_hint="var vm = this",
            severity="warning",
        )]
        result = inject_inline_warnings(source, warnings)
        lines = result.splitlines()
        vm_usage = next(l for l in lines if "vm.refresh" in l)
        assert "// \u26a0\ufe0f" in vm_usage


# ---------------------------------------------------------------------------
# Step 3 (cont): Integration — generator produces warnings + inline comments
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_generator import generate_composable_from_mixin


class TestGeneratorWarningIntegration:
    def test_generated_composable_has_header(self):
        source = """
export default {
    data() {
        return { token: null }
    },
    methods: {
        go() {
            this.$router.push('/login')
        }
    }
}
"""
        members = MixinMembers(data=["token"], methods=["go"])
        result = generate_composable_from_mixin(source, "authMixin", members, [])
        assert "// \u26a0" in result
        assert "manual step" in result

    def test_generated_composable_has_inline_suffix(self):
        source = """
export default {
    methods: {
        go() {
            this.$router.push('/login')
        }
    }
}
"""
        members = MixinMembers(methods=["go"])
        result = generate_composable_from_mixin(source, "authMixin", members, [])
        # Should have inline suffix with hint, no box
        assert "MIGRATION WARNINGS" not in result
        # Should have suffix icon + hint on the this.$router line
        lines = result.splitlines()
        router_lines = [l for l in lines if "this.$router" in l and not l.lstrip().startswith("//")]
        assert len(router_lines) >= 1
        assert "use useRouter()" in router_lines[0]

    def test_clean_mixin_generates_high_confidence(self):
        source = """
export default {
    data() {
        return { count: 0 }
    },
    methods: {
        increment() {
            this.count++
        }
    }
}
"""
        members = MixinMembers(data=["count"], methods=["increment"])
        result = generate_composable_from_mixin(source, "counterMixin", members, [])
        # Clean mixin — no this.$ patterns — should have header with 0 issues
        assert "// \u2705 0 issues" in result

    def test_external_dep_this_items_gets_header_and_inline_hints(self):
        """End-to-end: mixin with this.items (external dep) gets both
        header and inline ❌ + hint on all occurrences."""
        source = """
export default {
    data() {
        return { query: '' }
    },
    methods: {
        search() {
            return this.items.filter(i => i.name.includes(this.query))
        },
        count() {
            return this.items.length
        }
    }
}
"""
        members = MixinMembers(data=["query"], methods=["search", "count"])
        result = generate_composable_from_mixin(source, "filterMixin", members, [])
        # All code lines with this.items should have ❌ + hint
        lines = result.splitlines()
        items_code_lines = [
            l for l in lines
            if "this.items" in l and not l.lstrip().startswith("//")
        ]
        assert len(items_code_lines) >= 2, (
            f"Expected >=2 code lines with this.items, got {len(items_code_lines)}"
        )
        for l in items_code_lines:
            assert "as param" in l, f"Missing icon+hint on line: {l}"

    def test_underscore_external_dep_rewritten_still_gets_hints(self):
        """End-to-end: mixin with this._searchTimeout (underscore external dep)
        that gets rewritten by internal_props should still get ❌ + hint."""
        source = """
export default {
    methods: {
        search() {
            clearTimeout(this._searchTimeout)
            this._searchTimeout = setTimeout(() => this.doSearch(), 300)
        },
        doSearch() {
            console.log('searching')
        }
    }
}
"""
        members = MixinMembers(methods=["search", "doSearch"])
        result = generate_composable_from_mixin(source, "searchMixin", members, [])
        # internal_props rewrites this._searchTimeout -> _searchTimeout
        assert "let _searchTimeout = null" in result
        # The bare _searchTimeout usages should have ❌ + hint
        lines = result.splitlines()
        bare_lines = [
            l for l in lines
            if "_searchTimeout" in l
            and not l.lstrip().startswith("//")
            and "let _searchTimeout" not in l
        ]
        assert len(bare_lines) >= 1, (
            f"Expected >=1 code lines with _searchTimeout usage, got {len(bare_lines)}"
        )
        for l in bare_lines:
            assert "as param" in l, f"Missing icon+hint on rewritten line: {l}"


# ---------------------------------------------------------------------------
# Step 3 (cont): Integration — patcher produces warnings + inline comments
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_patcher import patch_composable


class TestPatcherWarningIntegration:
    def test_patched_composable_has_header(self):
        composable = """
import { ref } from 'vue'

export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        mixin = """
export default {
    data() { return { token: null } },
    methods: {
        go() { this.$router.push('/login') }
    }
}
"""
        members = MixinMembers(data=["token"], methods=["go"])
        result = patch_composable(composable, mixin, [], ["go"], members)
        assert "// \u26a0" in result
        assert "manual step" in result or "issue" in result

    def test_patched_composable_with_router_has_suffix_hint(self):
        """Mixin warnings (this.$router) produce inline suffix hints."""
        composable = """
import { ref } from 'vue'

export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        mixin = """
export default {
    data() { return { token: null } },
    methods: {
        go() { this.$router.push('/login') }
    }
}
"""
        members = MixinMembers(data=["token"], methods=["go"])
        result = patch_composable(composable, mixin, [], ["go"], members)
        # Has this.$router in output — line should have ❌ + hint
        lines = result.splitlines()
        router_lines = [l for l in lines if "this.$router" in l and not l.lstrip().startswith("//")]
        if router_lines:
            assert "use useRouter()" in router_lines[0]

    def test_clean_mixin_patch_has_header(self):
        """Mixin without this.$ patterns gets header but no inline icons."""
        composable = """
import { ref } from 'vue'

export function useCounter() {
  const count = ref(0)
  return { count }
}
"""
        mixin = """
export default {
    data() {
        return { count: 0 }
    },
    methods: {
        increment() {
            this.count++
        }
    }
}
"""
        members = MixinMembers(data=["count"], methods=["increment"])
        result = patch_composable(composable, mixin, [], ["increment"], members)
        assert "// \u2705 0 issues" in result or "// \u26a0" in result


# ---------------------------------------------------------------------------
# Step 4: Post-generation self-check tests
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import post_generation_check


class TestPostGenerationCheck:
    def test_detects_remaining_this_dot(self):
        source = """
export function useAuth() {
  function go() { this.$router.push('/') }
  return { go }
}
"""
        warnings = post_generation_check(source)
        assert any(w.category == "remaining-this" for w in warnings)

    def test_detects_remaining_this_dot_property(self):
        source = """
export function useAuth() {
  function go() { this.someProperty }
  return { go }
}
"""
        warnings = post_generation_check(source)
        assert any(w.category == "remaining-this" for w in warnings)

    def test_ignores_this_in_comments(self):
        source = """
export function useAuth() {
  // this.something was already migrated
  const x = ref(0)
  return { x }
}
"""
        warnings = post_generation_check(source)
        assert not any(w.category == "remaining-this" for w in warnings)

    def test_detects_unbalanced_braces(self):
        source = """
export function useAuth() {
  function go() {
    if (true) {
      return 1
  }
  return { go }
}
"""
        warnings = post_generation_check(source)
        assert any(w.category == "unbalanced-braces" for w in warnings)

    def test_no_warning_for_balanced_braces(self):
        source = """
export function useAuth() {
  function go() {
    if (true) {
      return 1
    }
  }
  return { go }
}
"""
        warnings = post_generation_check(source)
        assert not any(w.category == "unbalanced-braces" for w in warnings)

    def test_counts_todo_markers(self):
        source = """
export function useAuth() {
  const x = computed(() => null) // TODO: implement
  const y = computed(() => null) // TODO: implement
  return { x, y }
}
"""
        warnings = post_generation_check(source)
        todo_warnings = [w for w in warnings if w.category == "todo-marker"]
        assert len(todo_warnings) == 1  # one summary warning, not per-TODO
        assert "2" in todo_warnings[0].message  # mentions the count

    def test_no_warnings_for_clean_composable(self):
        source = """
import { ref } from 'vue'

export function useCounter() {
  const count = ref(0)
  function increment() { count.value++ }
  return { count, increment }
}
"""
        warnings = post_generation_check(source)
        assert len(warnings) == 0

    def test_warning_severity_is_set(self):
        source = """
export function useAuth() {
  function go() { this.x }
  return { go }
}
"""
        warnings = post_generation_check(source)
        for w in warnings:
            assert w.severity in ("error", "warning", "info")


# ---------------------------------------------------------------------------
# Step 5: Terminal warning summary tests
# ---------------------------------------------------------------------------

from vue3_migration.reporting.terminal import format_warning_summary


class TestFormatWarningSummary:
    def _make_entry(self, stem, warnings=None):
        entry = MixinEntry(
            local_name=stem,
            mixin_path=f"fake/{stem}.js",
            mixin_stem=stem,
            members=MixinMembers(),
        )
        if warnings:
            entry.warnings = warnings
        return entry

    def test_high_confidence_entry(self):
        entry = self._make_entry("selectionMixin")
        result = format_warning_summary(
            [entry], {"selectionMixin": ConfidenceLevel.HIGH}
        )
        assert "useSelection" in result or "selectionMixin" in result
        assert "HIGH" in result

    def test_medium_confidence_with_warnings(self):
        w = MigrationWarning(
            "authMixin", "this.$router",
            "this.$router needs useRouter()",
            "Use useRouter()",
            None, "warning",
        )
        entry = self._make_entry("authMixin", warnings=[w])
        result = format_warning_summary(
            [entry], {"authMixin": ConfidenceLevel.MEDIUM}
        )
        assert "MEDIUM" in result
        assert "this.$router" in result

    def test_empty_entries(self):
        result = format_warning_summary([], {})
        assert result == ""

    def test_multiple_entries(self):
        e1 = self._make_entry("authMixin")
        e2 = self._make_entry("selectionMixin")
        result = format_warning_summary(
            [e1, e2],
            {"authMixin": ConfidenceLevel.HIGH, "selectionMixin": ConfidenceLevel.MEDIUM},
        )
        assert "authMixin" in result
        assert "selectionMixin" in result

    def test_severity_icon_per_warning(self):
        """Each warning should show its own severity icon, not a generic one."""
        w_error = MigrationWarning(
            "authMixin", "this.$emit", "not available", "Fix it", None, "error",
        )
        w_warning = MigrationWarning(
            "authMixin", "this.$router", "not available", "Use useRouter()", None, "warning",
        )
        entry = self._make_entry("authMixin", warnings=[w_error, w_warning])
        result = format_warning_summary(
            [entry], {"authMixin": ConfidenceLevel.LOW}
        )
        assert "this.$emit" in result
        assert "this.$router" in result


# ---------------------------------------------------------------------------
# Step 5 (cont): Workflow populates warnings on MixinEntry
# ---------------------------------------------------------------------------

from vue3_migration.workflows.auto_migrate_workflow import _analyze_mixin_silent


class TestWorkflowWarningPopulation:
    def test_analyze_mixin_populates_warnings(self, tmp_path):
        """_analyze_mixin_silent should populate entry.warnings for this.$ patterns."""
        mixin_file = tmp_path / "src" / "mixins" / "authMixin.js"
        mixin_file.parent.mkdir(parents=True)
        mixin_file.write_text("""
export default {
    methods: {
        go() {
            this.$router.push('/login')
        }
    }
}
""")
        component_source = "this.go()"
        entry = _analyze_mixin_silent(
            "authMixin", str(mixin_file), tmp_path / "src" / "App.vue",
            component_source, [], tmp_path, set(),
        )
        assert entry is not None
        assert len(entry.warnings) > 0
        assert any(w.category == "this.$router" for w in entry.warnings)
        assert all(w.mixin_stem == "authMixin" for w in entry.warnings)

    def test_analyze_clean_mixin_no_warnings(self, tmp_path):
        """Clean mixin should have no warnings."""
        mixin_file = tmp_path / "src" / "mixins" / "counterMixin.js"
        mixin_file.parent.mkdir(parents=True)
        mixin_file.write_text("""
export default {
    data() {
        return { count: 0 }
    },
    methods: {
        increment() {
            this.count++
        }
    }
}
""")
        component_source = "this.count + this.increment()"
        entry = _analyze_mixin_silent(
            "counterMixin", str(mixin_file), tmp_path / "src" / "App.vue",
            component_source, [], tmp_path, set(),
        )
        assert entry is not None
        assert len(entry.warnings) == 0


# ---------------------------------------------------------------------------
# External dependency detection tests
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import detect_external_dependencies


class TestDetectExternalDependencies:
    def test_detects_external_refs(self):
        source = """\
export default {
  data() { return { comments: [] } },
  mounted() {
    if (this.entityId) {
      this.loadComments(this.entityId)
    }
  },
  methods: {
    loadComments(id) {
      this.comments = []
    }
  }
}
"""
        members = MixinMembers(
            data=["comments"],
            methods=["loadComments"],
        )
        warnings = detect_external_dependencies(source, members)
        names = [w.category for w in warnings]
        assert all(c == "external-dependency" for c in names)
        messages = " ".join(w.message for w in warnings)
        assert "entityId" in messages

    def test_no_external_deps(self):
        source = """\
export default {
  data() { return { count: 0 } },
  methods: {
    increment() { this.count++ }
  }
}
"""
        members = MixinMembers(data=["count"], methods=["increment"])
        warnings = detect_external_dependencies(source, members)
        assert warnings == []

    def test_severity_is_error(self):
        source = "function foo() { return this.unknown }"
        members = MixinMembers()
        warnings = detect_external_dependencies(source, members)
        assert len(warnings) == 1
        assert warnings[0].severity == "error"

    def test_excludes_dollar_refs(self):
        source = "function foo() { this.$router.push('/') }"
        members = MixinMembers()
        warnings = detect_external_dependencies(source, members)
        assert warnings == []

    def test_line_hint_present(self):
        source = """\
export default {
  methods: {
    doThing() {
      this.externalProp + 1
    }
  }
}
"""
        members = MixinMembers(methods=["doThing"])
        warnings = detect_external_dependencies(source, members)
        assert len(warnings) == 1
        assert warnings[0].line_hint is not None
        assert "externalProp" in warnings[0].line_hint


# ---------------------------------------------------------------------------
# Bug fix regression: Issue #21 — Missing cleanup detection
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import detect_missing_cleanup


class TestDetectMissingCleanup:
    def test_missing_cleanup_warning(self):
        """addEventListener without removeEventListener should trigger warning."""
        source = '''
    onMounted(() => {
        window.addEventListener('keydown', handleKey)
    })
    '''
        warnings = detect_missing_cleanup(source)
        assert any('cleanup' in w.lower() or 'removeEventListener' in w.lower() for w in warnings)

    def test_no_warning_when_cleanup_present(self):
        """addEventListener with matching removeEventListener should not warn."""
        source = '''
    onMounted(() => {
        window.addEventListener('keydown', handleKey)
    })

    onBeforeUnmount(() => {
        window.removeEventListener('keydown', handleKey)
    })
    '''
        warnings = detect_missing_cleanup(source)
        listener_warnings = [w for w in warnings if 'addEventListener' in w.lower() or 'cleanup' in w.lower()]
        assert len(listener_warnings) == 0

    def test_set_interval_without_clear(self):
        """setInterval without clearInterval should trigger warning."""
        source = '''
    onMounted(() => {
        const id = setInterval(() => { tick() }, 1000)
    })
    '''
        warnings = detect_missing_cleanup(source)
        assert any('setInterval' in w for w in warnings)

    def test_set_interval_with_clear(self):
        """setInterval with clearInterval should not warn."""
        source = '''
    let intervalId = null
    onMounted(() => {
        intervalId = setInterval(() => { tick() }, 1000)
    })
    onBeforeUnmount(() => {
        clearInterval(intervalId)
    })
    '''
        warnings = detect_missing_cleanup(source)
        interval_warnings = [w for w in warnings if 'setInterval' in w]
        assert len(interval_warnings) == 0

    def test_set_timeout_without_clear(self):
        """setTimeout without clearTimeout should trigger warning."""
        source = '''
    onMounted(() => {
        setTimeout(() => { doLater() }, 500)
    })
    '''
        warnings = detect_missing_cleanup(source)
        assert any('setTimeout' in w for w in warnings)

    def test_set_timeout_with_clear(self):
        """setTimeout with clearTimeout should not warn."""
        source = '''
    let timerId = null
    timerId = setTimeout(() => { doLater() }, 500)
    clearTimeout(timerId)
    '''
        warnings = detect_missing_cleanup(source)
        timeout_warnings = [w for w in warnings if 'setTimeout' in w]
        assert len(timeout_warnings) == 0

    def test_no_event_listener_no_warning(self):
        """Source without addEventListener should have no listener warnings."""
        source = '''
    onMounted(() => {
        console.log('mounted')
    })
    '''
        warnings = detect_missing_cleanup(source)
        assert len(warnings) == 0

    def test_add_listener_without_on_mounted(self):
        """addEventListener without onMounted should not trigger the cleanup warning."""
        source = '''
    function setup() {
        window.addEventListener('resize', handleResize)
    }
    '''
        warnings = detect_missing_cleanup(source)
        listener_warnings = [w for w in warnings if 'addEventListener' in w.lower() or 'cleanup' in w.lower()]
        assert len(listener_warnings) == 0


# ---------------------------------------------------------------------------
# Phase 5: this. in parameter positions (Issue #19)
# ---------------------------------------------------------------------------


class TestPostGenThisInParams:
    def test_catches_this_in_params(self):
        """this. in parameter position should trigger a post-gen warning."""
        source = '''
    export function useTest() {
      function downloadFile(blob, this.exportFileName) {
        return blob
      }
      return { downloadFile }
    }
    '''
        warnings = post_generation_check(source)
        assert any(
            w.category == 'this-in-params' for w in warnings
        ), f"Expected 'this-in-params' warning, got: {[w.category for w in warnings]}"

    def test_no_false_positive_for_normal_params(self):
        """Normal function params should not trigger this-in-params warning."""
        source = '''
    export function useTest() {
      function downloadFile(blob, fileName) {
        return blob
      }
      return { downloadFile }
    }
    '''
        warnings = post_generation_check(source)
        assert not any(w.category == 'this-in-params' for w in warnings)


# ---------------------------------------------------------------------------
# Phase 5: Undefined lifecycle references (Issue #22)
# ---------------------------------------------------------------------------


class TestPostGenUndefinedLifecycleRefs:
    def test_catches_undefined_ref_in_lifecycle(self):
        """Lifecycle hooks referencing undefined functions should trigger warning."""
        source = '''
    export function useTest() {
      onMounted(() => {
        handleResize()
        window.addEventListener('resize', handleResize)
      })
      return {}
    }
    '''
        warnings = post_generation_check(source)
        assert any(
            'handleResize' in w.message for w in warnings
        ), f"Expected warning about 'handleResize', got: {[w.message for w in warnings]}"

    def test_no_warning_when_function_defined(self):
        """No warning when lifecycle-referenced function is defined in composable."""
        source = '''
    export function useTest() {
      function handleResize() { console.log('resize') }
      onMounted(() => {
        handleResize()
      })
      return { handleResize }
    }
    '''
        warnings = post_generation_check(source)
        assert not any(
            'handleResize' in w.message for w in warnings
        ), f"Should not warn about defined function, got: {[w.message for w in warnings]}"

    def test_no_warning_for_builtins(self):
        """Built-in functions like console, window, etc. should not trigger warning."""
        source = '''
    export function useTest() {
      onMounted(() => {
        console.log('mounted')
        window.addEventListener('resize', () => {})
      })
      return {}
    }
    '''
        warnings = post_generation_check(source)
        assert not any(
            w.category == 'undefined-in-lifecycle' for w in warnings
        ), f"Should not warn about builtins, got: {[w.message for w in warnings]}"

    def test_const_defined_function_not_flagged(self):
        """Functions defined with const should not be flagged as undefined."""
        source = '''
    export function useTest() {
      const doWork = () => { return 42 }
      onMounted(() => {
        doWork()
      })
      return { doWork }
    }
    '''
        warnings = post_generation_check(source)
        assert not any(
            'doWork' in w.message for w in warnings
        )


# ---------------------------------------------------------------------------
# Phase 6: Factory mixin warning improvements (Issue #16)
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import detect_structural_patterns


class TestFactoryMixinWarnings:
    def test_factory_mixin_includes_param_names(self):
        """Factory mixin warning should include parameter names."""
        source = '''
        export default function(defaultKey) {
            return {
                data() { return { key: defaultKey } },
                methods: { doSomething() {} }
            }
        }
        '''
        warnings = detect_structural_patterns(source, "factoryMixin")
        factory_warnings = [w for w in warnings if w.category == "structural:factory-function"]
        assert len(factory_warnings) == 1
        assert "defaultKey" in factory_warnings[0].message
        assert "params" in factory_warnings[0].message.lower()

    def test_factory_mixin_multiple_params(self):
        """Factory mixin warning should list all parameter names."""
        source = '''
        export default function createMixin(key, options) {
            return {
                data() { return { key } }
            }
        }
        '''
        warnings = detect_structural_patterns(source, "factoryMixin")
        factory_warnings = [w for w in warnings if w.category == "structural:factory-function"]
        assert len(factory_warnings) == 1
        assert "key" in factory_warnings[0].message
        assert "options" in factory_warnings[0].message

    def test_factory_mixin_no_params(self):
        """Factory mixin with no params should say 'no params'."""
        source = '''
        export default function() {
            return {
                data() { return { x: 1 } }
            }
        }
        '''
        warnings = detect_structural_patterns(source, "factoryMixin")
        factory_warnings = [w for w in warnings if w.category == "structural:factory-function"]
        assert len(factory_warnings) == 1
        assert "no params" in factory_warnings[0].message.lower()


# ---------------------------------------------------------------------------
# Phase 6: Transitive mixin warning improvements (Issue #17)
# ---------------------------------------------------------------------------


class TestTransitiveMixinWarnings:
    def test_nested_mixin_names_included(self):
        """Transitive mixin warning should list the nested mixin names."""
        source = '''
        import validationMixin from './validationMixin'
        import formMixin from './formMixin'

        export default {
            mixins: [validationMixin, formMixin],
            data() { return { value: '' } }
        }
        '''
        warnings = detect_structural_patterns(source, "combinedMixin")
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert len(nested_warnings) == 1
        assert "validationMixin" in nested_warnings[0].message
        assert "formMixin" in nested_warnings[0].message

    def test_single_nested_mixin_name_included(self):
        """Single nested mixin name should be included in the warning."""
        source = '''
        export default {
            mixins: [baseMixin],
            data() { return { x: 1 } }
        }
        '''
        warnings = detect_structural_patterns(source, "childMixin")
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert len(nested_warnings) == 1
        assert "baseMixin" in nested_warnings[0].message


# ---------------------------------------------------------------------------
# B2: Suppress warnings when composable already has alternative implementation
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import suppress_resolved_warnings


class TestSuppressResolvedWarnings:
    def test_external_dep_suppressed_when_in_declared(self):
        """External dep warning suppressed when name is in composable_declared."""
        warnings = [
            MigrationWarning(
                mixin_stem="myMixin", category="external-dependency",
                message="'items' — external dep, not available in composable scope",
                action_required="Accept 'items' as a composable parameter",
                line_hint="this.items.length", severity="error",
            ),
        ]
        result = suppress_resolved_warnings(warnings, ["items", "loadData"])
        assert len(result) == 0

    def test_external_dep_not_suppressed_when_missing(self):
        """External dep warning NOT suppressed when name is missing from composable_declared."""
        warnings = [
            MigrationWarning(
                mixin_stem="myMixin", category="external-dependency",
                message="'entityId' — external dep, not available in composable scope",
                action_required="Accept 'entityId' as a composable parameter",
                line_hint="this.entityId", severity="error",
            ),
        ]
        result = suppress_resolved_warnings(warnings, ["items", "loadData"])
        assert len(result) == 1
        assert result[0].message == warnings[0].message

    def test_this_router_suppressed_when_composable_has_useRouter(self):
        """this.$router warning suppressed when composable contains useRouter."""
        warnings = [
            MigrationWarning(
                mixin_stem="authMixin", category="this.$router",
                message="this.$router is not available in composables",
                action_required="Import and use useRouter() from vue-router",
                line_hint="this.$router.push('/login')", severity="error",
            ),
        ]
        comp_source = """
import { useRouter } from 'vue-router'
export function useAuth() {
  const router = useRouter()
  return { router }
}
"""
        result = suppress_resolved_warnings(warnings, [], comp_source)
        assert len(result) == 0

    def test_this_router_not_suppressed_when_composable_lacks_useRouter(self):
        """this.$router warning NOT suppressed when composable lacks useRouter."""
        warnings = [
            MigrationWarning(
                mixin_stem="authMixin", category="this.$router",
                message="this.$router is not available in composables",
                action_required="Import and use useRouter() from vue-router",
                line_hint="this.$router.push('/login')", severity="error",
            ),
        ]
        comp_source = """
export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        result = suppress_resolved_warnings(warnings, [], comp_source)
        assert len(result) == 1

    def test_this_t_suppressed_when_composable_has_useI18n(self):
        """this.$t warning suppressed when composable contains useI18n."""
        warnings = [
            MigrationWarning(
                mixin_stem="i18nMixin", category="this.$t",
                message="this.$t — needs useI18n()",
                action_required="Use useI18n()",
                line_hint="this.$t('key')", severity="warning",
            ),
        ]
        comp_source = """
import { useI18n } from 'vue-i18n'
export function useTranslation() {
  const { t } = useI18n()
  return { t }
}
"""
        result = suppress_resolved_warnings(warnings, [], comp_source)
        assert len(result) == 0

    def test_mixed_scenario_some_suppressed_some_kept(self):
        """Mixed scenario: some warnings suppressed, others kept."""
        warnings = [
            MigrationWarning(
                mixin_stem="myMixin", category="external-dependency",
                message="'items' — external dep, not available in composable scope",
                action_required="Accept 'items'",
                line_hint="this.items", severity="error",
            ),
            MigrationWarning(
                mixin_stem="myMixin", category="external-dependency",
                message="'userId' — external dep, not available in composable scope",
                action_required="Accept 'userId'",
                line_hint="this.userId", severity="error",
            ),
            MigrationWarning(
                mixin_stem="myMixin", category="this.$router",
                message="this.$router is not available in composables",
                action_required="Import and use useRouter()",
                line_hint="this.$router.push('/')", severity="error",
            ),
        ]
        comp_source = """
import { useRouter } from 'vue-router'
export function useMyMixin() {
  const router = useRouter()
  const items = ref([])
  return { items, router }
}
"""
        result = suppress_resolved_warnings(warnings, ["items"], comp_source)
        # 'items' ext dep: suppressed (in declared)
        # 'userId' ext dep: kept (not in declared)
        # this.$router: suppressed (useRouter in source)
        assert len(result) == 1
        assert "'userId'" in result[0].message

    def test_non_suppressible_categories_pass_through(self):
        """Non-suppressible categories (e.g. this-alias, mixin-option:props) pass through unchanged."""
        warnings = [
            MigrationWarning(
                mixin_stem="myMixin", category="this-alias",
                message="'this' is aliased as 'self'",
                action_required="Manually replace self.x",
                line_hint="const self = this", severity="warning",
            ),
            MigrationWarning(
                mixin_stem="myMixin", category="mixin-option:props",
                message="Mixin defines props",
                action_required="Use defineProps()",
                line_hint=None, severity="warning",
            ),
        ]
        comp_source = "export function useFoo() { return {} }"
        result = suppress_resolved_warnings(warnings, ["items"], comp_source)
        assert len(result) == 2

    def test_this_store_suppressed_with_pinia_store(self):
        """this.$store suppressed when composable uses a Pinia store (useXxxStore pattern)."""
        warnings = [
            MigrationWarning(
                mixin_stem="myMixin", category="this.$store",
                message="this.$store is not available in composables",
                action_required="Import and use the Pinia/Vuex store directly",
                line_hint="this.$store.dispatch('load')", severity="error",
            ),
        ]
        comp_source = """
import { useAuthStore } from '@/stores/auth'
export function useMyMixin() {
  const store = useAuthStore()
  return { store }
}
"""
        result = suppress_resolved_warnings(warnings, [], comp_source)
        assert len(result) == 0

    def test_no_suppression_without_composable_source(self):
        """this.$X warnings are NOT suppressed when composable_source is None."""
        warnings = [
            MigrationWarning(
                mixin_stem="myMixin", category="this.$router",
                message="this.$router is not available in composables",
                action_required="Import and use useRouter()",
                line_hint="this.$router.push('/')", severity="error",
            ),
        ]
        result = suppress_resolved_warnings(warnings, [], composable_source=None)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Catch-all unknown this.$xxx warnings
# ---------------------------------------------------------------------------

class TestUnknownThisDollarCatchAll:
    """Tests for the catch-all that flags unknown this.$<ident> patterns."""

    def _make_members(self):
        return MixinMembers()

    def test_unknown_plugin_property_triggers_warning(self):
        """this.$toast should produce a catch-all warning."""
        source = """
export default {
    methods: {
        showError() {
            this.$toast.error('Something went wrong')
        }
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        cats = [w.category for w in warnings]
        assert "this.$toast" in cats
        w = next(w for w in warnings if w.category == "this.$toast")
        assert w.severity == "warning"
        assert "$toast" in w.message
        assert "inject()" in w.action_required

    def test_unknown_confirm_plugin(self):
        """this.$confirm() should produce a catch-all warning."""
        source = """
export default {
    methods: {
        remove() {
            this.$confirm('Are you sure?')
        }
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        cats = [w.category for w in warnings]
        assert "this.$confirm" in cats

    def test_known_patterns_no_duplicate(self):
        """Known patterns like this.$router should NOT produce a catch-all duplicate."""
        source = """
export default {
    methods: {
        go() {
            this.$router.push('/home')
        }
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        router_warnings = [w for w in warnings if w.category == "this.$router"]
        assert len(router_warnings) == 1

    def test_auto_rewritten_skipped(self):
        """$nextTick, $set, $delete are auto-rewritten — no warning."""
        source = """
export default {
    methods: {
        update() {
            this.$nextTick(() => {})
            this.$set(this.obj, 'key', 'val')
            this.$delete(this.obj, 'key')
        }
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        cats = [w.category for w in warnings]
        assert "this.$nextTick" not in cats
        assert "this.$set" not in cats
        assert "this.$delete" not in cats

    def test_deduplication_same_identifier(self):
        """this.$toast used 3 times should produce only 1 warning."""
        source = """
export default {
    methods: {
        a() { this.$toast.info('a') },
        b() { this.$toast.error('b') },
        c() { this.$toast.success('c') },
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        toast_warnings = [w for w in warnings if w.category == "this.$toast"]
        assert len(toast_warnings) == 1

    def test_multiple_unknown_identifiers(self):
        """this.$toast + this.$modal should produce 2 separate warnings."""
        source = """
export default {
    methods: {
        show() {
            this.$toast.info('hi')
            this.$modal.open('dialog')
        }
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        cats = {w.category for w in warnings}
        assert "this.$toast" in cats
        assert "this.$modal" in cats

    def test_line_hint_captured(self):
        """The catch-all warning should capture the source line."""
        source = """
export default {
    methods: {
        notify() {
            this.$modalMessageBx.show('hello')
        }
    }
}
"""
        warnings = collect_mixin_warnings(source, self._make_members(), [])
        w = next(w for w in warnings if w.category == "this.$modalMessageBx")
        assert w.line_hint is not None
        assert "$modalMessageBx" in w.line_hint

    def test_short_hint_fallback(self):
        """Unknown this.$ categories should get a generic short hint."""
        from vue3_migration.core.warning_collector import _get_short_hint
        w = MigrationWarning(
            mixin_stem="", category="this.$customThing",
            message="test", action_required="test",
            line_hint=None, severity="warning",
        )
        hint = _get_short_hint(w)
        assert "plugin property" in hint


# ---------------------------------------------------------------------------
# Resolve nested mixin members
# ---------------------------------------------------------------------------

import os
import tempfile
from vue3_migration.core.warning_collector import resolve_nested_mixin_members


def _write_mixin_file(directory, name, source):
    """Helper to write a mixin file and return its path."""
    path = os.path.join(directory, f"{name}.js")
    with open(path, "w") as f:
        f.write(source)
    return Path(path)


class TestResolveNestedMixinMembers:
    """Tests for resolve_nested_mixin_members() — resolves nested mixin files
    and extracts their members."""

    def test_single_nested_mixin_resolved(self, tmp_path):
        """A mixin with one nested mixin should have its members resolved."""
        _write_mixin_file(tmp_path, "validationMixin", """
export default {
    data() { return { isValid: false, errors: [] } },
    methods: { validate() {}, clearErrors() {} }
}
""")
        parent_source = f"""
import validationMixin from './validationMixin'
export default {{
    mixins: [validationMixin],
    data() {{ return {{ value: '' }} }}
}}
"""
        parent_path = _write_mixin_file(tmp_path, "parentMixin", parent_source)
        result = resolve_nested_mixin_members(parent_source, parent_path, tmp_path)

        assert "validationMixin" in result
        assert result["validationMixin"] is not None
        assert "isValid" in result["validationMixin"]["data"]
        assert "errors" in result["validationMixin"]["data"]
        assert "validate" in result["validationMixin"]["methods"]
        assert "clearErrors" in result["validationMixin"]["methods"]

    def test_multiple_nested_mixins_resolved(self, tmp_path):
        """Multiple nested mixins should all be resolved."""
        _write_mixin_file(tmp_path, "validationMixin", """
export default {
    data() { return { isValid: false } },
    methods: { validate() {} }
}
""")
        _write_mixin_file(tmp_path, "formMixin", """
export default {
    data() { return { formData: {} } },
    computed: { isFormDirty() {} },
    methods: { submitForm() {} }
}
""")
        parent_source = """
import validationMixin from './validationMixin'
import formMixin from './formMixin'
export default {
    mixins: [validationMixin, formMixin],
    data() { return { name: '' } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "parentMixin", parent_source)
        result = resolve_nested_mixin_members(parent_source, parent_path, tmp_path)

        assert "validationMixin" in result
        assert "formMixin" in result
        assert result["validationMixin"] is not None
        assert result["formMixin"] is not None
        assert "isValid" in result["validationMixin"]["data"]
        assert "formData" in result["formMixin"]["data"]
        assert "isFormDirty" in result["formMixin"]["computed"]

    def test_chain_resolution(self, tmp_path):
        """Chain A → B → C should resolve all transitive members."""
        _write_mixin_file(tmp_path, "mixinC", """
export default {
    data() { return { deepValue: 0 } },
    methods: { deepMethod() {} }
}
""")
        _write_mixin_file(tmp_path, "mixinB", """
import mixinC from './mixinC'
export default {
    mixins: [mixinC],
    data() { return { midValue: '' } },
    computed: { midComputed() {} }
}
""")
        parent_source = """
import mixinB from './mixinB'
export default {
    mixins: [mixinB],
    data() { return { topValue: true } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "mixinA", parent_source)
        result = resolve_nested_mixin_members(parent_source, parent_path, tmp_path)

        # mixinB is directly nested
        assert "mixinB" in result
        assert result["mixinB"] is not None
        assert "midValue" in result["mixinB"]["data"]
        assert "midComputed" in result["mixinB"]["computed"]
        # mixinC is transitively nested (via mixinB)
        assert "mixinC" in result
        assert result["mixinC"] is not None
        assert "deepValue" in result["mixinC"]["data"]
        assert "deepMethod" in result["mixinC"]["methods"]

    def test_circular_mixins_no_infinite_loop(self, tmp_path):
        """Circular A → B → A should not cause infinite recursion."""
        _write_mixin_file(tmp_path, "mixinA", """
import mixinB from './mixinB'
export default {
    mixins: [mixinB],
    data() { return { aValue: 1 } }
}
""")
        _write_mixin_file(tmp_path, "mixinB", """
import mixinA from './mixinA'
export default {
    mixins: [mixinA],
    data() { return { bValue: 2 } }
}
""")
        source_a = """
import mixinB from './mixinB'
export default {
    mixins: [mixinB],
    data() { return { aValue: 1 } }
}
"""
        path_a = tmp_path / "mixinA.js"
        result = resolve_nested_mixin_members(source_a, path_a, tmp_path)

        # Should resolve mixinB but not recurse back into mixinA infinitely
        assert "mixinB" in result
        assert result["mixinB"] is not None
        assert "bValue" in result["mixinB"]["data"]

    def test_diamond_dependency_deduplication(self, tmp_path):
        """Diamond: A → B,C; B,C → D — D members should appear once."""
        _write_mixin_file(tmp_path, "mixinD", """
export default {
    data() { return { shared: true } },
    methods: { sharedMethod() {} }
}
""")
        _write_mixin_file(tmp_path, "mixinB", """
import mixinD from './mixinD'
export default {
    mixins: [mixinD],
    data() { return { bOnly: 1 } }
}
""")
        _write_mixin_file(tmp_path, "mixinC", """
import mixinD from './mixinD'
export default {
    mixins: [mixinD],
    data() { return { cOnly: 2 } }
}
""")
        parent_source = """
import mixinB from './mixinB'
import mixinC from './mixinC'
export default {
    mixins: [mixinB, mixinC],
    data() { return { topVal: 0 } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "mixinA", parent_source)
        result = resolve_nested_mixin_members(parent_source, parent_path, tmp_path)

        assert "mixinB" in result
        assert "mixinC" in result
        assert "mixinD" in result
        # mixinD should appear exactly once as a key
        assert list(result.keys()).count("mixinD") == 1
        assert "shared" in result["mixinD"]["data"]

    def test_unresolvable_mixin_returns_none(self, tmp_path):
        """A nested mixin whose file can't be found returns None."""
        parent_source = """
import ghostMixin from './ghostMixin'
export default {
    mixins: [ghostMixin],
    data() { return { x: 1 } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "parentMixin", parent_source)
        result = resolve_nested_mixin_members(parent_source, parent_path, tmp_path)

        assert "ghostMixin" in result
        assert result["ghostMixin"] is None

    def test_mixed_resolvable_and_unresolvable(self, tmp_path):
        """Mix of found and missing nested mixins."""
        _write_mixin_file(tmp_path, "realMixin", """
export default {
    data() { return { realData: 1 } }
}
""")
        parent_source = """
import realMixin from './realMixin'
import missingMixin from './missingMixin'
export default {
    mixins: [realMixin, missingMixin],
    data() { return { x: 0 } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "parentMixin", parent_source)
        result = resolve_nested_mixin_members(parent_source, parent_path, tmp_path)

        assert "realMixin" in result
        assert result["realMixin"] is not None
        assert "realData" in result["realMixin"]["data"]
        assert "missingMixin" in result
        assert result["missingMixin"] is None

    def test_no_path_context_returns_empty(self):
        """When mixin_path and project_root are None, returns empty dict."""
        source = """
import foo from './foo'
export default {
    mixins: [foo],
    data() { return { x: 1 } }
}
"""
        result = resolve_nested_mixin_members(source, None, None)
        assert result == {}

    def test_cache_only_resolution(self, tmp_path):
        """When all_mixin_members cache is provided, uses it instead of filesystem."""
        parent_source = """
import cachedMixin from './cachedMixin'
export default {
    mixins: [cachedMixin],
    data() { return { x: 1 } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "parentMixin", parent_source)
        cache = {
            "cachedMixin": {"data": ["cachedVal"], "computed": [], "methods": ["cachedMethod"], "watch": []}
        }
        result = resolve_nested_mixin_members(
            parent_source, parent_path, tmp_path,
            all_mixin_members=cache,
        )

        assert "cachedMixin" in result
        assert result["cachedMixin"] is not None
        assert "cachedVal" in result["cachedMixin"]["data"]
        assert "cachedMethod" in result["cachedMixin"]["methods"]

    def test_depth_limit_exceeded(self, tmp_path):
        """When recursion depth exceeds max, stops and returns partial results."""
        # Create a chain deeper than max_depth
        # We'll use _max_depth=2 to test without creating many files
        _write_mixin_file(tmp_path, "mixinC", """
export default {
    data() { return { cVal: 3 } }
}
""")
        _write_mixin_file(tmp_path, "mixinB", """
import mixinC from './mixinC'
export default {
    mixins: [mixinC],
    data() { return { bVal: 2 } }
}
""")
        parent_source = """
import mixinB from './mixinB'
export default {
    mixins: [mixinB],
    data() { return { aVal: 1 } }
}
"""
        parent_path = _write_mixin_file(tmp_path, "mixinA", parent_source)

        # With _max_depth=1, should resolve mixinB but NOT recurse into mixinC
        result = resolve_nested_mixin_members(
            parent_source, parent_path, tmp_path,
            _max_depth=1,
        )

        assert "mixinB" in result
        assert result["mixinB"] is not None
        # mixinC should NOT be resolved because depth limit was reached
        assert "mixinC" not in result

    def test_no_nested_mixins_returns_empty(self, tmp_path):
        """A mixin without nested mixins returns empty dict."""
        source = """
export default {
    data() { return { x: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "simpleMixin", source)
        result = resolve_nested_mixin_members(source, path, tmp_path)
        assert result == {}

    def test_no_import_for_nested_mixin(self, tmp_path):
        """Nested mixin referenced but no import statement — unresolvable."""
        source = """
export default {
    mixins: [unknownMixin],
    data() { return { x: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        result = resolve_nested_mixin_members(source, path, tmp_path)

        assert "unknownMixin" in result
        assert result["unknownMixin"] is None


# ---------------------------------------------------------------------------
# Enhanced detect_structural_patterns() warning messages
# ---------------------------------------------------------------------------


class TestEnhancedNestedMixinWarnings:
    """Tests for enriched nested mixin warnings with resolved member listings."""

    def test_no_warning_when_all_resolved(self, tmp_path):
        """When path context provided and all nested mixins resolve,
        the structural:nested-mixins warning is suppressed (external-dep
        warnings already cover any used transitive members)."""
        _write_mixin_file(tmp_path, "validationMixin", """
export default {
    data() { return { isValid: false, errors: [] } },
    methods: { validate() {} }
}
""")
        source = """
import validationMixin from './validationMixin'
export default {
    mixins: [validationMixin],
    data() { return { x: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        warnings = detect_structural_patterns(
            source, "parentMixin",
            mixin_path=path, project_root=tmp_path,
        )
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert nested_warnings == [], (
            "Resolved nested mixins should NOT produce structural:nested-mixins warning"
        )

    def test_backward_compat_no_path_context(self):
        """When path context is None, original vague warning is produced."""
        source = """
import foo from './foo'
export default {
    mixins: [foo],
    data() { return { x: 1 } }
}
"""
        warnings = detect_structural_patterns(source, "testMixin")
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]

        assert len(nested_warnings) == 1
        assert "transitive members may be missed" in nested_warnings[0].message

    def test_unresolvable_mixin_in_warning(self, tmp_path):
        """Unresolvable mixin shows 'file not found' in message."""
        source = """
import ghostMixin from './ghostMixin'
export default {
    mixins: [ghostMixin],
    data() { return { x: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        warnings = detect_structural_patterns(
            source, "parentMixin",
            mixin_path=path, project_root=tmp_path,
        )
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]

        assert len(nested_warnings) == 1
        msg = nested_warnings[0].message
        assert "ghostMixin" in msg
        assert "file not found" in msg.lower()

    def test_mixed_resolved_and_unresolved_warns_only_unresolved(self, tmp_path):
        """Warning only mentions unresolvable mixins; resolved ones are suppressed."""
        _write_mixin_file(tmp_path, "realMixin", """
export default {
    data() { return { realData: 1 } },
    methods: { realMethod() {} }
}
""")
        source = """
import realMixin from './realMixin'
import ghostMixin from './ghostMixin'
export default {
    mixins: [realMixin, ghostMixin],
    data() { return { x: 0 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        warnings = detect_structural_patterns(
            source, "parentMixin",
            mixin_path=path, project_root=tmp_path,
        )
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]

        assert len(nested_warnings) == 1
        msg = nested_warnings[0].message
        # Resolved mixin should NOT be in the warning
        assert "realMixin" not in msg
        # unresolved mixin noted
        assert "ghostMixin" in msg
        assert "file not found" in msg.lower()

    def test_chain_all_resolved_suppresses_warning(self, tmp_path):
        """Chain resolution: A → B → C all resolve, so warning is suppressed."""
        _write_mixin_file(tmp_path, "deepMixin", """
export default {
    data() { return { deepVal: 0 } }
}
""")
        _write_mixin_file(tmp_path, "midMixin", """
import deepMixin from './deepMixin'
export default {
    mixins: [deepMixin],
    methods: { midMethod() {} }
}
""")
        source = """
import midMixin from './midMixin'
export default {
    mixins: [midMixin],
    data() { return { topVal: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "topMixin", source)
        warnings = detect_structural_patterns(
            source, "topMixin",
            mixin_path=path, project_root=tmp_path,
        )
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert nested_warnings == [], (
            "All resolved chain should NOT produce structural:nested-mixins warning"
        )

    def test_all_resolved_suppresses_warning(self, tmp_path):
        """When all nested mixins resolve, no warning is emitted."""
        _write_mixin_file(tmp_path, "helperMixin", """
export default {
    data() { return { helperVal: 1 } }
}
""")
        source = """
import helperMixin from './helperMixin'
export default {
    mixins: [helperMixin],
    data() { return { x: 0 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        warnings = detect_structural_patterns(
            source, "parentMixin",
            mixin_path=path, project_root=tmp_path,
        )
        nested_warnings = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert nested_warnings == []


# ---------------------------------------------------------------------------
# Integration test: kitchenSinkMixin fixture
# ---------------------------------------------------------------------------


class TestKitchenSinkNestedMixinIntegration:
    """Integration test using the real kitchenSinkMixin fixture."""

    def test_kitchen_sink_nested_helper_resolved_suppresses_warning(self):
        """kitchenSinkMixin → nestedHelper resolves fully, so the
        structural:nested-mixins warning should be suppressed."""
        from vue3_migration.core.warning_collector import collect_mixin_warnings
        from vue3_migration.core.mixin_analyzer import extract_mixin_members, extract_lifecycle_hooks

        mixin_path = Path("tests/fixtures/dummy_project/src/mixins/kitchenSinkMixin.js")
        project_root = Path("tests/fixtures/dummy_project")
        source = mixin_path.read_text()
        members = MixinMembers(**extract_mixin_members(source))
        hooks = extract_lifecycle_hooks(source)

        warnings = collect_mixin_warnings(
            source, members, hooks,
            mixin_path=mixin_path, project_root=project_root,
        )
        nested = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert nested == [], (
            "nestedHelper resolves fully — no structural:nested-mixins warning expected"
        )


# ---------------------------------------------------------------------------
# Resolve nested member chains (member → source mixin + chain path)
# ---------------------------------------------------------------------------

from vue3_migration.core.warning_collector import resolve_nested_member_chains


class TestResolveNestedMemberChains:
    """Tests for resolve_nested_member_chains() — maps each member to its
    source mixin and full chain path."""

    def test_single_level_chain(self, tmp_path):
        """Members from a direct nested mixin have a 2-element chain."""
        _write_mixin_file(tmp_path, "validationMixin", """
export default {
    data() { return { isValid: false } },
    methods: { validate() {} }
}
""")
        source = """
import validationMixin from './validationMixin'
export default {
    mixins: [validationMixin],
    data() { return { x: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        chains = resolve_nested_member_chains(source, path, tmp_path)

        assert "isValid" in chains
        assert chains["isValid"][0] == "validationMixin"
        assert chains["isValid"][1] == ["parentMixin", "validationMixin"]

        assert "validate" in chains
        assert chains["validate"][0] == "validationMixin"

    def test_deep_chain(self, tmp_path):
        """Members from A -> B -> C have a 3-element chain."""
        _write_mixin_file(tmp_path, "mixinC", """
export default {
    data() { return { deepVal: 0 } }
}
""")
        _write_mixin_file(tmp_path, "mixinB", """
import mixinC from './mixinC'
export default {
    mixins: [mixinC],
    data() { return { midVal: 1 } }
}
""")
        source = """
import mixinB from './mixinB'
export default {
    mixins: [mixinB],
    data() { return { topVal: 2 } }
}
"""
        path = _write_mixin_file(tmp_path, "mixinA", source)
        chains = resolve_nested_member_chains(source, path, tmp_path)

        assert "midVal" in chains
        assert chains["midVal"][0] == "mixinB"
        assert chains["midVal"][1] == ["mixinA", "mixinB"]

        assert "deepVal" in chains
        assert chains["deepVal"][0] == "mixinC"
        assert chains["deepVal"][1] == ["mixinA", "mixinB", "mixinC"]

    def test_unresolvable_mixin_not_in_chains(self, tmp_path):
        """Members from unresolvable mixins don't appear in chains."""
        source = """
import ghostMixin from './ghostMixin'
export default {
    mixins: [ghostMixin],
    data() { return { x: 1 } }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        chains = resolve_nested_member_chains(source, path, tmp_path)
        assert chains == {}

    def test_no_path_context_returns_empty(self):
        """When paths are None, returns empty dict."""
        source = """
export default {
    mixins: [foo],
    data() { return { x: 1 } }
}
"""
        chains = resolve_nested_member_chains(source, None, None)
        assert chains == {}


# ---------------------------------------------------------------------------
# Enriched external dep warnings with chain info
# ---------------------------------------------------------------------------


class TestEnrichedExternalDepWarnings:
    """External dep warnings should include chain info when the dep
    comes from a resolved transitive mixin."""

    def test_resolved_dep_mentions_source_mixin(self, tmp_path):
        """External dep from a nested mixin should name the source mixin."""
        _write_mixin_file(tmp_path, "nestedMixin", """
export default {
    data() { return { nestedVal: 1 } }
}
""")
        source = """
import nestedMixin from './nestedMixin'
export default {
    mixins: [nestedMixin],
    methods: {
        doSomething() {
            this.nestedVal = 2
        }
    }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        warnings = collect_mixin_warnings(
            source, MixinMembers(data=[], computed=[], methods=["doSomething"]), [],
            mixin_path=path, project_root=tmp_path,
        )
        ext_dep = [w for w in warnings if w.category == "external-dependency" and "nestedVal" in w.message]
        assert len(ext_dep) == 1
        assert "nestedMixin" in ext_dep[0].message
        assert "→" in ext_dep[0].message

    def test_short_chain_shows_full_in_inline_hint(self, tmp_path):
        """Chain of 2 items should show full chain in inline hint."""
        from vue3_migration.core.warning_collector import _get_short_hint

        _write_mixin_file(tmp_path, "nestedMixin", """
export default {
    data() { return { nestedVal: 1 } }
}
""")
        source = """
import nestedMixin from './nestedMixin'
export default {
    mixins: [nestedMixin],
    methods: {
        doSomething() { this.nestedVal = 2 }
    }
}
"""
        path = _write_mixin_file(tmp_path, "parentMixin", source)
        warnings = collect_mixin_warnings(
            source, MixinMembers(data=[], computed=[], methods=["doSomething"]), [],
            mixin_path=path, project_root=tmp_path,
        )
        ext_dep = [w for w in warnings if w.category == "external-dependency" and "nestedVal" in w.message]
        assert len(ext_dep) == 1
        hint = _get_short_hint(ext_dep[0])
        assert "nestedVal" in hint
        assert "nestedMixin" in hint
        assert "parentMixin" in hint  # short chain shows full path
        assert "param" in hint

    def test_long_chain_omits_chain_in_inline_hint(self, tmp_path):
        """Chain > 2 items: inline hint shows source only, not full chain."""
        from vue3_migration.core.warning_collector import _get_short_hint

        _write_mixin_file(tmp_path, "mixinC", """
export default {
    data() { return { deepVal: 0 } }
}
""")
        _write_mixin_file(tmp_path, "mixinB", """
import mixinC from './mixinC'
export default {
    mixins: [mixinC],
    data() { return { midVal: 1 } }
}
""")
        source = """
import mixinB from './mixinB'
export default {
    mixins: [mixinB],
    methods: {
        doSomething() { this.deepVal = 99 }
    }
}
"""
        path = _write_mixin_file(tmp_path, "mixinA", source)
        warnings = collect_mixin_warnings(
            source, MixinMembers(data=[], computed=[], methods=["doSomething"]), [],
            mixin_path=path, project_root=tmp_path,
        )
        ext_dep = [w for w in warnings if w.category == "external-dependency" and "deepVal" in w.message]
        assert len(ext_dep) == 1
        hint = _get_short_hint(ext_dep[0])
        assert "deepVal" in hint
        assert "mixinC" in hint
        # Should NOT contain the full chain in inline hint
        assert "mixinA" not in hint
        assert "param" in hint

    def test_unresolved_dep_keeps_generic_hint(self, tmp_path):
        """External deps not from a transitive mixin keep generic message."""
        source = """
export default {
    methods: {
        doSomething() {
            this.unknownThing = 1
        }
    }
}
"""
        path = _write_mixin_file(tmp_path, "someMixin", source)
        warnings = collect_mixin_warnings(
            source, MixinMembers(data=[], computed=[], methods=["doSomething"]), [],
            mixin_path=path, project_root=tmp_path,
        )
        ext_dep = [w for w in warnings if w.category == "external-dependency" and "unknownThing" in w.message]
        assert len(ext_dep) == 1
        assert "pass unknownThing as param, function arg, or use another composable" in ext_dep[0].message
        assert ext_dep[0].message.startswith("'unknownThing'")


class TestMultipleWarningsOnSameLine:
    """When a line matches multiple warning patterns (e.g. this.$on + this.handleCustom),
    all matching warnings should be annotated, not just the first one."""

    def test_external_dep_annotated_when_sharing_line_with_this_dollar(self):
        """this.$on('custom', this.handleCustom) — both this.$on and handleCustom
        should get inline annotations."""
        source = (
            "export function useX() {\n"
            "  function listenEvents() {\n"
            "    this.$on('custom', this.handleCustom)\n"
            "  }\n"
            "  return { listenEvents }\n"
            "}\n"
        )
        warnings = [
            MigrationWarning("x", "this.$on",
                             "this.$on removed in Vue 3",
                             "Use event bus or provide/inject",
                             "this.$on('custom', this.handleCustom)",
                             "error"),
            MigrationWarning("x", "external-dependency",
                             "'handleCustom' — pass handleCustom as param, function arg, or use another composable",
                             "Accept as param",
                             "this.handleCustom",
                             "error"),
        ]
        result = inject_inline_warnings(source, warnings)
        target_line = [l for l in result.splitlines() if "this.$on" in l][0]
        # Both warnings should be visible on this line
        assert "event bus" in target_line or "removed in Vue 3" in target_line
        assert "handleCustom" in target_line and "external dep" in target_line


class TestChainInfoInGeneratedComposable:
    """Chain info from transitive mixin resolution should appear in
    generated composable inline comments, not just the report."""

    def test_generated_composable_shows_chain_in_inline_comment(self, tmp_path):
        """When a mixin has nested mixins and an external dep resolves to a
        transitive mixin, the inline comment should include the chain info."""
        from vue3_migration.transform.composable_generator import generate_composable_from_mixin

        # Create leaf mixin with a 'leafFlag' data member
        leaf = tmp_path / "leafMixin.js"
        leaf.write_text("export default {\n  data() { return { leafFlag: true } }\n}\n")

        # Create parent mixin that nests leaf and references this.leafFlag
        parent = tmp_path / "parentMixin.js"
        parent.write_text(
            "import leafMixin from './leafMixin'\n"
            "export default {\n"
            "  mixins: [leafMixin],\n"
            "  data() { return { myVal: 1 } },\n"
            "  methods: {\n"
            "    doWork() { this.leafFlag = false }\n"
            "  }\n"
            "}\n"
        )

        mixin_source = parent.read_text()
        members = MixinMembers(data=["myVal"], computed=[], methods=["doWork"])

        result = generate_composable_from_mixin(
            mixin_source, "parentMixin", members, [],
            mixin_path=parent, composable_path=tmp_path / "useParent.js",
            project_root=tmp_path,
        )

        # The inline comment for this.leafFlag should mention the chain
        leaf_line = [l for l in result.splitlines()
                     if "leafFlag" in l and "external dep" in l]
        assert leaf_line, f"Expected inline comment with chain info for leafFlag, got:\n{result}"
        assert "leafMixin" in leaf_line[0], (
            f"Expected chain mentioning 'leafMixin' in: {leaf_line[0]}"
        )


class TestNestedMixinsWarningSuppression:
    """structural:nested-mixins warning should be suppressed when chain
    resolution succeeds, because external-dependency warnings already
    provide chain-enriched info for any used transitive members."""

    def test_no_nested_warning_when_resolved(self, tmp_path):
        """When path context is available and nested mixins resolve,
        the structural:nested-mixins warning should NOT be emitted."""
        leaf = tmp_path / "childMixin.js"
        leaf.write_text("export default {\n  data() { return { x: 1 } }\n}\n")

        parent = tmp_path / "parentMixin.js"
        parent.write_text(
            "import childMixin from './childMixin'\n"
            "export default {\n"
            "  mixins: [childMixin],\n"
            "  data() { return { y: 2 } }\n"
            "}\n"
        )

        warnings = detect_structural_patterns(
            parent.read_text(), "parentMixin",
            mixin_path=parent, project_root=tmp_path,
        )
        nested = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert nested == [], f"Expected no nested-mixin warning when resolved, got: {nested}"

    def test_nested_warning_when_no_path_context(self):
        """When no path context is provided (can't resolve), the
        structural:nested-mixins warning should still be emitted."""
        source = """
        import childMixin from './childMixin'
        export default {
            mixins: [childMixin],
            data() { return { y: 2 } }
        }
        """
        warnings = detect_structural_patterns(source, "parentMixin")
        nested = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert len(nested) == 1
        assert "childMixin" in nested[0].message

    def test_nested_warning_when_unresolvable(self, tmp_path):
        """When path context is available but ALL nested mixins are
        unresolvable (files not found), the warning should still fire."""
        parent = tmp_path / "parentMixin.js"
        parent.write_text(
            "import ghostMixin from './ghostMixin'\n"
            "export default {\n"
            "  mixins: [ghostMixin],\n"
            "  data() { return { y: 2 } }\n"
            "}\n"
        )

        warnings = detect_structural_patterns(
            parent.read_text(), "parentMixin",
            mixin_path=parent, project_root=tmp_path,
        )
        nested = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert len(nested) == 1
        assert "ghostMixin" in nested[0].message

    def test_mixed_resolved_and_unresolved_keeps_warning_for_unresolved(self, tmp_path):
        """When some nested mixins resolve and some don't, the warning
        should only mention the unresolvable ones."""
        leaf = tmp_path / "realMixin.js"
        leaf.write_text("export default {\n  data() { return { x: 1 } }\n}\n")

        parent = tmp_path / "parentMixin.js"
        parent.write_text(
            "import realMixin from './realMixin'\n"
            "import ghostMixin from './ghostMixin'\n"
            "export default {\n"
            "  mixins: [realMixin, ghostMixin],\n"
            "  data() { return { y: 2 } }\n"
            "}\n"
        )

        warnings = detect_structural_patterns(
            parent.read_text(), "parentMixin",
            mixin_path=parent, project_root=tmp_path,
        )
        nested = [w for w in warnings if w.category == "structural:nested-mixins"]
        assert len(nested) == 1
        assert "ghostMixin" in nested[0].message
        # Resolved mixin should NOT be mentioned in the warning
        assert "realMixin" not in nested[0].message


# ---------------------------------------------------------------------------
# Direct mixin access patterns (this.$options)
# ---------------------------------------------------------------------------

class TestDirectMixinAccessWarnings:
    """Tests for this.$options and this.$options.mixins detection."""

    def test_detects_options_mixins_access(self):
        source = """
export default {
    methods: {
        callMixin() {
            return this.$options.mixins[0].methods.doSomething()
        }
    }
}"""
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        cats = [w.category for w in warnings]
        assert "this.$options.mixins" in cats

    def test_options_mixins_severity_is_error(self):
        source = "this.$options.mixins[0].methods.foo()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        match = [w for w in warnings if w.category == "this.$options.mixins"]
        assert match and match[0].severity == "error"

    def test_detects_general_options_access(self):
        source = """
export default {
    methods: {
        getName() {
            return this.$options.name
        }
    }
}"""
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        cats = [w.category for w in warnings]
        assert "this.$options" in cats

    def test_general_options_severity_is_error(self):
        source = "this.$options.name"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        match = [w for w in warnings if w.category == "this.$options"]
        assert match and match[0].severity == "error"

    def test_options_mixins_does_not_also_trigger_general(self):
        """this.$options.mixins should only trigger the specific warning, not the general one."""
        source = "this.$options.mixins[0].methods.foo()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        cats = [w.category for w in warnings]
        assert "this.$options.mixins" in cats
        assert "this.$options" not in cats

    def test_options_not_caught_by_catchall(self):
        """this.$options should not also trigger the unknown-property catch-all."""
        source = "this.$options.data()"
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        cats = [w.category for w in warnings]
        assert "this.$options" in cats
        # Should not have a "plugin/instance property" catch-all warning for $options
        catchall = [w for w in warnings if "plugin" in w.message.lower() or "instance property" in w.message.lower()]
        assert not catchall


# ---------------------------------------------------------------------------
# Issue 4: this.$watch (and other patterns) should skip comment lines
# ---------------------------------------------------------------------------

class TestWarningSkipsCommentLines:
    """collect_mixin_warnings should not match patterns inside JS comments.
    When the first occurrence of a pattern is in a comment, the tool should
    skip it and use the first real (non-comment) occurrence for source_line."""

    def test_watch_in_comment_skipped_for_source_line(self):
        """If the first this.$watch is in a // comment, source_line should
        point to the real usage, not the comment."""
        source = (
            "// Edge case: this.$watch with ALL variants\n"  # L1 — comment
            "export default {\n"                              # L2
            "  methods: {\n"                                  # L3
            "    setup() {\n"                                 # L4
            "      this.$watch('foo', fn)\n"                  # L5 — real usage
            "    }\n"                                         # L6
            "  }\n"                                           # L7
            "}\n"                                             # L8
        )
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["setup"]), [])
        watch_w = [w for w in warnings if w.category == "this.$watch"]
        assert len(watch_w) == 1
        assert watch_w[0].source_line == 5, (
            f"Expected source_line=5 (real usage), got {watch_w[0].source_line} "
            "(probably matched the comment on L1)"
        )

    def test_emit_in_comment_skipped(self):
        """Same for this.$emit — comments should be skipped."""
        source = (
            "// this.$emit usage below\n"                    # L1 — comment
            "export default {\n"
            "  methods: {\n"
            "    fire() {\n"
            "      this.$emit('done')\n"                     # L5
            "    }\n"
            "  }\n"
            "}\n"
        )
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["fire"]), [])
        emit_w = [w for w in warnings if w.category == "this.$emit"]
        assert len(emit_w) == 1
        assert emit_w[0].source_line == 5

    def test_all_occurrences_in_comments_still_detected(self):
        """If ALL occurrences of a pattern are in comments, the warning should
        still fire (comments may contain real code that was commented out).
        But ideally this is debatable — for now, ensure backward compat."""
        source = (
            "// this.$watch('foo', handler)\n"
            "export default {}\n"
        )
        warnings = collect_mixin_warnings(source, MixinMembers(), [])
        watch_w = [w for w in warnings if w.category == "this.$watch"]
        # Pattern still detected even in comments (backward compat)
        assert len(watch_w) == 1

    def test_watch_multiple_real_occurrences_uses_first(self):
        """When multiple real (non-comment) occurrences exist, source_line
        should point to the first one."""
        source = (
            "export default {\n"                              # L1
            "  methods: {\n"                                  # L2
            "    setup() {\n"                                 # L3
            "      this.$watch('a', fn1)\n"                   # L4
            "      this.$watch('b', fn2)\n"                   # L5
            "    }\n"
            "  }\n"
            "}\n"
        )
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["setup"]), [])
        watch_w = [w for w in warnings if w.category == "this.$watch"]
        assert len(watch_w) == 1
        assert watch_w[0].source_line == 4
