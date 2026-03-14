"""Tests for vue3_migration.core.composable_analyzer."""
import pytest

from vue3_migration.core.composable_analyzer import (
    classify_all_identifier_kinds,
    classify_identifier_kind,
    extract_all_identifiers,
    extract_function_name,
    extract_return_keys,
)

# ---------------------------------------------------------------------------
# Inline fixtures (mirror the dummy project composable files)
# ---------------------------------------------------------------------------

USE_SELECTION = """\
import { ref, computed } from 'vue'

export function useSelection() {
  const selectedItems = ref([])
  const selectionMode = ref('single')

  const hasSelection = computed(() => selectedItems.value.length > 0)
  const selectionCount = computed(() => selectedItems.value.length)

  function selectItem(item) {
    selectedItems.value.push(item)
  }

  function clearSelection() {
    selectedItems.value = []
  }

  function toggleItem(item) {
    const idx = selectedItems.value.indexOf(item)
    if (idx === -1) selectedItems.value.push(item)
    else selectedItems.value.splice(idx, 1)
  }

  return {
    selectedItems,
    selectionMode,
    hasSelection,
    selectionCount,
    selectItem,
    clearSelection,
    toggleItem,
  }
}
"""

# usePagination has resetPagination defined but NOT returned (not_returned scenario)
# hasPrevPage + prevPage are completely absent (missing scenario)
USE_PAGINATION_PARTIAL = """\
import { ref, computed } from 'vue'

export function usePagination() {
  const currentPage = ref(1)
  const pageSize = ref(20)
  const totalItems = ref(0)

  const totalPages = computed(() => Math.ceil(totalItems.value / pageSize.value))
  const hasNextPage = computed(() => currentPage.value < totalPages.value)

  function nextPage() {
    if (hasNextPage.value) currentPage.value++
  }

  function goToPage(page) {
    currentPage.value = page
  }

  function resetPagination() {
    currentPage.value = 1
  }

  return {
    currentPage,
    pageSize,
    totalItems,
    totalPages,
    hasNextPage,
    nextPage,
    goToPage,
  }
}
"""

USE_LOGGING = """\
import { ref } from 'vue'

export function useLogging() {
  const logs = ref([])

  function log(message) {
    logs.value.push({ message, time: Date.now() })
  }

  return {
    logs,
    log,
  }
}
"""

# Composable with a method that returns an object literal BEFORE the main return
USE_TABLE_NESTED_RETURN = """\
import { ref, computed } from 'vue'

export function useTable() {
  const sortField = ref('name')
  const sortDirection = ref('asc')
  const items = ref([])

  const sortedItems = computed(() => {
    return [...items.value].sort((a, b) => {
      const dir = sortDirection.value === 'asc' ? 1 : -1
      return a[sortField.value] > b[sortField.value] ? dir : -dir
    })
  })

  function getColumnClass(col) {
    return {
      sortable: col.sortable,
      sorted: col.field === sortField.value,
    }
  }

  function toggleSort(field) {
    if (sortField.value === field) {
      sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
    } else {
      sortField.value = field
      sortDirection.value = 'asc'
    }
  }

  return {
    sortField,
    sortDirection,
    items,
    sortedItems,
    getColumnClass,
    toggleSort,
  }
}
"""


# ---------------------------------------------------------------------------
# extract_all_identifiers
# ---------------------------------------------------------------------------

class TestExtractAllIdentifiers:
    def test_finds_const_declarations(self):
        result = extract_all_identifiers(USE_SELECTION)
        assert 'selectedItems' in result
        assert 'selectionMode' in result

    def test_finds_computed_consts(self):
        result = extract_all_identifiers(USE_SELECTION)
        assert 'hasSelection' in result
        assert 'selectionCount' in result

    def test_finds_function_declarations(self):
        result = extract_all_identifiers(USE_SELECTION)
        assert 'selectItem' in result
        assert 'clearSelection' in result
        assert 'toggleItem' in result

    def test_finds_unreturned_function(self):
        # resetPagination is defined but NOT in the return statement
        result = extract_all_identifiers(USE_PAGINATION_PARTIAL)
        assert 'resetPagination' in result

    def test_does_not_include_js_keywords(self):
        result = extract_all_identifiers(USE_SELECTION)
        for kw in ('const', 'let', 'var', 'function', 'return', 'if', 'new'):
            assert kw not in result

    def test_destructured_variables(self):
        src = """\
import { ref, computed } from 'vue'
export function useFoo() {
  const { a, b: renamed } = someCall()
  return { a, renamed }
}
"""
        result = extract_all_identifiers(src)
        assert 'a' in result
        assert 'renamed' in result

    def test_nested_return_uses_main_return(self):
        """When a method has its own return {}, identifiers should come from the main return."""
        result = extract_all_identifiers(USE_TABLE_NESTED_RETURN)
        # Main return keys should be found
        for key in ('sortField', 'sortDirection', 'items', 'sortedItems',
                    'getColumnClass', 'toggleSort'):
            assert key in result


# ---------------------------------------------------------------------------
# extract_return_keys
# ---------------------------------------------------------------------------

