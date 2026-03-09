"""Tests for vue3_migration.core.js_parser — low-level JS parsing helpers."""
import pytest

from vue3_migration.core.js_parser import (
    extract_brace_block,
    extract_property_names,
    extract_value_at,
    is_regex_start,
    skip_regex_literal,
    skip_string,
    strip_comments,
)


# ---------------------------------------------------------------------------
# skip_string
# ---------------------------------------------------------------------------

class TestSkipString:
    def test_double_quoted(self):
        src = '"hello" rest'
        assert skip_string(src, 0) == 7  # past closing "

    def test_single_quoted(self):
        src = "'world' rest"
        assert skip_string(src, 0) == 7

    def test_template_literal(self):
        src = '`${foo}` rest'
        assert skip_string(src, 0) == 8

    def test_escaped_quote_inside(self):
        # "he\"llo" — the \" is escaped, closing " is at index 8
        src = r'"he\"llo" rest'
        assert skip_string(src, 0) == 9

    def test_escaped_backslash(self):
        # "\\" — two chars inside quotes, closing at index 3
        src = r'"\\" x'
        assert skip_string(src, 0) == 4

    def test_empty_string(self):
        src = '""x'
        assert skip_string(src, 0) == 2


# ---------------------------------------------------------------------------
# skip_regex_literal
# ---------------------------------------------------------------------------

class TestSkipRegexLiteral:
    def test_simple_regex(self):
        src = '/foo/ rest'
        # opens at 0, closes at 4, returns 5
        assert skip_regex_literal(src, 0) == 5

    def test_regex_with_flags(self):
        src = '/foo/gi rest'
        assert skip_regex_literal(src, 0) == 7

    def test_regex_with_character_class(self):
        src = '/[a-z]+/ rest'
        assert skip_regex_literal(src, 0) == 8

    def test_regex_escaped_slash(self):
        src = r'/foo\/bar/ rest'
        assert skip_regex_literal(src, 0) == 10

    def test_unterminated_regex_newline(self):
        # Unterminated regex (has newline before closing /)
        src = '/foo\nbar/ rest'
        # Should bail at the newline, returning start+1 = 1
        assert skip_regex_literal(src, 0) == 1


# ---------------------------------------------------------------------------
# is_regex_start
# ---------------------------------------------------------------------------

class TestIsRegexStart:
    def test_at_start_of_string(self):
        assert is_regex_start('/foo/', 0) is True

    def test_after_return_keyword(self):
        src = 'return /foo/'
        assert is_regex_start(src, 7) is True

    def test_after_typeof_keyword(self):
        src = 'typeof /foo/'
        assert is_regex_start(src, 7) is True

    def test_after_equals(self):
        src = 'x = /foo/'
        assert is_regex_start(src, 4) is True

    def test_after_closing_paren(self):
        # fn() /2  — division after a value
        src = 'fn() /2'
        assert is_regex_start(src, 5) is False

    def test_after_closing_bracket(self):
        src = 'arr] /2'
        assert is_regex_start(src, 5) is False

    def test_after_identifier(self):
        # 'value /2' — 'value' is not a regex keyword, so /2 is division
        src = 'value /2'
        assert is_regex_start(src, 6) is False

    def test_after_number(self):
        src = '10 /2'
        assert is_regex_start(src, 3) is False


# ---------------------------------------------------------------------------
# extract_brace_block
# ---------------------------------------------------------------------------

class TestExtractBraceBlock:
    def test_simple_block(self):
        src = '{ a: 1, b: 2 }'
        assert extract_brace_block(src, 0) == ' a: 1, b: 2 '

    def test_nested_braces(self):
        src = '{ outer: { inner: 1 } }'
        result = extract_brace_block(src, 0)
        assert 'inner' in result
        assert 'outer' in result

    def test_string_with_braces_inside(self):
        # Braces inside a string must NOT confuse the depth counter
        src = '{ key: "has {braces} inside" }'
        result = extract_brace_block(src, 0)
        assert 'has {braces} inside' in result

    def test_single_line_comment_with_brace(self):
        src = '{ // { ignored\n key: 1 }'
        result = extract_brace_block(src, 0)
        assert 'key' in result

    def test_block_comment_with_brace(self):
        src = '{ /* { ignored } */ key: 1 }'
        result = extract_brace_block(src, 0)
        assert 'key' in result

    def test_deeply_nested(self):
        src = '{ a: { b: { c: 1 } } }'
        result = extract_brace_block(src, 0)
        assert result.count('{') == 2
        assert result.count('}') == 2


