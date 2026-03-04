"""Tests for Plan 3: Parser & Extraction Fixes."""

import pytest

from vue3_migration.core.js_parser import extract_value_at
from vue3_migration.transform.composable_patcher import _extract_data_default
from vue3_migration.core.component_analyzer import parse_imports
from vue3_migration.transform.injector import remove_import_line
from vue3_migration.transform.this_rewriter import rewrite_this_refs
from vue3_migration.core.warning_collector import detect_this_aliasing
from vue3_migration.core.mixin_analyzer import extract_mixin_members


# ── Fix 1: extract_value_at() ──────────────────────────────────────────


class TestExtractValueAt:
    """extract_value_at() should extract a full JS value expression
    starting at `pos`, respecting nested brackets/braces and strings."""

    def test_simple_number(self):
        src = "a: 42, b: 1"
        assert extract_value_at(src, 3) == "42"

    def test_simple_string_single(self):
        src = "a: 'hello', b: 1"
        assert extract_value_at(src, 3) == "'hello'"

    def test_simple_string_double(self):
        src = 'a: "hello", b: 1'
        assert extract_value_at(src, 3) == '"hello"'

    def test_string_with_comma(self):
        src = "a: 'hello, world', b: 1"
        assert extract_value_at(src, 3) == "'hello, world'"

    def test_array(self):
        src = "items: [1, 2, 3], b: 1"
        assert extract_value_at(src, 7) == "[1, 2, 3]"

    def test_nested_array(self):
        src = "items: [[1, 2], [3, 4]], b: 1"
        assert extract_value_at(src, 7) == "[[1, 2], [3, 4]]"

    def test_object(self):
        src = "config: { a: 1, b: 2 }, c: 3"
        assert extract_value_at(src, 8) == "{ a: 1, b: 2 }"

    def test_nested_object(self):
        src = "config: { a: { x: 1 }, b: 2 }, c: 3"
        assert extract_value_at(src, 8) == "{ a: { x: 1 }, b: 2 }"

    def test_function_call(self):
        src = "fn: someFunc(1, 2), b: 1"
        assert extract_value_at(src, 4) == "someFunc(1, 2)"

    def test_null_value(self):
        src = "a: null, b: 1"
        assert extract_value_at(src, 3) == "null"

    def test_boolean(self):
        src = "a: true, b: false"
        assert extract_value_at(src, 3) == "true"

    def test_last_property_before_closing_brace(self):
        src = "a: 1, b: [1, 2]}"
        assert extract_value_at(src, 9) == "[1, 2]"

    def test_template_literal_with_comma(self):
        src = "a: `hello, ${x}`, b: 1"
        assert extract_value_at(src, 3) == "`hello, ${x}`"

    def test_string_with_brace(self):
        src = "a: 'hello}world', b: 1"
        assert extract_value_at(src, 3) == "'hello}world'"

    def test_whitespace_trimmed(self):
        src = "a:  42 , b: 1"
        assert extract_value_at(src, 4) == "42"

    def test_multiline_array(self):
        src = "items: [\n  1,\n  2,\n  3\n], b: 1"
        assert extract_value_at(src, 7) == "[\n  1,\n  2,\n  3\n]"


# ── Fix 1b: _extract_data_default() with complex values ───────────────


class TestExtractDataDefault:
    """_extract_data_default() should correctly extract complex default values
    from mixin data() functions using extract_value_at()."""

    def _mixin(self, return_body: str) -> str:
        return f"""export default {{\n  data() {{\n    return {{\n{return_body}\n    }}\n  }}\n}}"""

    def test_array_value(self):
        src = self._mixin("      items: [1, 2, 3],\n      other: true")
        assert _extract_data_default(src, "items") == "[1, 2, 3]"

    def test_object_value(self):
        src = self._mixin("      config: { a: 1, b: 2 },\n      other: true")
        assert _extract_data_default(src, "config") == "{ a: 1, b: 2 }"

    def test_string_with_comma(self):
        src = self._mixin("      label: 'hello, world',\n      other: true")
        assert _extract_data_default(src, "label") == "'hello, world'"

    def test_nested_array(self):
        src = self._mixin("      matrix: [[1, 2], [3, 4]],\n      other: true")
        assert _extract_data_default(src, "matrix") == "[[1, 2], [3, 4]]"

    def test_simple_value_still_works(self):
        src = self._mixin("      count: 0,\n      name: ''")
        assert _extract_data_default(src, "count") == "0"

    def test_null_value(self):
        src = self._mixin("      data: null,\n      other: 1")
        assert _extract_data_default(src, "data") == "null"

    def test_last_property_no_trailing_comma(self):
        src = self._mixin("      items: [1, 2, 3]")
        assert _extract_data_default(src, "items") == "[1, 2, 3]"


# ── Fix 2: Named import parsing ───────────────────────────────────────


