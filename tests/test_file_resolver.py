"""Tests for vue3_migration.core.file_resolver."""
import pytest
from pathlib import Path

from vue3_migration.core.file_resolver import (
    compute_import_path,
    resolve_import_path,
    resolve_mixin_stem,
)

FIXTURES = Path(__file__).parent / "fixtures" / "dummy_project"


# ---------------------------------------------------------------------------
# resolve_mixin_stem
# ---------------------------------------------------------------------------

class TestResolveMixinStem:
    def test_relative_path_no_extension(self):
        assert resolve_mixin_stem('../mixins/selectionMixin') == 'selectionMixin'

    def test_at_alias_no_extension(self):
        assert resolve_mixin_stem('@/mixins/paginationMixin') == 'paginationMixin'

    def test_with_js_extension(self):
        assert resolve_mixin_stem('@/mixins/authMixin.js') == 'authMixin'

    def test_with_ts_extension(self):
        assert resolve_mixin_stem('../mixins/loggingMixin.ts') == 'loggingMixin'

    def test_bare_filename(self):
        assert resolve_mixin_stem('selectionMixin') == 'selectionMixin'

    def test_deeply_nested_path(self):
        assert resolve_mixin_stem('@/src/mixins/nested/filterMixin.js') == 'filterMixin'


# ---------------------------------------------------------------------------
# compute_import_path
# ---------------------------------------------------------------------------

class TestComputeImportPath:
    def test_composable_under_src_uses_at_alias(self):
        composable = FIXTURES / 'src' / 'composables' / 'useSelection.js'
        result = compute_import_path(composable, FIXTURES)
        assert result == '@/composables/useSelection'

    def test_strips_js_extension(self):
        composable = FIXTURES / 'src' / 'composables' / 'usePagination.js'
        result = compute_import_path(composable, FIXTURES)
        assert '.js' not in result

    def test_other_composables(self):
        for name in ('useLogging', 'useItems', 'useAdvancedFilter'):
            composable = FIXTURES / 'src' / 'composables' / f'{name}.js'
            result = compute_import_path(composable, FIXTURES)
            assert result == f'@/composables/{name}'

    def test_prefix_is_at_slash(self):
        composable = FIXTURES / 'src' / 'composables' / 'useSelection.js'
        result = compute_import_path(composable, FIXTURES)
        assert result.startswith('@/')


# ---------------------------------------------------------------------------
# resolve_import_path (requires actual files on disk)
# ---------------------------------------------------------------------------

class TestResolveImportPath:
    def test_relative_path_resolves(self):
        component = FIXTURES / 'src' / 'components' / 'FullyCovered.vue'
        result = resolve_import_path('../mixins/selectionMixin', component)
        assert result is not None
        assert result.name == 'selectionMixin.js'

    def test_at_slash_alias_resolves(self):
        component = FIXTURES / 'src' / 'components' / 'FullyCovered.vue'
        result = resolve_import_path('@/mixins/selectionMixin', component)
        assert result is not None
        assert result.name == 'selectionMixin.js'

    def test_at_alias_without_slash_resolves(self):
        component = FIXTURES / 'src' / 'components' / 'FullyCovered.vue'
        result = resolve_import_path('@mixins/selectionMixin', component)
        assert result is not None
        assert result.name == 'selectionMixin.js'

    def test_nonexistent_path_returns_none(self):
        component = FIXTURES / 'src' / 'components' / 'FullyCovered.vue'
        result = resolve_import_path('@/mixins/doesNotExist', component)
        assert result is None

    def test_resolves_composable_path(self):
        component = FIXTURES / 'src' / 'components' / 'FullyCovered.vue'
        result = resolve_import_path('@/composables/useSelection', component)
        assert result is not None
        assert result.name == 'useSelection.js'
