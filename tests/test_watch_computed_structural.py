# tests/test_watch_computed_structural.py
"""Tests for Plan 4: Watch/Computed automation + Structural warnings."""
from vue3_migration.core.mixin_analyzer import extract_mixin_members
from vue3_migration.models import MixinMembers
from vue3_migration.transform.composable_generator import generate_composable_from_mixin
from vue3_migration.transform.composable_patcher import generate_member_declaration


# ── Step 1: Watch member extraction ──────────────────────────────────────────

WATCH_MIXIN = """
export default {
  data() {
    return {
      count: 0,
      items: [],
      query: '',
    }
  },
  watch: {
    count(val, oldVal) {
      console.log('changed', val, oldVal)
    },
    items: function(val) {
      this.processItems(val)
    },
    query: {
      handler(val) {
        this.search(val)
      },
      deep: true
    },
  },
  methods: {
    processItems(val) {},
    search(val) {},
  },
}
"""


def test_extract_mixin_members_includes_watch():
    """extract_mixin_members should return watch handler names."""
    result = extract_mixin_members(WATCH_MIXIN)
    assert "watch" in result
    assert sorted(result["watch"]) == ["count", "items", "query"]


def test_extract_watch_shorthand():
    """Shorthand watch: count(val) { ... } should be extracted."""
    src = """
export default {
  watch: {
    count(val) { console.log(val) },
  },
}
"""
    result = extract_mixin_members(src)
    assert result["watch"] == ["count"]


def test_extract_watch_function_property():
    """Function property watch: items: function(val) { ... } should be extracted."""
    src = """
export default {
  watch: {
    items: function(val) { this.update(val) },
  },
}
"""
    result = extract_mixin_members(src)
    assert result["watch"] == ["items"]


def test_extract_watch_options_object():
    """Options object watch: query: { handler(val) {...}, deep: true } should be extracted."""
    src = """
export default {
  watch: {
    query: {
      handler(val) { this.search(val) },
      deep: true,
    },
  },
}
"""
    result = extract_mixin_members(src)
    assert result["watch"] == ["query"]


def test_extract_watch_empty_when_no_watch_section():
    """No watch section → empty watch list."""
    src = """
export default {
  data() { return { x: 1 } },
  methods: { foo() {} },
}
"""
    result = extract_mixin_members(src)
    assert result["watch"] == []


# ── Step 2: Watch auto-conversion (composable_generator) ─────────────────────

SIMPLE_WATCH_MIXIN = """
export default {
  data() {
    return {
      count: 0,
    }
  },
  watch: {
    count(val, oldVal) {
      console.log('changed', val, oldVal)
    },
  },
}
"""

FUNC_PROP_WATCH_MIXIN = """
export default {
  data() {
    return {
      items: [],
    }
  },
  watch: {
    items: function(val) {
      this.doSomething(val)
    },
  },
  methods: {
    doSomething(val) {},
  },
}
"""

DEEP_WATCH_MIXIN = """
export default {
  data() {
    return {
      query: '',
    }
  },
  watch: {
    query: {
      handler(val) {
        console.log(val)
      },
      deep: true,
    },
  },
}
"""

IMMEDIATE_WATCH_MIXIN = """
export default {
  data() {
    return {
      filter: '',
    }
  },
  watch: {
    filter: {
      handler(val, oldVal) {
        console.log(val, oldVal)
      },
      immediate: true,
    },
  },
}
"""

STRING_HANDLER_WATCH_MIXIN = """
export default {
  data() {
    return { count: 0 }
  },
  watch: {
    count: 'handleCount',
  },
  methods: {
    handleCount() {},
  },
}
"""

QUOTED_KEY_WATCH_MIXIN = """
export default {
  data() {
    return { nested: { path: '' } }
  },
  watch: {
    'nested.path': function(val) {
      console.log(val)
    },
  },
}
"""