class TestParseNamedImports:
    """parse_imports() should handle named imports like
    import { authMixin } from './mixins'."""

    def test_named_import_single(self):
        src = "import { authMixin } from './mixins'"
        result = parse_imports(src)
        assert result == {"authMixin": "./mixins"}

    def test_named_import_multiple(self):
        src = "import { authMixin, dataMixin } from './mixins'"
        result = parse_imports(src)
        assert result["authMixin"] == "./mixins"
        assert result["dataMixin"] == "./mixins"

    def test_named_import_with_alias(self):
        src = "import { Foo as Bar } from './utils'"
        result = parse_imports(src)
        assert result == {"Bar": "./utils"}

    def test_named_and_default_together(self):
        src = (
            "import defaultExport from './default'\n"
            "import { named } from './named'\n"
        )
        result = parse_imports(src)
        assert result["defaultExport"] == "./default"
        assert result["named"] == "./named"

    def test_default_import_still_works(self):
        src = "import authMixin from './mixins/auth'"
        result = parse_imports(src)
        assert result == {"authMixin": "./mixins/auth"}


class TestRemoveNamedImportLine:
    """remove_import_line() should handle named import lines."""

    def test_remove_named_import_line(self):
        content = "import { authMixin } from './mixins/auth'\n\nexport default {}"
        result = remove_import_line(content, "auth")
        assert "import" not in result
        assert "export default {}" in result

    def test_remove_default_import_still_works(self):
        content = "import authMixin from './mixins/auth'\n\nexport default {}"
        result = remove_import_line(content, "auth")
        assert "import" not in result


# ── Fix 3: Bracket notation this['prop'] ──────────────────────────────


class TestBracketNotation:
    """rewrite_this_refs() should handle this['prop'] and this["prop"]
    in addition to this.prop."""

    def test_single_quote_bracket_ref_member(self):
        code = "this['count'] + 1"
        result = rewrite_this_refs(code, ref_members=["count"], plain_members=[])
        assert result == "count.value + 1"

    def test_double_quote_bracket_ref_member(self):
        code = 'this["count"] + 1'
        result = rewrite_this_refs(code, ref_members=["count"], plain_members=[])
        assert result == "count.value + 1"

    def test_bracket_plain_member(self):
        code = "this['doSomething']()"
        result = rewrite_this_refs(code, ref_members=[], plain_members=["doSomething"])
        assert result == "doSomething()"

    def test_bracket_unknown_member_unchanged(self):
        code = "this['unknown']"
        result = rewrite_this_refs(code, ref_members=["count"], plain_members=[])
        assert result == "this['unknown']"

    def test_mixed_dot_and_bracket(self):
        code = "this.count + this['name']"
        result = rewrite_this_refs(code, ref_members=["count", "name"], plain_members=[])
        assert result == "count.value + name.value"

    def test_bracket_in_string_not_rewritten(self):
        code = "const s = \"this['count']\""
        result = rewrite_this_refs(code, ref_members=["count"], plain_members=[])
        assert result == "const s = \"this['count']\""


# ── Fix 4: this aliasing detection ────────────────────────────────────


class TestThisAliasingDetection:
    """detect_this_aliasing() should detect const self = this and similar
    patterns and emit warnings."""

    def test_const_self(self):
        src = "const self = this;\nsetTimeout(() => { self.count++ })"
        warnings = detect_this_aliasing(src, "myMixin")
        assert len(warnings) == 1
        assert "self" in warnings[0].message

    def test_let_that(self):
        src = "let that = this;"
        warnings = detect_this_aliasing(src, "myMixin")
        assert len(warnings) == 1
        assert "that" in warnings[0].message

    def test_var_vm(self):
        src = "var vm = this;"
        warnings = detect_this_aliasing(src, "myMixin")
        assert len(warnings) == 1
        assert "vm" in warnings[0].message

    def test_underscore_this(self):
        src = "const _this = this;"
        warnings = detect_this_aliasing(src, "myMixin")
        assert len(warnings) == 1
        assert "_this" in warnings[0].message

    def test_underscore_self(self):
        src = "const _self = this;"
        warnings = detect_this_aliasing(src, "myMixin")
        assert len(warnings) == 1
        assert "_self" in warnings[0].message

    def test_no_aliasing(self):
        src = "this.count = 1;"
        warnings = detect_this_aliasing(src, "myMixin")
        assert len(warnings) == 0

    def test_warning_category(self):
        src = "const self = this;"
        warnings = detect_this_aliasing(src, "myMixin")
        assert warnings[0].category == "this-alias"
        assert warnings[0].severity == "warning"


# ── Fix 5: TypeScript data() regex ────────────────────────────────────


class TestTypescriptDataRegex:
    """data() with TypeScript return type annotations should still be
    parsed correctly by extract_mixin_members and _extract_data_default."""

    def test_data_with_simple_return_type(self):
        src = """export default {
  data(): DataType {
    return {
      count: 0,
      name: ''
    }
  }
}"""
        members = extract_mixin_members(src)
        assert "count" in members["data"]
        assert "name" in members["data"]

    def test_data_with_generic_return_type(self):
        src = """export default {
  data(): Record<string, unknown> {
    return {
      items: [],
      config: {}
    }
  }
}"""
        members = extract_mixin_members(src)
        assert "items" in members["data"]
        assert "config" in members["data"]

    def test_data_without_return_type_still_works(self):
        src = """export default {
  data() {
    return {
      count: 0
    }
  }
}"""
        members = extract_mixin_members(src)
        assert "count" in members["data"]

    def test_extract_data_default_with_return_type(self):
        src = """export default {
  data(): DataType {
    return {
      items: [1, 2, 3],
      name: 'test'
    }
  }
}"""
        assert _extract_data_default(src, "items") == "[1, 2, 3]"
        assert _extract_data_default(src, "name") == "'test'"