class TestExtractReturnKeys:
    def test_all_returned_keys_present(self):
        result = extract_return_keys(USE_SELECTION)
        expected = {'selectedItems', 'selectionMode', 'hasSelection', 'selectionCount',
                    'selectItem', 'clearSelection', 'toggleItem'}
        assert expected.issubset(set(result))

    def test_unreturned_function_absent(self):
        # resetPagination is defined but NOT in the return block
        result = extract_return_keys(USE_PAGINATION_PARTIAL)
        assert 'resetPagination' not in result

    def test_missing_members_absent(self):
        # hasPrevPage and prevPage are completely absent from usePagination
        result = extract_return_keys(USE_PAGINATION_PARTIAL)
        assert 'hasPrevPage' not in result
        assert 'prevPage' not in result

    def test_returned_keys_in_partial_composable(self):
        result = extract_return_keys(USE_PAGINATION_PARTIAL)
        for key in ('currentPage', 'pageSize', 'totalItems', 'totalPages',
                    'hasNextPage', 'nextPage', 'goToPage'):
            assert key in result

    def test_no_return_statement(self):
        src = 'export function useFoo() { const x = 1 }'
        assert extract_return_keys(src) == []

    def test_logging_composable(self):
        result = extract_return_keys(USE_LOGGING)
        assert 'logs' in result
        assert 'log' in result

    def test_nested_return_skipped(self):
        """A method's return { sortable, sorted } must not be mistaken for the main return."""
        result = extract_return_keys(USE_TABLE_NESTED_RETURN)
        # Main return keys must be present
        for key in ('sortField', 'sortDirection', 'items', 'sortedItems',
                    'getColumnClass', 'toggleSort'):
            assert key in result, f"Expected '{key}' in return keys"
        # Keys from the nested getColumnClass return must NOT appear
        assert 'sortable' not in result
        assert 'sorted' not in result


# ---------------------------------------------------------------------------
# extract_function_name
# ---------------------------------------------------------------------------

class TestExtractFunctionName:
    def test_export_function(self):
        assert extract_function_name(USE_SELECTION) == 'useSelection'

    def test_export_default_function(self):
        src = 'export default function useFoo() {}'
        assert extract_function_name(src) == 'useFoo'

    def test_export_const_arrow(self):
        src = 'export const useBar = () => {}'
        assert extract_function_name(src) == 'useBar'

    def test_export_default_const(self):
        src = 'export default const useBaz = () => {}'
        assert extract_function_name(src) == 'useBaz'

    def test_no_export(self):
        src = 'function helper() { return 1 }'
        assert extract_function_name(src) is None

    def test_use_pagination(self):
        assert extract_function_name(USE_PAGINATION_PARTIAL) == 'usePagination'

    def test_use_logging(self):
        assert extract_function_name(USE_LOGGING) == 'useLogging'


# ---------------------------------------------------------------------------
# Identifier kind classification
# ---------------------------------------------------------------------------

class TestClassifyIdentifierKind:
    """Tests for identifier kind classification in composable source."""

    def test_ref_declaration(self):
        source = "const isLoading = ref(false)"
        assert classify_identifier_kind("isLoading", source) == "ref"

    def test_shallow_ref(self):
        source = "const items = shallowRef([])"
        assert classify_identifier_kind("items", source) == "ref"

    def test_reactive_declaration(self):
        source = "const state = reactive({})"
        assert classify_identifier_kind("state", source) == "ref"

    def test_to_ref(self):
        source = "const name = toRef(props, 'name')"
        assert classify_identifier_kind("name", source) == "ref"

    def test_computed_declaration(self):
        source = "const fullName = computed(() => first.value + last.value)"
        assert classify_identifier_kind("fullName", source) == "computed"

    def test_function_declaration(self):
        source = "function doStuff() { return 1 }"
        assert classify_identifier_kind("doStuff", source) == "function"

    def test_arrow_function(self):
        source = "const doStuff = () => { return 1 }"
        assert classify_identifier_kind("doStuff", source) == "function"

    def test_async_arrow_function(self):
        source = "const fetchData = async () => { await api.get() }"
        assert classify_identifier_kind("fetchData", source) == "function"

    def test_async_function_declaration(self):
        source = "async function fetchData() { await api.get() }"
        assert classify_identifier_kind("fetchData", source) == "function"

    def test_typed_ref(self):
        source = "const isLoading = ref<boolean>(false)"
        assert classify_identifier_kind("isLoading", source) == "ref"

    def test_typed_computed(self):
        source = "const count = computed<number>(() => items.value.length)"
        assert classify_identifier_kind("count", source) == "computed"

    def test_unknown_declaration(self):
        source = "const result = someHelper()"
        assert classify_identifier_kind("result", source) == "unknown"

    def test_undeclared_name(self):
        source = "const other = ref(0)"
        assert classify_identifier_kind("missing", source) == "unknown"

    def test_let_ref(self):
        source = "let counter = ref(0)"
        assert classify_identifier_kind("counter", source) == "ref"


class TestClassifyAllIdentifierKinds:
    def test_bulk_classification(self):
        source = """
import { ref, computed } from 'vue'

export function useExample() {
  const count = ref(0)
  const doubled = computed(() => count.value * 2)
  function increment() { count.value++ }
  const reset = () => { count.value = 0 }

  return { count, doubled, increment, reset }
}"""
        kinds = classify_all_identifier_kinds(source, ["count", "doubled", "increment", "reset"])
        assert kinds == {
            "count": "ref",
            "doubled": "computed",
            "increment": "function",
            "reset": "function",
        }
