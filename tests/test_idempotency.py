# tests/test_idempotency.py
"""End-to-end idempotency tests -- running the tool twice produces identical output."""
from vue3_migration.core.warning_collector import (
    inject_inline_warnings,
    MigrationWarning,
    ConfidenceLevel,
)
from vue3_migration.models import MixinMembers
from vue3_migration.transform.composable_patcher import patch_composable


SAMPLE_COMPOSABLE = (
    "import { ref, computed } from 'vue'\n\n"
    "export function useAuth() {\n"
    "  const user = ref(null)\n"
    "  const isAdmin = computed(() => user.value?.role === 'admin')\n"
    "\n"
    "  function login(creds) {\n"
    "    this.$emit('auth-changed')\n"
    "  }\n"
    "\n"
    "  return { user, isAdmin, login }\n"
    "}\n"
)

SAMPLE_MIXIN = '''
export default {
  data() { return { user: null } },
  computed: { isAdmin() { return this.user?.role === 'admin' } },
  methods: {
    login(creds) { this.$emit('auth-changed') }
  },
  created() { this.checkAuth() },
}
'''

WARNINGS = [
    MigrationWarning(
        mixin_stem="authMixin",
        category="this.$emit",
        message="this.$emit is not available in composables",
        severity="error",
        line_hint="this.$emit('auth-changed')",
        action_required="Accept an emit function parameter or use defineEmits",
    ),
]


def test_inject_warnings_idempotent():
    """inject_inline_warnings called twice produces identical output."""
    first = inject_inline_warnings(
        SAMPLE_COMPOSABLE, WARNINGS,
        confidence=ConfidenceLevel.LOW, warning_count=1,
    )
    second = inject_inline_warnings(
        first, WARNINGS,
        confidence=ConfidenceLevel.LOW, warning_count=1,
    )
    assert first == second, "Second run should produce identical output"


def test_patch_composable_idempotent():
    """patch_composable called twice produces identical output."""
    members = MixinMembers(data=["user"], computed=["isAdmin"], methods=["login", "checkAuth"])
    first = patch_composable(
        SAMPLE_COMPOSABLE, SAMPLE_MIXIN,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["created"],
    )
    second = patch_composable(
        first, SAMPLE_MIXIN,
        not_returned=[], missing=[],
        mixin_members=members,
        lifecycle_hooks=["created"],
    )
    assert first == second, "Second run should produce identical output"
