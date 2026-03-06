"""Tests for vue3_migration.core.mixin_analyzer."""
import pytest

from vue3_migration.core.mixin_analyzer import (
    extract_lifecycle_hooks,
    extract_mixin_members,
    find_external_this_refs,
    resolve_external_dep_sources,
)
from vue3_migration.models import MixinEntry, MixinMembers

# ---------------------------------------------------------------------------
# Inline fixture sources (mirror the dummy project files)
# ---------------------------------------------------------------------------

SELECTION_MIXIN = """\
export default {
  data() {
    return {
      selectedItems: [],
      selectionMode: 'single',
    }
  },
  computed: {
    hasSelection() {
      return this.selectedItems.length > 0
    },
    selectionCount() {
      return this.selectedItems.length
    },
  },
  methods: {
    selectItem(item) {
      this.selectedItems.push(item)
    },
    clearSelection() {
      this.selectedItems = []
    },
    toggleItem(item) {
      const idx = this.selectedItems.indexOf(item)
      if (idx === -1) this.selectedItems.push(item)
      else this.selectedItems.splice(idx, 1)
    },
  },
}
"""

PAGINATION_MIXIN = """\
export default {
  data() {
    return {
      currentPage: 1,
      pageSize: 20,
      totalItems: 0,
    }
  },
  computed: {
    totalPages() {
      return Math.ceil(this.totalItems / this.pageSize)
    },
    hasNextPage() {
      return this.currentPage < this.totalPages
    },
    hasPrevPage() {
      return this.currentPage > 1
    },
  },
  methods: {
    nextPage() {
      if (this.hasNextPage) this.currentPage++
    },
    prevPage() {
      if (this.hasPrevPage) this.currentPage--
    },
    goToPage(page) {
      this.currentPage = page
    },
    resetPagination() {
      this.currentPage = 1
    },
  },
}
"""

LOGGING_MIXIN = """\
export default {
  data() {
    return {
      logs: [],
    }
  },
  methods: {
    log(message) {
      this.logs.push({ message, time: Date.now() })
    },
  },
  created() {
    this.log('Component created')
  },
  mounted() {
    this.log('Component mounted')
  },
  beforeDestroy() {
    this.log('Component will be destroyed')
  },
}
"""

AUTH_MIXIN = """\
export default {
  data() {
    return {
      isAuthenticated: false,
      currentUser: null,
      token: null,
    }
  },
  computed: {
    isAdmin() {
      return this.currentUser?.role === 'admin'
    },
  },
  methods: {
    login(credentials) {},
    logout() {
      this.isAuthenticated = false
    },
    checkAuth() {},
  },
  created() {
    this.checkAuth()
  },
}
"""


# ---------------------------------------------------------------------------
# extract_mixin_members
# ---------------------------------------------------------------------------

class TestExtractMixinMembers:
    def test_selection_mixin_data(self):
        result = extract_mixin_members(SELECTION_MIXIN)
        assert result['data'] == ['selectedItems', 'selectionMode']

    def test_selection_mixin_computed(self):
        result = extract_mixin_members(SELECTION_MIXIN)
        assert 'hasSelection' in result['computed']
        assert 'selectionCount' in result['computed']

    def test_selection_mixin_methods(self):
        result = extract_mixin_members(SELECTION_MIXIN)
        assert 'selectItem' in result['methods']
        assert 'clearSelection' in result['methods']
        assert 'toggleItem' in result['methods']

    def test_no_false_positives_inside_method_bodies(self):
        # push, splice, indexOf are CALLED inside method bodies, not method names
        result = extract_mixin_members(SELECTION_MIXIN)
        assert 'push' not in result['methods']
        assert 'splice' not in result['methods']
        assert 'indexOf' not in result['methods']

    def test_pagination_mixin_data(self):
        result = extract_mixin_members(PAGINATION_MIXIN)
        assert set(result['data']) == {'currentPage', 'pageSize', 'totalItems'}

    def test_pagination_mixin_computed(self):
        result = extract_mixin_members(PAGINATION_MIXIN)
        assert set(result['computed']) == {'totalPages', 'hasNextPage', 'hasPrevPage'}

    def test_pagination_mixin_methods(self):
        result = extract_mixin_members(PAGINATION_MIXIN)
        assert set(result['methods']) == {'nextPage', 'prevPage', 'goToPage', 'resetPagination'}

    def test_logging_mixin_data(self):
        result = extract_mixin_members(LOGGING_MIXIN)
        assert result['data'] == ['logs']

    def test_logging_mixin_methods(self):
        result = extract_mixin_members(LOGGING_MIXIN)
        assert result['methods'] == ['log']
        # Date.now, push should not appear
        assert 'now' not in result['methods']
        assert 'push' not in result['methods']

    def test_no_data_section_returns_empty(self):
        src = 'export default { computed: { foo() { return 1 } } }'
        result = extract_mixin_members(src)
        assert result['data'] == []
        assert 'foo' in result['computed']

    def test_all_keys_present(self):
        result = extract_mixin_members('export default {}')
        assert set(result.keys()) == {'data', 'computed', 'methods', 'watch'}


