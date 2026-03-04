"""Tests for vue3_migration.core.composable_search.

Uses the dummy fixture project's composables/ directory for filesystem-based tests.
"""
import pytest
from pathlib import Path

from vue3_migration.core.composable_search import (
    collect_composable_stems,
    find_all_composable_files,
    generate_candidates,
    mixin_has_composable,
    search_for_composable,
)

FIXTURES = Path(__file__).parent / "fixtures" / "dummy_project"
COMPOSABLES_DIR = FIXTURES / "src" / "composables"


# ---------------------------------------------------------------------------
# generate_candidates
# ---------------------------------------------------------------------------

class TestGenerateCandidates:
    def test_selection_mixin(self):
        result = generate_candidates('selectionMixin')
        assert 'useSelection' in result

    def test_pagination_mixin(self):
        result = generate_candidates('paginationMixin')
        assert 'usePagination' in result

    def test_items_mixin(self):
        result = generate_candidates('itemsMixin')
        assert 'useItems' in result

    def test_filter_mixin(self):
        result = generate_candidates('filterMixin')
        assert 'useFilter' in result

    def test_logging_mixin(self):
        result = generate_candidates('loggingMixin')
        assert 'useLogging' in result

    def test_auth_mixin(self):
        result = generate_candidates('authMixin')
        assert 'useAuth' in result

    def test_bare_mixin_suffix_only(self):
        # 'Mixin' alone -> core_name = '' -> no candidates
        result = generate_candidates('Mixin')
        assert result == []

    def test_properties_common_mixin_strips_common(self):
        candidates = generate_candidates('PropertiesCommonMixin')
        assert 'usePropertiesCommon' in candidates
        assert 'useProperties' in candidates

    def test_no_duplicates_in_output(self):
        result = generate_candidates('selectionMixin')
        assert len(result) == len(set(c.lower() for c in result))

    def test_underscore_prefix_stripped(self):
        result = generate_candidates('selection_Mixin')
        assert 'useSelection' in result


# ---------------------------------------------------------------------------
# search_for_composable — exact match (Phase 1)
# ---------------------------------------------------------------------------

class TestSearchForComposableExact:
    def test_selection_mixin_exact(self):
        result = search_for_composable('selectionMixin', [COMPOSABLES_DIR])
        assert any('useSelection' in p.name for p in result)

    def test_pagination_mixin_exact(self):
        result = search_for_composable('paginationMixin', [COMPOSABLES_DIR])
        assert any('usePagination' in p.name for p in result)

    def test_logging_mixin_exact(self):
        result = search_for_composable('loggingMixin', [COMPOSABLES_DIR])
        assert any('useLogging' in p.name for p in result)

    def test_items_mixin_exact(self):
        result = search_for_composable('itemsMixin', [COMPOSABLES_DIR])
        assert any('useItems' in p.name for p in result)

    def test_no_match_for_notification_mixin(self):
        # notificationMixin -> candidates ['useNotification'], no useNotification.js exists -> []
        result = search_for_composable('notificationMixin', [COMPOSABLES_DIR])
        assert result == []

    def test_empty_dirs_list(self):
        result = search_for_composable('selectionMixin', [])
        assert result == []


# ---------------------------------------------------------------------------
# search_for_composable — fuzzy match (Phase 2)
# ---------------------------------------------------------------------------

class TestSearchForComposableFuzzy:
    def test_filter_mixin_fuzzy_match(self):
        # filterMixin -> candidates: ['useFilter'], exact match fails (no useFilter.js)
        # fuzzy: core_word='filter', 'useadvancedfilter' contains 'filter' -> useAdvancedFilter.js
        result = search_for_composable('filterMixin', [COMPOSABLES_DIR])
        assert any('useAdvancedFilter' in p.name for p in result)

    def test_result_paths_are_real_files(self):
        result = search_for_composable('filterMixin', [COMPOSABLES_DIR])
        for p in result:
            assert p.is_file()

    def test_only_js_ts_files_returned(self):
        result = search_for_composable('selectionMixin', [COMPOSABLES_DIR])
        for p in result:
            assert p.suffix in ('.js', '.ts')


# ---------------------------------------------------------------------------
# collect_composable_stems
# ---------------------------------------------------------------------------

class TestCollectComposableStems:
    def test_collects_all_use_files(self):
        stems = collect_composable_stems([COMPOSABLES_DIR])
        assert 'useselection' in stems
        assert 'usepagination' in stems
        assert 'uselogging' in stems
        assert 'useitems' in stems
        assert 'useadvancedfilter' in stems

    def test_stems_are_lowercase(self):
        stems = collect_composable_stems([COMPOSABLES_DIR])
        for s in stems:
            assert s == s.lower()

    def test_empty_dirs(self):
        assert collect_composable_stems([]) == set()


# ---------------------------------------------------------------------------
# mixin_has_composable
# ---------------------------------------------------------------------------

