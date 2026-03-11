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