# ---------------------------------------------------------------------------
# extract_lifecycle_hooks
# ---------------------------------------------------------------------------

class TestExtractLifecycleHooks:
    def test_logging_mixin_hooks(self):
        result = extract_lifecycle_hooks(LOGGING_MIXIN)
        assert 'created' in result
        assert 'mounted' in result
        assert 'beforeDestroy' in result

    def test_auth_mixin_created_hook(self):
        result = extract_lifecycle_hooks(AUTH_MIXIN)
        assert 'created' in result

    def test_no_hooks_in_selection_mixin(self):
        result = extract_lifecycle_hooks(SELECTION_MIXIN)
        assert result == []

    def test_vue3_composition_hooks(self):
        src = 'export default { onMounted() { console.log("hi") } }'
        result = extract_lifecycle_hooks(src)
        assert 'onMounted' in result

    def test_mounted_as_method_value(self):
        # mounted: function() {}  style
        src = 'export default { mounted: function() {} }'
        result = extract_lifecycle_hooks(src)
        assert 'mounted' in result

    def test_does_not_match_partial_names(self):
        # 'createdAt' should NOT match 'created'
        src = 'export default { methods: { createdAt() {} } }'
        result = extract_lifecycle_hooks(src)
        assert 'created' not in result


# ---------------------------------------------------------------------------
# find_external_this_refs tests
# ---------------------------------------------------------------------------

COMMENT_MIXIN_WITH_EXTERNAL = """\
export default {
  data() {
    return {
      comments: [],
      newComment: '',
    }
  },
  methods: {
    loadComments(entityId) {
      this.isLoadingComments = true
    },
    addComment() {
      if (!this.newComment.trim()) return
      this.$emit('comment-added')
    },
  },
  mounted() {
    if (this.entityId) {
      this.loadComments(this.entityId)
    }
  }
}
"""


class TestFindExternalThisRefs:
    def test_finds_external_refs(self):
        own = ["comments", "newComment", "loadComments", "addComment", "isLoadingComments"]
        result = find_external_this_refs(COMMENT_MIXIN_WITH_EXTERNAL, own)
        assert "entityId" in result

    def test_excludes_own_members(self):
        own = ["comments", "newComment", "loadComments", "addComment", "isLoadingComments"]
        result = find_external_this_refs(COMMENT_MIXIN_WITH_EXTERNAL, own)
        assert "comments" not in result
        assert "newComment" not in result
        assert "loadComments" not in result

    def test_excludes_dollar_refs(self):
        own = ["comments", "newComment", "loadComments", "addComment", "isLoadingComments"]
        result = find_external_this_refs(COMMENT_MIXIN_WITH_EXTERNAL, own)
        # this.$emit should not appear as an external dep
        for name in result:
            assert not name.startswith("$")

    def test_no_external_refs(self):
        """Mixin that only references its own members has no external deps."""
        result = find_external_this_refs(SELECTION_MIXIN, [
            "selectedItems", "selectionMode", "hasSelection",
            "selectionCount", "selectItem", "clearSelection", "toggleItem",
        ])
        assert result == []

    def test_skips_refs_in_strings(self):
        code = """
        function foo() {
          console.log("this.externalThing is a string")
          this.ownMethod()
        }
        """
        result = find_external_this_refs(code, ["ownMethod"])
        assert "externalThing" not in result

    def test_skips_refs_in_comments(self):
        code = """
        function foo() {
          // this.externalThing
          this.ownMethod()
        }
        """
        result = find_external_this_refs(code, ["ownMethod"])
        assert "externalThing" not in result

    def test_deduplicates(self):
        code = """
        function foo() {
          this.ext + this.ext + this.ext
        }
        """
        result = find_external_this_refs(code, [])
        assert result == ["ext"]


# ---------------------------------------------------------------------------
# resolve_external_dep_sources tests
# ---------------------------------------------------------------------------