def test_watch_shorthand_generates_watch_call():
    """Simple shorthand watch → watch(name, (params) => { body })."""
    members = MixinMembers(data=["count"], watch=["count"])
    result = generate_composable_from_mixin(SIMPLE_WATCH_MIXIN, "testMixin", members, [])
    assert "watch(count" in result
    assert "(val, oldVal) =>" in result
    assert "console.log('changed', val, oldVal)" in result
    # Should NOT contain the old TODO comment
    assert "// watch: count" not in result


def test_watch_func_property_generates_watch_call():
    """Function property watch → watch(name, (params) => { body })."""
    members = MixinMembers(data=["items"], methods=["doSomething"], watch=["items"])
    result = generate_composable_from_mixin(FUNC_PROP_WATCH_MIXIN, "testMixin", members, [])
    assert "watch(items" in result
    assert "(val) =>" in result


def test_watch_deep_option_generates_options_arg():
    """Watch with deep: true → watch(name, handler, { deep: true })."""
    members = MixinMembers(data=["query"], watch=["query"])
    result = generate_composable_from_mixin(DEEP_WATCH_MIXIN, "testMixin", members, [])
    assert "watch(query" in result
    assert "{ deep: true }" in result


def test_watch_immediate_option_generates_options_arg():
    """Watch with immediate: true → watch(name, handler, { immediate: true })."""
    members = MixinMembers(data=["filter"], watch=["filter"])
    result = generate_composable_from_mixin(IMMEDIATE_WATCH_MIXIN, "testMixin", members, [])
    assert "watch(filter" in result
    assert "{ immediate: true }" in result


def test_watch_this_refs_rewritten():
    """this. references in watch handler body should be rewritten."""
    members = MixinMembers(data=["items"], methods=["doSomething"], watch=["items"])
    result = generate_composable_from_mixin(FUNC_PROP_WATCH_MIXIN, "testMixin", members, [])
    # this.doSomething(val) → doSomething(val)
    assert "doSomething(val)" in result
    assert "this.doSomething" not in result.split("//")[0]  # ignore comments


def test_watch_adds_watch_import():
    """Auto-converted watch should add 'watch' to Vue imports."""
    members = MixinMembers(data=["count"], watch=["count"])
    result = generate_composable_from_mixin(SIMPLE_WATCH_MIXIN, "testMixin", members, [])
    assert "watch" in result.split("from 'vue'")[0]


def test_watch_string_handler_auto_converted():
    """String handler watch → auto-converted watch() call, not warning comment."""
    members = MixinMembers(data=["count"], methods=["handleCount"], watch=["count"])
    result = generate_composable_from_mixin(STRING_HANDLER_WATCH_MIXIN, "testMixin", members, [])
    # Should auto-convert string shorthand to watch() call
    assert "watch(count" in result
    assert "handleCount()" in result
    # Should NOT produce a warning
    assert "// watch: count" not in result


def test_watch_quoted_key_extracted():
    """Quoted key watch like 'nested.path' should be extracted by extract_mixin_members."""
    result = extract_mixin_members(QUOTED_KEY_WATCH_MIXIN)
    assert "nested.path" in result["watch"]


def test_watch_dotted_key_generates_getter_function():
    """Dotted watch key → watch(() => nested.value.path, ...)."""
    members = MixinMembers(data=["nested"], watch=["nested.path"])
    result = generate_composable_from_mixin(QUOTED_KEY_WATCH_MIXIN, "testMixin", members, [])
    assert "watch(() => nested.value.path" in result
    assert "(val) =>" in result
    assert "console.log(val)" in result


def test_watch_dotted_key_not_in_return():
    """Dotted watch key should NOT appear in the return statement."""
    members = MixinMembers(data=["nested"], watch=["nested.path"])
    result = generate_composable_from_mixin(QUOTED_KEY_WATCH_MIXIN, "testMixin", members, [])
    # 'nested' should be returned, but 'nested.path' should not
    assert "nested" in result
    # The return statement should not contain 'nested.path'
    import re as _re
    return_m = _re.search(r'return\s*\{([^}]*)\}', result)
    assert return_m is not None
    assert "nested.path" not in return_m.group(1)


