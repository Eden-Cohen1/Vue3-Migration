"""Tests for vue3_migration.core.mixin_analyzer."""
import pytest

from vue3_migration.core.mixin_analyzer import extract_lifecycle_hooks, extract_mixin_members

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