def _make_entry(stem: str, data=None, computed=None, methods=None, watch=None):
    """Create a minimal MixinEntry for testing source resolution."""
    from pathlib import Path
    return MixinEntry(
        local_name=stem,
        mixin_path=Path(f"/fake/{stem}.js"),
        mixin_stem=stem,
        members=MixinMembers(
            data=data or [],
            computed=computed or [],
            methods=methods or [],
            watch=watch or [],
        ),
    )


class TestResolveExternalDepSources:
    def test_found_in_sibling_data(self):
        sibling = _make_entry("loadingMixin", data=["entityId", "isLoading"])
        result = resolve_external_dep_sources(
            ["entityId"], [sibling], set(), "MyComponent",
        )
        assert result["entityId"]["kind"] == "sibling"
        assert "loadingMixin.data" in result["entityId"]["detail"]

    def test_found_in_component(self):
        result = resolve_external_dep_sources(
            ["entityId"], [], {"entityId", "otherProp"}, "TaskDetail",
        )
        assert result["entityId"]["kind"] == "component"
        assert "TaskDetail" in result["entityId"]["detail"]

    def test_found_in_component_with_section(self):
        result = resolve_external_dep_sources(
            ["entityId"], [], {"entityId"}, "TaskDetail",
            component_members_by_section={"data": ["entityId"], "computed": [], "methods": [], "watch": []},
        )
        assert result["entityId"]["kind"] == "component"
        assert result["entityId"]["detail"] == "TaskDetail.data"

    def test_ambiguous_multiple_sources(self):
        sibling = _make_entry("dataMixin", data=["status"])
        result = resolve_external_dep_sources(
            ["status"], [sibling], {"status"}, "MyComponent",
        )
        assert result["status"]["kind"] == "ambiguous"
        assert len(result["status"]["sources"]) == 2

    def test_unknown_source(self):
        result = resolve_external_dep_sources(
            ["mystery"], [], set(), "MyComponent",
        )
        assert result["mystery"]["kind"] == "unknown"

    def test_found_in_sibling_methods(self):
        sibling = _make_entry("authMixin", methods=["checkAuth"])
        result = resolve_external_dep_sources(
            ["checkAuth"], [sibling], set(), "App",
        )
        assert result["checkAuth"]["kind"] == "sibling"
        assert "authMixin.methods" in result["checkAuth"]["detail"]

    def test_multiple_deps_resolved(self):
        sibling = _make_entry("loadingMixin", data=["isLoading"])
        result = resolve_external_dep_sources(
            ["isLoading", "userId"], [sibling], {"userId"}, "Comp",
        )
        assert result["isLoading"]["kind"] == "sibling"
        assert result["userId"]["kind"] == "component"


# ---------------------------------------------------------------------------
# extract_mixin_imports
# ---------------------------------------------------------------------------

from vue3_migration.core.mixin_analyzer import extract_mixin_imports

MIXIN_WITH_IMPORTS = """\
import DefaultExport from '../utils/helpers'
import { namedA, namedB } from '../services/api'
import { original as aliased } from '../lib/transform'
import * as allUtils from '../utils/all'
import '../polyfills/array'
import { ref } from 'vue'

export default {
  methods: {
    doWork() {
      return namedA(DefaultExport.parse(this.data))
    },
  },
}
"""

def test_extract_mixin_imports_default():
    results = extract_mixin_imports(MIXIN_WITH_IMPORTS)
    default_imp = [r for r in results if "DefaultExport" in r["identifiers"]]
    assert len(default_imp) == 1
    assert "import DefaultExport from '../utils/helpers'" in default_imp[0]["line"]

def test_extract_mixin_imports_named():
    results = extract_mixin_imports(MIXIN_WITH_IMPORTS)
    named_imp = [r for r in results if "namedA" in r["identifiers"]]
    assert len(named_imp) == 1
    assert "namedB" in named_imp[0]["identifiers"]

def test_extract_mixin_imports_aliased():
    results = extract_mixin_imports(MIXIN_WITH_IMPORTS)
    aliased_imp = [r for r in results if "aliased" in r["identifiers"]]
    assert len(aliased_imp) == 1
    assert "original" not in aliased_imp[0]["identifiers"]

def test_extract_mixin_imports_namespace():
    results = extract_mixin_imports(MIXIN_WITH_IMPORTS)
    ns_imp = [r for r in results if "allUtils" in r["identifiers"]]
    assert len(ns_imp) == 1