# ── Step 2b: Watch auto-conversion (composable_patcher) ──────────────────────

def test_patcher_watch_shorthand_generates_watch_call():
    """generate_member_declaration for watch should produce watch() call."""
    mixin_src = SIMPLE_WATCH_MIXIN
    # In patcher, watch name only in watch list (data is handled separately)
    members = MixinMembers(watch=["count"])
    ref_members = ["count"]
    plain_members: list[str] = []
    result = generate_member_declaration("count", mixin_src, members, ref_members, plain_members)
    assert "watch(count" in result
    assert "// watch: count" not in result


def test_patcher_watch_deep_generates_options():
    """generate_member_declaration for watch with deep generates options."""
    mixin_src = DEEP_WATCH_MIXIN
    members = MixinMembers(watch=["query"])
    ref_members = ["query"]
    plain_members: list[str] = []
    result = generate_member_declaration("query", mixin_src, members, ref_members, plain_members)
    assert "watch(query" in result
    assert "{ deep: true }" in result


# ── Step 3: Getter/setter computed auto-conversion ────────────────────────────

GETTER_SETTER_MIXIN = """
export default {
  data() {
    return {
      first: '',
      last: '',
    }
  },
  computed: {
    fullName: {
      get() { return this.first + ' ' + this.last },
      set(val) { const [f, l] = val.split(' '); this.first = f; this.last = l }
    },
  },
}
"""

GETTER_ONLY_OBJECT_MIXIN = """
export default {
  data() {
    return { firstName: '', lastName: '' }
  },
  computed: {
    name: {
      get() { return this.firstName + ' ' + this.lastName }
    },
  },
}
"""


def test_getter_setter_computed_generates_writable_computed():
    """Getter/setter computed → computed({ get: ..., set: ... })."""
    members = MixinMembers(data=["first", "last"], computed=["fullName"])
    result = generate_composable_from_mixin(GETTER_SETTER_MIXIN, "testMixin", members, [])
    assert "computed({" in result
    assert "get:" in result
    assert "set:" in result
    # Should NOT contain the old TODO comment
    assert "// TODO: getter/setter" not in result


def test_getter_setter_this_refs_rewritten():
    """this. references in both get and set bodies should be rewritten."""
    members = MixinMembers(data=["first", "last"], computed=["fullName"])
    result = generate_composable_from_mixin(GETTER_SETTER_MIXIN, "testMixin", members, [])
    # this.first → first.value, this.last → last.value
    assert "first.value" in result
    assert "last.value" in result


def test_getter_only_object_form():
    """Getter-only object form → computed({ get: ... }) — no set."""
    members = MixinMembers(data=["firstName", "lastName"], computed=["name"])
    result = generate_composable_from_mixin(GETTER_ONLY_OBJECT_MIXIN, "testMixin", members, [])
    assert "computed({" in result
    assert "get:" in result
    # No set function
    lines_with_set = [l for l in result.splitlines() if "set:" in l and not l.strip().startswith("//")]
    assert len(lines_with_set) == 0


def test_patcher_getter_setter_computed():
    """generate_member_declaration for getter/setter computed → computed({ get, set })."""
    members = MixinMembers(data=["first", "last"], computed=["fullName"])
    ref_members = ["first", "last", "fullName"]
    plain_members: list[str] = []
    result = generate_member_declaration("fullName", GETTER_SETTER_MIXIN, members, ref_members, plain_members)
    assert "computed({" in result
    assert "get:" in result
    assert "set:" in result
    assert "// TODO" not in result


# ── Step 4: Structural warning detections ─────────────────────────────────────

from vue3_migration.core.warning_collector import (
    detect_mixin_options,
    detect_structural_patterns,
)


# -- Mixin options detection --

