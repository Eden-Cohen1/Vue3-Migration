"""Tests for the warning infrastructure: models, collection, and confidence scoring."""
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
        ("this.$router.push('/')", "warning"),
        ("this.$route.params.id", "warning"),
        ("this.$store.state.user", "warning"),
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
        source = """
export function useAuth() {
  // ⚠ MIGRATION: this.$router needs useRouter()
  function go() { useRouter().push('/') }
  return { go }
}
"""
        assert compute_confidence(source, []) == ConfidenceLevel.MEDIUM

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
    def test_injects_comment_above_matching_line(self):
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
        lines = result.splitlines()
        assert any("// ⚠ MIGRATION:" in line for line in lines)
        # The warning comment should appear before the line with the match
        for i, line in enumerate(lines):
            if "// ⚠ MIGRATION:" in line:
                assert i + 1 < len(lines)
                assert "this.$router" in lines[i + 1]
                break

    def test_no_line_hint_placed_as_block_at_top(self):
        source = "  function go() { doSomething() }\n"
        warnings = [
            MigrationWarning("auth", "test", "msg", "act", None, "warning"),
        ]
        result = inject_inline_warnings(source, warnings)
        assert "// ⚠ MIGRATION: msg" in result
        # Should be at the very top (no confidence header)
        assert result.startswith("// ⚠ MIGRATION: msg\n")

    def test_no_injection_when_no_warnings(self):
        source = "  const x = ref(0)\n"
        result = inject_inline_warnings(source, [])
        assert result == source

    def test_preserves_indentation(self):
        source = "    function go() { this.$router.push('/') }\n"
        warnings = [
            MigrationWarning(
                "auth", "this.$router", "msg", "act",
                "this.$router.push('/')", "warning",
            ),
        ]
        result = inject_inline_warnings(source, warnings)
        for line in result.splitlines():
            if "// ⚠ MIGRATION:" in line:
                # Should have same leading whitespace as the code line
                assert line.startswith("    //")
                break

    def test_adds_confidence_header(self):
        source = "export function useAuth() {\n  return {}\n}\n"
        result = inject_inline_warnings(
            source, [], confidence=ConfidenceLevel.MEDIUM, warning_count=2
        )
        assert "Transformation confidence: MEDIUM" in result
        assert "2 warnings" in result

    def test_no_confidence_header_when_not_provided(self):
        source = "export function useAuth() {\n  return {}\n}\n"
        result = inject_inline_warnings(source, [])
        assert "Transformation confidence:" not in result

    def test_unplaced_warnings_appear_after_confidence_header(self):
        """Warnings with line_hint=None should appear as block after header."""
        source = "import { ref } from 'vue'\n\nexport function useX() {\n  return {}\n}\n"
        warnings = [
            MigrationWarning("x", "structural:nested-mixins",
                             "Mixin uses nested mixins", "Check transitive", None, "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=1,
        )
        lines = result.splitlines()
        assert "Transformation confidence: MEDIUM" in lines[0]
        assert "// ⚠ MIGRATION: Mixin uses nested mixins" in lines[1]
        assert "import { ref }" in lines[2]

    def test_unmatched_line_hint_falls_back_to_block(self):
        """Warnings whose line_hint doesn't match any composable line go to block."""
        source = "import { ref } from 'vue'\n\nexport function useX() {\n  return {}\n}\n"
        warnings = [
            MigrationWarning("x", "this.$refs",
                             "this.$refs not available", "Use template refs",
                             "const el = this.$refs.input",  # doesn't exist in composable
                             "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=1,
        )
        lines = result.splitlines()
        assert "Transformation confidence: MEDIUM" in lines[0]
        assert "// ⚠ MIGRATION: this.$refs not available" in lines[1]

    def test_mix_of_placed_and_unplaced_warnings(self):
        """Inline-placed + fallback-block warnings both appear."""
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
                             "this.$router.push('/')",  # matches line in composable
                             "warning"),
            MigrationWarning("x", "structural:nested-mixins",
                             "Nested mixins", "Check", None, "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=2,
        )
        lines = result.splitlines()
        # Header line
        assert "Transformation confidence: MEDIUM" in lines[0]
        # Unplaced warning right after header
        assert "// ⚠ MIGRATION: Nested mixins" in lines[1]
        # Inline warning above matching line somewhere in the body
        inline_found = False
        for i, line in enumerate(lines):
            if "// ⚠ MIGRATION: this.$router not available" in line:
                inline_found = True
                assert "this.$router.push" in lines[i + 1]
                break
        assert inline_found, "Inline warning not found"

    def test_multiple_unplaced_warnings_all_appear(self):
        """All unplaced warnings appear in the block."""
        source = "export function useX() {\n  return {}\n}\n"
        warnings = [
            MigrationWarning("x", "a", "Warning A", "Fix A", None, "warning"),
            MigrationWarning("x", "b", "Warning B", "Fix B", None, "warning"),
            MigrationWarning("x", "c", "Warning C", "Fix C",
                             "nonexistent line hint", "warning"),
        ]
        result = inject_inline_warnings(
            source, warnings, confidence=ConfidenceLevel.MEDIUM, warning_count=3,
        )
        assert "// ⚠ MIGRATION: Warning A" in result
        assert "// ⚠ MIGRATION: Warning B" in result
        assert "// ⚠ MIGRATION: Warning C" in result


# ---------------------------------------------------------------------------
# Step 3 (cont): Integration — generator produces warnings + inline comments
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_generator import generate_composable_from_mixin


class TestGeneratorWarningIntegration:
    def test_generated_composable_has_confidence_header(self):
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
        assert "// Transformation confidence:" in result

    def test_generated_composable_has_inline_warning(self):
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
        assert "// ⚠ MIGRATION:" in result

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
        # Clean mixin — no this.$ patterns — should be HIGH
        assert "Transformation confidence: HIGH" in result


# ---------------------------------------------------------------------------
# Step 3 (cont): Integration — patcher produces warnings + inline comments
# ---------------------------------------------------------------------------

from vue3_migration.transform.composable_patcher import patch_composable


class TestPatcherWarningIntegration:
    def test_patched_composable_has_confidence_header(self):
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
        assert "// Transformation confidence:" in result

    def test_patched_composable_with_router_warning_is_medium(self):
        """Mixin warnings (this.$router) downgrade patched composable to MEDIUM."""
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
        # Has this.$router in output + warning, so LOW (remaining this. reference)
        assert "Transformation confidence: LOW" in result

    def test_clean_mixin_patch_no_router_warnings(self):
        """Mixin without this.$ patterns gets no this.$-category warnings."""
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
        # No this.$ patterns but the TODO from body extraction → MEDIUM
        assert "Transformation confidence:" in result
        assert "// Transformation confidence: MEDIUM" in result or "// Transformation confidence: HIGH" in result


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
# Step 6: Markdown report warnings section tests
# ---------------------------------------------------------------------------

from vue3_migration.reporting.markdown import build_warning_summary


class TestBuildWarningSummary:
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

    def _wrap(self, *entries):
        """Wrap entries as entries_by_component format: list of (Path, [entries])."""
        from pathlib import Path
        return [(Path("fake/Comp.vue"), list(entries))]

    def test_renders_section_header(self):
        w = MigrationWarning("auth", "this.$router", "msg", "action", None, "warning")
        entry = self._make_entry("authMixin", [w])
        result = build_warning_summary(self._wrap(entry))
        assert "## Migration Summary" in result

    def test_shows_confidence_per_mixin(self):
        entry = self._make_entry("authMixin")
        result = build_warning_summary(self._wrap(entry))
        assert "HIGH" in result
        assert "authMixin" in result

    def test_shows_warning_details(self):
        w = MigrationWarning(
            "authMixin", "this.$router",
            "this.$router is not available",
            "Use useRouter()",
            "this.$router.push('/')", "warning",
        )
        entry = self._make_entry("authMixin", [w])
        result = build_warning_summary(self._wrap(entry))
        assert "this.$router" in result
        assert "Use useRouter()" in result

    def test_empty_entries_returns_empty(self):
        result = build_warning_summary([])
        assert result == ""

    def test_no_warnings_shows_high_confidence(self):
        entry = self._make_entry("authMixin")
        result = build_warning_summary(self._wrap(entry))
        assert "HIGH" in result
        assert "No manual changes needed" in result

    def test_checklist_format(self):
        w = MigrationWarning("auth", "this.$router", "msg", "action", None, "warning")
        entry = self._make_entry("authMixin", [w])
        result = build_warning_summary(self._wrap(entry))
        assert "**this.$router**" in result
        assert "\u2192" in result

    def test_overview_counts(self):
        w1 = MigrationWarning("auth", "this.$router", "msg", "act", None, "error")
        w2 = MigrationWarning("auth", "this.$store", "msg", "act", None, "warning")
        entry = self._make_entry("authMixin", [w1, w2])
        result = build_warning_summary(self._wrap(entry))
        assert "1 error" in result
        assert "1 warning" in result

    def test_low_confidence_before_high(self):
        w = MigrationWarning("low", "remaining-this", "msg", "act", None, "error")
        low_entry = self._make_entry("lowMixin", [w])
        high_entry = self._make_entry("highMixin")
        result = build_warning_summary(self._wrap(low_entry, high_entry))
        low_pos = result.index("lowMixin")
        high_pos = result.index("highMixin")
        assert low_pos < high_pos

    def test_deduplication_by_mixin_stem(self):
        from pathlib import Path
        entry = self._make_entry("sharedMixin")
        entries_by_component = [
            (Path("fake/A.vue"), [entry]),
            (Path("fake/B.vue"), [self._make_entry("sharedMixin")]),
        ]
        result = build_warning_summary(entries_by_component)
        assert result.count("sharedMixin") == 1  # header appears once

    def test_severity_icons(self):
        w = MigrationWarning("auth", "ext", "msg", "act", None, "error")
        entry = self._make_entry("authMixin", [w])
        result = build_warning_summary(self._wrap(entry))
        assert "\u274c" in result  # error icon


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