class TestMixinHasComposable:
    def test_true_when_matching_stem_exists(self):
        stems = {'useselection', 'usepagination', 'uselogging', 'useitems'}
        assert mixin_has_composable('selectionMixin', stems) is True

    def test_false_when_no_match(self):
        stems = {'useselection', 'usepagination'}
        assert mixin_has_composable('authMixin', stems) is False

    def test_case_insensitive_matching(self):
        # stem is stored lowercase, candidate lookup is also lowercased
        stems = {'useselection'}
        assert mixin_has_composable('SelectionMixin', stems) is True

    def test_strips_common_suffix(self):
        stems = {'useproperties'}
        assert mixin_has_composable('PropertiesCommonMixin', stems) is True

    def test_bare_mixin_name_returns_false(self):
        stems = {'useselection'}
        assert mixin_has_composable('Mixin', stems) is False

    def test_fuzzy_match_when_exact_missing(self):
        # filterMixin -> exact candidate 'useFilter' not present, but
        # 'useadvancedfilter' contains 'filter' -> should return True
        stems = {'useadvancedfilter', 'useselection'}
        assert mixin_has_composable('filterMixin', stems) is True

    def test_fuzzy_does_not_match_non_use_prefix(self):
        # 'filterhelper' does not start with 'use' -> should not match
        stems = {'filterhelper'}
        assert mixin_has_composable('filterMixin', stems) is False


# ---------------------------------------------------------------------------
# find_all_composable_files
# ---------------------------------------------------------------------------

class TestFindAllComposableFiles:
    def test_finds_composables_in_standard_dir(self, tmp_path):
        comp_dir = tmp_path / "src" / "composables"
        comp_dir.mkdir(parents=True)
        (comp_dir / "useAuth.js").write_text("export function useAuth() {}")
        (comp_dir / "useItems.ts").write_text("export function useItems() {}")

        files = find_all_composable_files(tmp_path)
        names = [f.name for f in files]
        assert "useAuth.js" in names
        assert "useItems.ts" in names

    def test_finds_composables_in_non_standard_dir(self, tmp_path):
        utils_dir = tmp_path / "src" / "utils"
        utils_dir.mkdir(parents=True)
        (utils_dir / "useSearch.js").write_text("export function useSearch() {}")

        files = find_all_composable_files(tmp_path)
        assert any(f.name == "useSearch.js" for f in files)

    def test_skips_non_use_files(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "helpers.js").write_text("export function helper() {}")
        (src / "useValid.js").write_text("export function useValid() {}")

        files = find_all_composable_files(tmp_path)
        names = [f.name for f in files]
        assert "helpers.js" not in names
        assert "useValid.js" in names

    def test_skips_node_modules(self, tmp_path):
        nm = tmp_path / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "useStuff.js").write_text("export function useStuff() {}")

        files = find_all_composable_files(tmp_path)
        assert not any("node_modules" in str(f) for f in files)

    def test_finds_across_multiple_dirs(self, tmp_path):
        (tmp_path / "src" / "hooks").mkdir(parents=True)
        (tmp_path / "src" / "composables").mkdir(parents=True)
        (tmp_path / "src" / "hooks" / "useModal.js").write_text("export function useModal() {}")
        (tmp_path / "src" / "composables" / "useFilter.js").write_text("export function useFilter() {}")

        files = find_all_composable_files(tmp_path)
        names = [f.name for f in files]
        assert "useModal.js" in names
        assert "useFilter.js" in names


# ---------------------------------------------------------------------------
# collect_composable_stems — project_root fallback
# ---------------------------------------------------------------------------

class TestCollectComposableStemsProjectRoot:
    def test_finds_stems_when_no_composable_dir(self, tmp_path):
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "useSearch.js").write_text("export function useSearch() {}")

        stems = collect_composable_stems([], project_root=tmp_path)
        assert "usesearch" in stems

    def test_empty_when_no_composable_dir_and_no_root(self, tmp_path):
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "useSearch.js").write_text("export function useSearch() {}")

        stems = collect_composable_stems([])
        assert stems == set()

    def test_standard_dir_takes_precedence(self, tmp_path):
        comp_dir = tmp_path / "src" / "composables"
        comp_dir.mkdir(parents=True)
        (comp_dir / "useAuth.js").write_text("export function useAuth() {}")

        stems = collect_composable_stems([comp_dir], project_root=tmp_path)
        assert "useauth" in stems


# ---------------------------------------------------------------------------
# search_for_composable — project_root fallback
# ---------------------------------------------------------------------------

class TestSearchForComposableProjectRoot:
    def test_finds_composable_outside_composables_dir(self, tmp_path):
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "useAuth.js").write_text("export function useAuth() {}")

        result = search_for_composable("authMixin", [], project_root=tmp_path)
        assert any(f.name == "useAuth.js" for f in result)

    def test_returns_empty_when_no_match_even_with_root(self, tmp_path):
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "useAuth.js").write_text("export function useAuth() {}")

        result = search_for_composable("notificationMixin", [], project_root=tmp_path)
        assert result == []

    def test_composable_dir_match_takes_priority_over_root_fallback(self, tmp_path):
        comp_dir = tmp_path / "src" / "composables"
        comp_dir.mkdir(parents=True)
        (comp_dir / "useAuth.js").write_text("export function useAuth() {}")
        utils = tmp_path / "src" / "utils"
        utils.mkdir(parents=True)
        (utils / "useAuth.js").write_text("export function useAuth() {}")

        result = search_for_composable("authMixin", [comp_dir], project_root=tmp_path)
        # Should return the composable-dir match, not duplicates
        assert len(result) == 1
        assert "composables" in str(result[0])