def test_extract_mixin_imports_skips_vue():
    results = extract_mixin_imports(MIXIN_WITH_IMPORTS)
    vue_imp = [r for r in results if any("ref" == id for id in r["identifiers"])]
    assert len(vue_imp) == 0

def test_extract_mixin_imports_skips_side_effect():
    results = extract_mixin_imports(MIXIN_WITH_IMPORTS)
    assert all(r["identifiers"] for r in results)

def test_extract_mixin_imports_empty_source():
    results = extract_mixin_imports("export default { data() { return {} } }")
    assert results == []


# ---------------------------------------------------------------------------
# filter_imports_by_usage
# ---------------------------------------------------------------------------

from vue3_migration.core.mixin_analyzer import filter_imports_by_usage

def test_filter_imports_keeps_used():
    imports = [
        {"line": "import { helperUtil } from '../utils/helpers'", "identifiers": ["helperUtil"]},
        {"line": "import { formatDate } from '../utils/date'", "identifiers": ["formatDate"]},
    ]
    code = "function doWork() { return helperUtil(data.value) }"
    result = filter_imports_by_usage(imports, code)
    assert len(result) == 1
    assert result[0]["identifiers"] == ["helperUtil"]

def test_filter_imports_removes_all_unused():
    imports = [
        {"line": "import { unused } from '../lib'", "identifiers": ["unused"]},
    ]
    code = "function doWork() { return 42 }"
    result = filter_imports_by_usage(imports, code)
    assert result == []

def test_filter_imports_no_partial_word_match():
    imports = [
        {"line": "import { item } from '../lib'", "identifiers": ["item"]},
    ]
    code = "function doWork() { return itemCount.value }"
    result = filter_imports_by_usage(imports, code)
    assert result == []

def test_filter_imports_multi_identifier_any_used():
    """If any identifier from an import line is used, keep the whole line."""
    imports = [
        {"line": "import { a, b } from '../lib'", "identifiers": ["a", "b"]},
    ]
    code = "function doWork() { return a() }"
    result = filter_imports_by_usage(imports, code)
    assert len(result) == 1


# ---------------------------------------------------------------------------
# rewrite_import_path
# ---------------------------------------------------------------------------

from pathlib import Path
from vue3_migration.core.mixin_analyzer import rewrite_import_path

# ── rewrite_import_path ──────────────────────────────────────────────────────

def test_rewrite_same_directory():
    """Mixin and composable at same depth — path unchanged."""
    line = "import { helper } from '../utils/helpers'"
    result = rewrite_import_path(
        line,
        mixin_dir=Path("/project/src/mixins"),
        composable_dir=Path("/project/src/composables"),
    )
    assert result == "import { helper } from '../utils/helpers'"

def test_rewrite_different_depth():
    """Composable is deeper — relative path needs extra ../"""
    line = "import { helper } from '../utils/helpers'"
    result = rewrite_import_path(
        line,
        mixin_dir=Path("/project/src/mixins"),
        composable_dir=Path("/project/src/composables/nested"),
    )
    assert result == "import { helper } from '../../utils/helpers'"

def test_rewrite_composable_shallower():
    """Composable is shallower — shorter relative path."""
    line = "import { helper } from '../../utils/helpers'"
    result = rewrite_import_path(
        line,
        mixin_dir=Path("/project/src/deep/mixins"),
        composable_dir=Path("/project/src/composables"),
    )
    assert result == "import { helper } from '../utils/helpers'"

def test_rewrite_absolute_import_unchanged():
    """Aliased/absolute import paths are not rewritten."""
    line = "import { helper } from '@/utils/helpers'"
    result = rewrite_import_path(
        line,
        mixin_dir=Path("/project/src/mixins"),
        composable_dir=Path("/project/src/composables"),
    )
    assert result == "import { helper } from '@/utils/helpers'"

def test_rewrite_bare_specifier_unchanged():
    """Bare module specifiers (npm packages) are not rewritten."""
    line = "import lodash from 'lodash'"
    result = rewrite_import_path(
        line,
        mixin_dir=Path("/project/src/mixins"),
        composable_dir=Path("/project/src/composables"),
    )
    assert result == "import lodash from 'lodash'"

def test_rewrite_double_quote():
    """Works with double quotes too."""
    line = 'import { helper } from "../utils/helpers"'
    result = rewrite_import_path(
        line,
        mixin_dir=Path("/project/src/mixins"),
        composable_dir=Path("/project/src/composables/nested"),
    )
    assert result == 'import { helper } from "../../utils/helpers"'