# ---------------------------------------------------------------------------
# extract_property_names
# ---------------------------------------------------------------------------

class TestExtractPropertyNames:
    def test_simple_methods(self):
        body = 'foo() {}, bar() {}, baz() {}'
        assert extract_property_names(body) == ['foo', 'bar', 'baz']

    def test_data_style_properties(self):
        body = "selectedItems: [], selectionMode: 'single',"
        names = extract_property_names(body)
        assert 'selectedItems' in names
        assert 'selectionMode' in names

    def test_no_false_positives_from_nested_calls(self):
        # clearInterval, someCall are INSIDE a method body (depth > 0) — must be skipped
        body = (
            'myMethod() {\n'
            '  clearInterval(this.timer)\n'
            '  someCall()\n'
            '},\n'
            'anotherMethod() {},\n'
        )
        names = extract_property_names(body)
        assert 'myMethod' in names
        assert 'anotherMethod' in names
        assert 'clearInterval' not in names
        assert 'someCall' not in names

    def test_async_method(self):
        body = 'async fetchData() {}, normalMethod() {}'
        names = extract_property_names(body)
        assert 'fetchData' in names
        assert 'normalMethod' in names
        assert 'async' not in names  # 'async' itself should not appear as a name

    def test_deduplication(self):
        # Same key appearing twice should appear once in output
        body = 'foo() {}, foo() {}'
        names = extract_property_names(body)
        assert names.count('foo') == 1

    def test_empty_body(self):
        assert extract_property_names('') == []
        assert extract_property_names('  ') == []


# ---------------------------------------------------------------------------
# extract_value_at — trailing comment stripping
# ---------------------------------------------------------------------------

class TestExtractValueAtComments:
    def test_trailing_single_line_comment_stripped(self):
        src = "0 // default count, unused: true}"
        assert extract_value_at(src, 0) == "0"

    def test_trailing_comment_with_parens(self):
        src = "false // D1: never used by component, next: 1}"
        assert extract_value_at(src, 0) == "false"

    def test_no_comment_unchanged(self):
        src = "'hello', next: 1}"
        assert extract_value_at(src, 0) == "'hello'"

    def test_comment_syntax_inside_string_preserved(self):
        src = "'http://example.com', next: 1}"
        assert extract_value_at(src, 0) == "'http://example.com'"

    def test_array_value_with_trailing_comment(self):
        src = "[] // empty list, next: 1}"
        assert extract_value_at(src, 0) == "[]"

    def test_object_value_with_trailing_comment(self):
        src = "{ a: 1 } // config, next: 1}"
        assert extract_value_at(src, 0) == "{ a: 1 }"


# ---------------------------------------------------------------------------
# strip_comments
# ---------------------------------------------------------------------------

class TestStripComments:
    def test_strip_html_comments(self):
        src = 'before <!-- removed --> after'
        result = strip_comments(src)
        assert 'removed' not in result
        assert 'before' in result
        assert 'after' in result

    def test_strip_js_single_line_comments(self):
        src = 'code\n// removed\nmore code'
        result = strip_comments(src)
        assert 'removed' not in result
        assert 'code' in result
        assert 'more code' in result

    def test_strip_js_block_comments(self):
        src = 'code /* removed */ more'
        result = strip_comments(src)
        assert 'removed' not in result
        assert 'code' in result
        assert 'more' in result

    def test_preserves_strings(self):
        src = '"// not a comment" + \'/* also not */\''
        result = strip_comments(src)
        assert '// not a comment' in result
        assert '/* also not */' in result

    def test_preserves_template_literals(self):
        src = '`<!-- not a comment -->`'
        result = strip_comments(src)
        assert '<!-- not a comment -->' in result

    def test_mixed_comments(self):
        src = (
            'real code\n'
            '// single line comment\n'
            '/* block comment */\n'
            '<!-- html comment -->\n'
            '"// string with comment syntax"\n'
            'more real code'
        )
        result = strip_comments(src)
        assert 'real code' in result
        assert 'more real code' in result
        assert '"// string with comment syntax"' in result
        assert 'single line comment' not in result
        assert 'block comment' not in result
        assert 'html comment' not in result
