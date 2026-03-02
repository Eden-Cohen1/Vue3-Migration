# tests/test_injector_lifecycle.py
"""Tests for the lifecycle_calls and inline_setup_lines extensions to inject_setup."""
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


def test_inline_setup_lines_prepended_before_composable_calls():
    result = inject_setup(
        COMPONENT,
        composable_calls=[("useX", ["a"])],
        inline_setup_lines=["    initData()"],
    )
    assert "initData()" in result
    assert result.index("initData") < result.index("useX")


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
