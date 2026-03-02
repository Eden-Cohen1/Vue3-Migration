# tests/test_injector_lifecycle.py
"""Tests for the lifecycle_calls and inline_setup_lines extensions to inject_setup."""
from textwrap import dedent

from vue3_migration.transform.injector import inject_setup

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
