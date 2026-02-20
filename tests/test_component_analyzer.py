"""Tests for vue3_migration.core.component_analyzer."""
import pytest

from vue3_migration.core.component_analyzer import (
    extract_own_members,
    find_used_members,
    parse_imports,
    parse_mixins_array,
)

# ---------------------------------------------------------------------------
# Fixtures (inline SFC strings)
# ---------------------------------------------------------------------------

SFC_TWO_MIXINS = """\
<script>
import selectionMixin from '@/mixins/selectionMixin'
import paginationMixin from '../mixins/paginationMixin'
import { ref } from 'vue'

export default {
  mixins: [selectionMixin, paginationMixin],
}
</script>
"""

SFC_TEMPLATE_USAGE = """\
<template>
  <div>
    <p>{{ selectionCount }} items selected</p>
    <button @click="clearSelection">Clear</button>
    <span v-if="hasSelection">{{ selectedItems.length }}</span>
  </div>
</template>
<script>
export default {}
</script>
"""

SFC_WITH_OVERRIDES = """\
<script>
export default {
  mixins: [selectionMixin],
  data() {
    return {
      selectionMode: 'multi',
    }
  },
  methods: {
    clearSelection() {
      this.selectedItems = []
      this.$emit('cleared')
    },
  },
}
</script>
"""


# ---------------------------------------------------------------------------
# parse_imports
# ---------------------------------------------------------------------------

class TestParseImports:
    def test_single_default_import(self):
        src = "import selectionMixin from '@/mixins/selectionMixin'"
        result = parse_imports(src)
        assert result == {'selectionMixin': '@/mixins/selectionMixin'}

    def test_relative_import(self):
        src = "import paginationMixin from '../mixins/paginationMixin'"
        result = parse_imports(src)
        assert result == {'paginationMixin': '../mixins/paginationMixin'}

    def test_multiple_imports(self):
        result = parse_imports(SFC_TWO_MIXINS)
        assert 'selectionMixin' in result
        assert result['selectionMixin'] == '@/mixins/selectionMixin'
        assert 'paginationMixin' in result

    def test_named_import_is_ignored(self):
        # import { ref } from 'vue' — not a default import, should not match
        result = parse_imports("import { ref } from 'vue'")
        assert 'ref' not in result

    def test_empty_source(self):
        assert parse_imports('') == {}

    def test_import_with_js_extension(self):
        src = "import authMixin from '@/mixins/authMixin.js'"
        result = parse_imports(src)
        assert result == {'authMixin': '@/mixins/authMixin.js'}


# ---------------------------------------------------------------------------
# parse_mixins_array
# ---------------------------------------------------------------------------

class TestParseMixinsArray:
    def test_single_mixin(self):
        src = 'export default { mixins: [selectionMixin] }'
        assert parse_mixins_array(src) == ['selectionMixin']

    def test_multiple_mixins(self):
        src = 'export default { mixins: [selectionMixin, paginationMixin] }'
        result = parse_mixins_array(src)
        assert result == ['selectionMixin', 'paginationMixin']

    def test_four_mixins(self):
        src = 'mixins: [selectionMixin, paginationMixin, authMixin, loggingMixin]'
        result = parse_mixins_array(src)
        assert len(result) == 4
        assert 'authMixin' in result
        assert 'loggingMixin' in result

    def test_no_mixins_key(self):
        src = 'export default { data() { return {} } }'
        assert parse_mixins_array(src) == []

    def test_whitespace_around_names(self):
        src = 'mixins: [ selectionMixin , paginationMixin ]'
        result = parse_mixins_array(src)
        assert result == ['selectionMixin', 'paginationMixin']

    def test_empty_mixins_array(self):
        src = 'export default { mixins: [] }'
        assert parse_mixins_array(src) == []


# ---------------------------------------------------------------------------
# find_used_members
# ---------------------------------------------------------------------------

class TestFindUsedMembers:
    def test_members_used_in_template(self):
        members = ['selectionCount', 'clearSelection', 'hasSelection', 'selectedItems']
        result = find_used_members(SFC_TEMPLATE_USAGE, members)
        assert 'selectionCount' in result
        assert 'clearSelection' in result
        assert 'hasSelection' in result
        assert 'selectedItems' in result

    def test_members_not_present_are_excluded(self):
        members = ['selectionCount', 'missingMember', 'anotherMissing']
        result = find_used_members(SFC_TEMPLATE_USAGE, members)
        assert 'missingMember' not in result
        assert 'anotherMissing' not in result

    def test_no_partial_word_matches(self):
        # 'selection' should NOT match when the text only contains 'selectionCount'
        src = '<template><p>{{ selectionCount }}</p></template><script></script>'
        result = find_used_members(src, ['selection', 'selectionCount'])
        assert 'selectionCount' in result
        assert 'selection' not in result

    def test_empty_members_list(self):
        result = find_used_members(SFC_TEMPLATE_USAGE, [])
        assert result == []

    def test_raw_js_file_without_sfc_tags(self):
        # For .js files (no <template>/<script> wrappers), searches full source
        src = 'const x = selectionCount + clearSelection()'
        result = find_used_members(src, ['selectionCount', 'clearSelection', 'nope'])
        assert 'selectionCount' in result
        assert 'clearSelection' in result
        assert 'nope' not in result


# ---------------------------------------------------------------------------
# extract_own_members
# ---------------------------------------------------------------------------

class TestExtractOwnMembers:
    def test_finds_data_override(self):
        result = extract_own_members(SFC_WITH_OVERRIDES)
        assert 'selectionMode' in result

    def test_finds_method_override(self):
        result = extract_own_members(SFC_WITH_OVERRIDES)
        assert 'clearSelection' in result

    def test_does_not_include_mixin_inherited_member(self):
        # selectedItems is used INSIDE clearSelection but is not a top-level key
        result = extract_own_members(SFC_WITH_OVERRIDES)
        assert 'selectedItems' not in result

    def test_empty_component(self):
        src = '<script>\nexport default {}\n</script>'
        assert extract_own_members(src) == set()

    def test_computed_section(self):
        src = '<script>\nexport default { computed: { myProp() { return 1 } } }\n</script>'
        result = extract_own_members(src)
        assert 'myProp' in result

    def test_watch_section(self):
        src = '<script>\nexport default { watch: { someVal(v) {} } }\n</script>'
        result = extract_own_members(src)
        assert 'someVal' in result

    def test_multiple_sections(self):
        src = (
            '<script>\nexport default {\n'
            '  data() { return { myData: 1 } },\n'
            '  computed: { myComputed() { return 2 } },\n'
            '  methods: { myMethod() {} },\n'
            '}\n</script>'
        )
        result = extract_own_members(src)
        assert 'myData' in result
        assert 'myComputed' in result
        assert 'myMethod' in result
