"""Tests for vue3_migration.transform.this_rewriter."""
from vue3_migration.transform.this_rewriter import rewrite_this_refs

def test_data_member_gets_dot_value():
    result = rewrite_this_refs("return this.count + 1", ref_members=["count"], plain_members=[])
    assert result == "return count.value + 1"

def test_method_has_no_dot_value():
    result = rewrite_this_refs("this.reset()", ref_members=[], plain_members=["reset"])
    assert result == "reset()"

def test_unknown_member_left_unchanged():
    result = rewrite_this_refs("this.unknown", ref_members=[], plain_members=[])
    assert result == "this.unknown"

def test_this_in_string_not_replaced():
    result = rewrite_this_refs(
        'const msg = "this.count is cool"; return this.count',
        ref_members=["count"], plain_members=[]
    )
    assert '"this.count is cool"' in result
    assert "count.value" in result
    assert result.count("count.value") == 1

def test_this_in_line_comment_not_replaced():
    result = rewrite_this_refs(
        "// this.count\nreturn this.count",
        ref_members=["count"], plain_members=[]
    )
    assert "// this.count" in result
    assert result.count("count.value") == 1

def test_multiple_members_same_line():
    result = rewrite_this_refs(
        "if (this.hasItems && this.total > 0) this.clear()",
        ref_members=["hasItems", "total"],
        plain_members=["clear"]
    )
    assert result == "if (hasItems.value && total.value > 0) clear()"

def test_empty_lists_returns_unchanged():
    code = "this.x + this.y()"
    assert rewrite_this_refs(code, [], []) == code


def test_this_in_block_comment_not_replaced():
    result = rewrite_this_refs(
        "/* this.count should be ignored */\nreturn this.count",
        ref_members=["count"], plain_members=[]
    )
    assert "/* this.count should be ignored */" in result
    assert result.count("count.value") == 1


def test_this_in_regex_literal_not_replaced():
    result = rewrite_this_refs(
        r"const r = /this\.count/; return this.count",
        ref_members=["count"], plain_members=[]
    )
    assert r"/this\.count/" in result
    assert result.count("count.value") == 1


def test_prefix_overlap_longer_name_wins():
    result = rewrite_this_refs(
        "this.countTotal + this.count",
        ref_members=["count", "countTotal"],
        plain_members=[]
    )
    assert result == "countTotal.value + count.value"


def test_rewrite_this_in_template_literal_interpolation():
    """this.x inside ${...} in a template literal must be rewritten."""
    code = "const msg = `Selected: ${this.selectedItems.length} items`"
    result = rewrite_this_refs(code, ref_members=["selectedItems"], plain_members=[])
    assert "this.selectedItems" not in result
    assert "selectedItems.value" in result


def test_no_rewrite_in_template_literal_text():
    """Literal text portions of template literals must NOT be rewritten."""
    code = "const msg = `this.count is just text ${this.count} end`"
    result = rewrite_this_refs(code, ref_members=["count"], plain_members=[])
    assert "`this.count is just text ${count.value} end`" in result


def test_nested_template_literal_interpolations():
    """Multiple interpolations in one template literal."""
    code = "`${this.a} and ${this.b}`"
    result = rewrite_this_refs(code, ref_members=["a", "b"], plain_members=[])
    assert "this.a" not in result
    assert "this.b" not in result
    assert "a.value" in result
    assert "b.value" in result


def test_method_call_in_template_literal():
    """Plain member (method) inside template literal interpolation."""
    code = "const msg = `Result: ${this.formatValue(this.total)}`"
    result = rewrite_this_refs(code, ref_members=["total"], plain_members=["formatValue"])
    assert "formatValue(total.value)" in result
    assert "this.formatValue" not in result
    assert "this.total" not in result


# -- Parameter-protection regression tests --

def test_this_ref_in_function_param_not_rewritten():
    """this.x in function parameter position must not be corrupted."""
    code = "function downloadFile(blob, this.exportFileName) { return blob }"
    result = rewrite_this_refs(code, ["exportFileName"], [])
    assert "this.exportFileName" in result  # param preserved
    assert "exportFileName.value" not in result  # NOT rewritten


def test_this_ref_body_rewritten_params_untouched():
    """Body refs rewritten, but param refs left alone."""
    code = "function save(this.name) { this.name = 'test' }"
    result = rewrite_this_refs(code, ["name"], [])
    # param must stay as this.name
    assert result.startswith("function save(this.name)")
    # body must be rewritten
    assert "name.value = 'test'" in result


def test_arrow_function_params_protected():
    """Arrow function params should not be rewritten."""
    code = "(this.x) => { this.x = 1 }"
    result = rewrite_this_refs(code, ["x"], [])
    # param preserved
    assert result.startswith("(this.x) =>")
    # body rewritten
    assert "x.value = 1" in result


def test_method_call_params_not_confused():
    """Regular method call params ARE code, not function declarations."""
    code = "doSomething(this.name, this.count)"
    result = rewrite_this_refs(code, ["name", "count"], [])
    assert "name.value" in result
    assert "count.value" in result
