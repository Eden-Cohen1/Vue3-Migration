# tests/test_injector_lifecycle.py
"""Tests for the lifecycle_calls and inline_setup_lines extensions to inject_setup."""
from textwrap import dedent

from vue3_migration.transform.injector import inject_setup, migrate_methods_to_setup, add_vue_import
from vue3_migration.transform.lifecycle_converter import find_lifecycle_referenced_members

COMPONENT = "<script>\nexport default {\n  name: 'Foo',\n}\n</script>"


def test_lifecycle_calls_appended_after_composable_calls():
    result = inject_setup(
        COMPONENT,
        composable_calls=[("useLogging", ["logs", "log"])],
        lifecycle_calls=["    onMounted(() => {\n      log('hi')\n    })"],
    )
    assert "onMounted" in result
    assert result.index("useLogging") < result.index("onMounted")


def test_inline_setup_lines_placed_after_composable_calls():
    result = inject_setup(
        COMPONENT,
        composable_calls=[("useX", ["a"])],
        inline_setup_lines=["    initData()"],
    )
    assert "initData()" in result
    assert result.index("useX") < result.index("initData")


def test_no_regression_without_lifecycle_params():
    result = inject_setup(COMPONENT, [("useX", ["a", "b"])])
    assert "useX" in result
    assert "onMounted" not in result
    assert "initData" not in result


def test_only_lifecycle_no_composable_calls():
    """lifecycle_calls with empty composable_calls still creates setup()."""
    result = inject_setup(
        COMPONENT,
        composable_calls=[],
        lifecycle_calls=["    onMounted(() => { doThing() })"],
    )
    assert "onMounted" in result
    assert "setup()" in result


def test_only_inline_lines_no_composable_calls():
    """inline_setup_lines with empty composable_calls creates setup()."""
    result = inject_setup(
        COMPONENT,
        composable_calls=[],
        inline_setup_lines=["    initData()"],
    )
    assert "initData()" in result
    assert "setup()" in result


def test_created_hook_inlined_after_composable_calls():
    """created() body must appear after the composable destructure that provides its symbols."""
    source = dedent("""\
        <script>
        import loggingMixin from '@/mixins/loggingMixin'

        export default {
          name: 'Test',
          mixins: [loggingMixin],
        }
        </script>
    """)
    result = inject_setup(
        source,
        composable_calls=[("useLogging", ["logs", "log"])],
        inline_setup_lines=["    log('Component created')"],
    )
    log_call_pos = result.index("log('Component created')")
    composable_pos = result.index("const { logs, log } = useLogging()")
    assert composable_pos < log_call_pos, "composable must be called before its members are used"


def test_inject_setup_adds_composable_import():
    """All composables called in setup() must have import statements."""
    source = dedent("""\
        <script>
        import selectionMixin from '@/mixins/selectionMixin'
        import paginationMixin from '@/mixins/paginationMixin'

        export default {
          name: 'Test',
          mixins: [selectionMixin, paginationMixin],
        }
        </script>
    """)
    composable_calls = [
        ("useSelection", "@/composables/useSelection", ["selectedItems"]),
        ("usePagination", "@/composables/usePagination", ["currentPage"]),
    ]
    result = inject_setup(source, composable_calls)
    assert "import { useSelection } from '@/composables/useSelection'" in result
    assert "import { usePagination } from '@/composables/usePagination'" in result


def test_find_lifecycle_referenced_members():
    """Members referenced inside mixin lifecycle hook bodies must be detected."""
    mixin_source = dedent("""\
        export default {
          data() {
            return { isAuthenticated: false, currentUser: null, token: null }
          },
          methods: {
            checkAuth() { /* check stored token */ },
            login(credentials) { /* login logic */ },
            logout() { this.isAuthenticated = false },
          },
          created() {
            this.checkAuth()
          },
        }
    """)
    member_names = ["isAuthenticated", "currentUser", "token", "checkAuth", "login", "logout"]
    referenced = find_lifecycle_referenced_members(mixin_source, ["created"], member_names)
    assert "checkAuth" in referenced
    assert "login" not in referenced  # not referenced in created()


def test_component_methods_moved_to_setup():
    """
    Component-level methods that only reference composable-provided members
    should be moved into setup() and added to the return object.
    """
    source = dedent("""\
        <script>
        export default {
          name: 'Test',
          setup() {
            const { selectItem, log } = useSelection()

            return { selectItem, log }
          },
          methods: {
            handleSelect(item) {
              this.selectItem(item)
              this.log(`Selected: ${item}`)
            },
          },
        }
        </script>
    """)
    composable_members = {"selectItem", "log"}
    ref_members = []  # selectItem and log are methods (plain), not refs
    plain_members = ["selectItem", "log"]
    result = migrate_methods_to_setup(source, composable_members, ref_members, plain_members)
    # The methods: {} block should be removed (or empty)
    assert "methods:" not in result
    # handleSelect should be in setup() as a function
    assert "function handleSelect" in result
    # this.selectItem should be rewritten to selectItem
    assert "this.selectItem" not in result
    assert "this.log" not in result
    # handleSelect should be returned from setup()
    assert "handleSelect" in result


def test_methods_with_unresolved_this_refs_kept():
    """Methods that reference this.* NOT in composable_members stay as methods."""
    source = dedent("""\
        <script>
        export default {
          setup() {
            const { log } = useLogging()
            return { log }
          },
          methods: {
            doSomething() {
              this.log('hello')
              this.$emit('done')
            },
          },
        }
        </script>
    """)
    composable_members = {"log"}
    result = migrate_methods_to_setup(source, composable_members, [], ["log"])
    # Method references this.$emit which is NOT in composable_members, so keep it
    assert "methods:" in result


# --- Bug 3: Vue import consolidation ---

def test_add_vue_import_merges_into_existing():
    content = "<script>\nimport { ref } from 'vue'\nexport default {}\n</script>"
    result = add_vue_import(content, "onMounted")
    assert result.count("from 'vue'") == 1
    assert "ref" in result
    assert "onMounted" in result


def test_add_vue_import_creates_new_if_absent():
    content = "<script>\nexport default {}\n</script>"
    result = add_vue_import(content, "onMounted")
    assert "import { onMounted } from 'vue'" in result


def test_add_vue_import_idempotent():
    content = "<script>\nimport { onMounted } from 'vue'\nexport default {}\n</script>"
    result = add_vue_import(content, "onMounted")
    assert result.count("onMounted") == 1


def test_add_vue_import_multiple_hooks_single_line():
    content = "<script>\nexport default {}\n</script>"
    result = add_vue_import(content, "onMounted")
    result = add_vue_import(result, "onBeforeUnmount")
    result = add_vue_import(result, "onUpdated")
    vue_lines = [l for l in result.splitlines() if "from 'vue'" in l]
    assert len(vue_lines) == 1, f"Expected 1 vue import line, got {len(vue_lines)}: {vue_lines}"
    assert "onMounted" in vue_lines[0]
    assert "onBeforeUnmount" in vue_lines[0]
    assert "onUpdated" in vue_lines[0]
