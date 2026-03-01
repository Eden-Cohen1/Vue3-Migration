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