def test_warn_mixin_with_props():
    src = "export default { props: { foo: String }, data() { return {} } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:props" in cats


def test_warn_mixin_with_inject():
    src = "export default { inject: ['store'], data() { return {} } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:inject" in cats


def test_warn_mixin_with_provide():
    src = "export default { provide() { return { foo: this.bar } } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:provide" in cats


def test_warn_mixin_with_filters():
    src = "export default { filters: { capitalize(val) { return val.toUpperCase() } } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:filters" in cats
    # filters are removed in Vue 3 — severity should be "error"
    filters_w = [w for w in warnings if w.category == "mixin-option:filters"][0]
    assert filters_w.severity == "error"


def test_warn_mixin_with_directives():
    src = "export default { directives: { focus: { inserted(el) { el.focus() } } } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:directives" in cats


def test_warn_mixin_with_components():
    src = "export default { components: { MyComp }, data() { return {} } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:components" in cats


def test_warn_mixin_with_extends():
    src = "export default { extends: BaseMixin, data() { return {} } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:extends" in cats


def test_warn_mixin_with_model():
    src = "export default { model: { prop: 'checked', event: 'change' }, data() { return {} } }"
    warnings = detect_mixin_options(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "mixin-option:model" in cats


def test_no_false_positive_option_in_string():
    """Options inside strings should not trigger warnings."""
    src = """export default {
  methods: {
    foo() { console.log('props: are cool') }
  }
}"""
    warnings = detect_mixin_options(src, "testMixin")
    assert len(warnings) == 0


# -- Structural pattern detection --

def test_warn_mixin_factory_function():
    src = "export default function createMixin(options) { return { data() { return {} } } }"
    warnings = detect_structural_patterns(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "structural:factory-function" in cats


def test_warn_nested_mixins():
    src = "export default { mixins: [otherMixin], data() { return {} } }"
    warnings = detect_structural_patterns(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "structural:nested-mixins" in cats


def test_warn_render_in_mixin():
    src = "export default { render(h) { return h('div') } }"
    warnings = detect_structural_patterns(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "structural:render-function" in cats


def test_warn_server_prefetch():
    src = "export default { serverPrefetch() { return this.fetchData() } }"
    warnings = detect_structural_patterns(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "structural:serverPrefetch" in cats


def test_warn_class_component_decorator():
    src = "@Component\nexport default class MyMixin extends Vue { }"
    warnings = detect_structural_patterns(src, "testMixin")
    cats = [w.category for w in warnings]
    assert "structural:class-component" in cats


def test_no_structural_warnings_clean_mixin():
    src = "export default { data() { return { x: 1 } }, methods: { foo() {} } }"
    warnings = detect_structural_patterns(src, "testMixin")
    assert len(warnings) == 0


# ── Step 5: Member name collision detection ───────────────────────────────────

from vue3_migration.core.warning_collector import detect_name_collisions


def test_name_collision_detected():
    """Same member name in two composables → warning."""
    composable_members = {
        "useAuth": ["isAdmin", "currentUser"],
        "usePermissions": ["isAdmin", "canEdit"],
    }
    warnings = detect_name_collisions(composable_members)
    assert len(warnings) == 1
    assert "isAdmin" in warnings[0].message
    assert "useAuth" in warnings[0].message
    assert "usePermissions" in warnings[0].message


def test_no_collision_unique_members():
    """No collisions when all member names are unique."""
    composable_members = {
        "useAuth": ["isAdmin", "currentUser"],
        "useSelection": ["selectedItems", "toggleSelect"],
    }
    warnings = detect_name_collisions(composable_members)
    assert len(warnings) == 0


def test_collision_multiple_overlaps():
    """Multiple collisions produce multiple warnings."""
    composable_members = {
        "useA": ["foo", "bar"],
        "useB": ["foo", "bar", "baz"],
    }
    warnings = detect_name_collisions(composable_members)
    names = [w.message for w in warnings]
    assert any("foo" in n for n in names)
    assert any("bar" in n for n in names)


# ── Phase 3 Regression Tests: Watch conversion bugs ──────────────────────────

from vue3_migration.transform.composable_patcher import (
    parse_watch_entry,
    _extract_watch_section_body,
    patch_composable,
)


def test_parse_watch_string_handler_auto_converted():
    """String shorthand watcher should be auto-converted, not marked complex."""
    mixin_src = """
export default {
  watch: {
    currentTheme: 'applyTheme',
  },
}
"""
    watch_body = _extract_watch_section_body(mixin_src)
    entry = parse_watch_entry(watch_body, "currentTheme")
    assert entry is not None
    assert entry["complex"] is False
    assert "applyTheme" in entry["body"]


def test_parse_watch_handler_function_expression():
    """handler: function(val) {...} should be recognized."""
    mixin_src = """
export default {
  watch: {
    searchQuery: {
      handler: function(newVal) {
        this.performSearch(newVal)
      },
      immediate: true,
    },
  },
}
"""
    watch_body = _extract_watch_section_body(mixin_src)
    entry = parse_watch_entry(watch_body, "searchQuery")
    assert entry is not None
    assert entry["complex"] is False
    assert "newVal" in entry["params"]
    assert "performSearch" in entry["body"]
    assert entry["options"].get("immediate") == "true"


def test_parse_watch_handler_arrow():
    """handler: (val) => {...} should be recognized."""
    mixin_src = """
export default {
  watch: {
    count: {
      handler: (newVal, oldVal) => {
        console.log(newVal)
      },
      deep: true,
    },
  },
}
"""
    watch_body = _extract_watch_section_body(mixin_src)
    entry = parse_watch_entry(watch_body, "count")
    assert entry is not None
    assert entry["complex"] is False
    assert "newVal" in entry["params"]
    assert entry["options"].get("deep") == "true"


def test_watch_import_added_when_patching():
    """Patched composable should have watch in imports when watch calls added."""
    composable_src = """import { ref } from 'vue'

export function useTest() {
  const count = ref(0)

  function onChange() {
    console.log('changed')
  }

  return { count, onChange }
}
"""
    mixin_src = """
export default {
  data() {
    return { count: 0 }
  },
  watch: {
    count(val) {
      console.log(val)
    },
  },
  methods: {
    onChange() {
      console.log('changed')
    },
  },
}
"""
    # count is only in watch (not data) so generate_member_declaration takes the watch path
    mixin_members = MixinMembers(data=[], methods=["onChange"], watch=["count"])
    result = patch_composable(
        composable_content=composable_src,
        mixin_content=mixin_src,
        not_returned=[],
        missing=["count"],  # watch member is missing from composable
        mixin_members=mixin_members,
    )
    # watch should appear in the Vue import line
    import_m = __import__('re').search(r"import\s*\{([^}]*)\}\s*from\s*['\"]vue['\"]", result)
    assert import_m is not None, "Vue import line not found"
    assert "watch" in import_m.group(1)


def test_debounce_this_underscore_rewritten():
    """this._searchTimeout should become a local let variable in generated composable."""
    mixin_src = """
export default {
  data() {
    return { query: '' }
  },
  methods: {
    debouncedSearch(val) {
      clearTimeout(this._searchTimeout)
      this._searchTimeout = setTimeout(() => {
        this.performSearch(val)
      }, 300)
    },
    performSearch(val) {
      console.log('searching', val)
    },
  },
}
"""
    mixin_members = MixinMembers(
        data=["query"],
        methods=["debouncedSearch", "performSearch"],
    )
    result = generate_composable_from_mixin(mixin_src, "searchMixin", mixin_members, [])
    # _searchTimeout should be declared as a let variable
    assert "let _searchTimeout = null" in result
    # this._searchTimeout should be rewritten to _searchTimeout in actual code
    # (warning comments may still reference this._searchTimeout, so only check code lines
    #  and strip inline suffix comments like "// ❌ pass this._searchTimeout as composable param")
    import re as _re
    code_lines = [line for line in result.splitlines() if not line.strip().startswith("//")]
    code_lines = [_re.sub(r"\s+//\s*[\u274c\u26a0\u2139]\ufe0f?.*$", "", l) for l in code_lines]
    code_text = "\n".join(code_lines)
    assert "this._searchTimeout" not in code_text
    assert "_searchTimeout" in result


def test_string_handler_patcher_generates_watch_call():
    """generate_member_declaration for string handler should produce watch() call."""
    mixin_src = STRING_HANDLER_WATCH_MIXIN
    # count only in watch (not data) so generate_member_declaration takes the watch path
    members = MixinMembers(methods=["handleCount"], watch=["count"])
    ref_members = ["count"]
    plain_members = ["handleCount"]
    result = generate_member_declaration("count", mixin_src, members, ref_members, plain_members)
    assert "watch(count" in result
    assert "handleCount()" in result
    assert "migrate manually" not in result


HANDLER_FUNC_EXPR_MIXIN = """
export default {
  data() {
    return { searchQuery: '' }
  },
  watch: {
    searchQuery: {
      handler: function(newVal) {
        this.performSearch(newVal)
      },
      immediate: true,
    },
  },
  methods: {
    performSearch(val) {},
  },
}
"""


def test_handler_func_expr_generates_watch_call():
    """handler: function(val) form should generate watch() call via composable generator."""
    members = MixinMembers(data=["searchQuery"], methods=["performSearch"], watch=["searchQuery"])
    result = generate_composable_from_mixin(HANDLER_FUNC_EXPR_MIXIN, "searchMixin", members, [])
    assert "watch(searchQuery" in result
    assert "{ immediate: true }" in result
    assert "// watch: searchQuery" not in result


# ── Dotted watch key edge cases ───────────────────────────────────────────────

MIXED_WATCH_MIXIN = """
export default {
  data() {
    return {
      count: 0,
      nested: { path: '' },
    }
  },
  watch: {
    count(val) {
      console.log(val)
    },
    'nested.path': function(val) {
      console.log('nested changed', val)
    },
  },
}
"""


def test_mixed_dotted_and_regular_watch_extraction():
    """Both regular and dotted watch keys should be extracted."""
    result = extract_mixin_members(MIXED_WATCH_MIXIN)
    assert "count" in result["watch"]
    assert "nested.path" in result["watch"]


def test_mixed_dotted_and_regular_watch_generation():
    """Both regular and dotted watch keys should generate correct watch calls."""
    members = MixinMembers(data=["count", "nested"], watch=["count", "nested.path"])
    result = generate_composable_from_mixin(MIXED_WATCH_MIXIN, "testMixin", members, [])
    # Regular watch key
    assert "watch(count" in result
    # Dotted watch key with getter
    assert "watch(() => nested.value.path" in result


def test_patcher_dotted_watch_generates_getter():
    """generate_member_declaration for dotted watch key should produce getter form."""
    mixin_src = QUOTED_KEY_WATCH_MIXIN
    members = MixinMembers(data=["nested"], watch=["nested.path"])
    ref_members = ["nested"]
    plain_members: list[str] = []
    result = generate_member_declaration("nested.path", mixin_src, members, ref_members, plain_members)
    assert "watch(() => nested.value.path" in result
    assert "console.log(val)" in result


def test_dotted_watch_double_quoted_key():
    """Double-quoted dotted watch key should also be extracted and converted."""
    src = '''
export default {
  data() {
    return { form: { name: '' } }
  },
  watch: {
    "form.name"(val) {
      console.log(val)
    },
  },
}
'''
    result = extract_mixin_members(src)
    assert "form.name" in result["watch"]

    members = MixinMembers(data=["form"], watch=["form.name"])
    output = generate_composable_from_mixin(src, "testMixin", members, [])
    assert "watch(() => form.value.name" in output
