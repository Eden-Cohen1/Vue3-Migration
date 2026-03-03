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

    def test_detects_this_dollar_nextTick(self):
        source = """
        export default {
            methods: {
                update() { this.$nextTick(() => {}) }
            }
        }
        """
        warnings = collect_mixin_warnings(source, MixinMembers(methods=["update"]), [])
        assert any(w.category == "this.$nextTick" for w in warnings)


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

    def test_warnings_downgrade_to_medium(self):
        source = """
export function useAuth() {
  const token = ref(null)
  return { token }
}
"""
        warnings = [MigrationWarning("auth", "this.$emit", "msg", "act", None, "warning")]
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

    def test_no_injection_when_no_line_hint(self):
        source = "  function go() { doSomething() }\n"
        warnings = [
            MigrationWarning("auth", "test", "msg", "act", None, "warning"),
        ]
        result = inject_inline_warnings(source, warnings)
        assert "// ⚠ MIGRATION:" not in result

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
        assert "Migration confidence: MEDIUM" in result
        assert "2 warnings" in result

    def test_no_confidence_header_when_not_provided(self):
        source = "export function useAuth() {\n  return {}\n}\n"
        result = inject_inline_warnings(source, [])
        assert "Migration confidence:" not in result


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
        assert "// Migration confidence:" in result

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
        assert "Migration confidence: HIGH" in result


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
        assert "// Migration confidence:" in result

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
        # Has this.$router warning, so at least MEDIUM
        assert "Migration confidence: MEDIUM" in result

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
        assert "Migration confidence:" in result
        assert "// Migration confidence: MEDIUM" in result or "// Migration confidence: HIGH" in result


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

from vue3_migration.reporting.markdown import build_warnings_section


class TestBuildWarningsSection:
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

    def test_renders_section_header(self):
        w = MigrationWarning("auth", "this.$router", "msg", "action", None, "warning")
        entry = self._make_entry("authMixin", [w])
        result = build_warnings_section(
            [entry], {"authMixin": ConfidenceLevel.MEDIUM}
        )
        assert "## Migration Warnings" in result

    def test_shows_confidence_per_mixin(self):
        entry = self._make_entry("authMixin")
        result = build_warnings_section(
            [entry], {"authMixin": ConfidenceLevel.HIGH}
        )
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
        result = build_warnings_section(
            [entry], {"authMixin": ConfidenceLevel.MEDIUM}
        )
        assert "this.$router" in result
        assert "Use useRouter()" in result

    def test_empty_entries_returns_empty(self):
        result = build_warnings_section([], {})
        assert result == ""

    def test_no_warnings_still_shows_confidence(self):
        entry = self._make_entry("authMixin")
        result = build_warnings_section(
            [entry], {"authMixin": ConfidenceLevel.HIGH}
        )
        assert "HIGH" in result
