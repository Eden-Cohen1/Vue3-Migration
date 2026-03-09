"""
JavaScript parsing helpers for Vue migration tool.

Provides low-level parsing of JS source code: skipping strings, comments,
regex literals, extracting brace-delimited blocks, and extracting top-level
property names from object literals. All functions are comment/string/regex
aware to avoid false matches inside non-code regions.
"""

import re


def skip_string(source: str, start: int) -> int:
    """Skip past a quoted string (handles escaped chars).

    Supports single quotes, double quotes, and template literals.
    Returns the index after the closing quote.
    """
    quote = source[start]
    pos = start + 1
    while pos < len(source):
        if source[pos] == "\\":
            pos += 2
            continue
        if source[pos] == quote:
            return pos + 1
        pos += 1
    return pos


def skip_regex_literal(source: str, start: int) -> int:
    """Skip past a regex literal /pattern/flags.

    Handles escaped characters and character classes ([...]).
    Returns the index after the closing / and any flags.
    """
    pos = start + 1  # skip opening /
    while pos < len(source):
        ch = source[pos]
        if ch == "\\":
            pos += 2  # skip escaped char
            continue
        if ch == "[":
            # Character class -- skip until unescaped ]
            pos += 1
            while pos < len(source):
                if source[pos] == "\\":
                    pos += 2
                    continue
                if source[pos] == "]":
                    break
                pos += 1
        elif ch == "/":
            pos += 1
            # Skip flags (g, i, m, s, u, y, d)
            while pos < len(source) and source[pos].isalpha():
                pos += 1
            return pos
        elif ch == "\n":
            # Unterminated regex -- bail out (not a real regex)
            return start + 1
        pos += 1
    return pos


def is_regex_start(source: str, pos: int) -> bool:
    """Determine if '/' at pos is a regex start (True) or division operator (False).

    Looks at the previous non-whitespace character/word for context.
    Division follows values: ), ], identifiers, digits.
    Regex follows operators, keywords, punctuation, or nothing.
    """
    i = pos - 1
    while i >= 0 and source[i] in " \t":
        i -= 1
    if i < 0:
        return True  # start of string
    prev = source[i]
    # After these, '/' is division (follows a value)
    if prev in ")]}":
        return False
    if prev.isalnum() or prev == "_" or prev == "$":
        # Could be an identifier (division) or a keyword (regex).
        end = i + 1
        while i >= 0 and (source[i].isalnum() or source[i] in "_$"):
            i -= 1
        word = source[i + 1: end]
        # After these keywords, '/' starts a regex
        regex_keywords = {
            "return", "typeof", "instanceof", "in", "delete",
            "void", "throw", "new", "case", "yield", "await",
        }
        return word in regex_keywords
    # After everything else (=, (, [, {, ,, ;, :, !, &, |, ?, ~, +, -, *, <, >, ^, %, newline)
    return True


def skip_non_code(source: str, pos: int) -> tuple[int, bool]:
    """Skip strings, comments, and regex literals at current position.

    Returns (new_pos, did_skip). If did_skip is False, the character at pos
    is actual code and should be processed.
    """
    two = source[pos: pos + 2]
    if two == "//":
        nl = source.find("\n", pos)
        return (nl + 1 if nl != -1 else len(source)), True
    if two == "/*":
        end = source.find("*/", pos + 2)
        return (end + 2 if end != -1 else len(source)), True
    if source[pos] in "\"'`":
        return skip_string(source, pos), True
    if source[pos] == "/" and is_regex_start(source, pos):
        return skip_regex_literal(source, pos), True
    return pos, False


def strip_comments(source: str) -> str:
    """Remove all comments from source while preserving strings and regex literals.

    Strips:
    - HTML comments: <!-- ... -->
    - JS single-line comments: // ... \\n  (preserves the newline)
    - JS multi-line comments: /* ... */

    Preserves:
    - String literals (single, double, template)
    - Regex literals
    """
    result: list[str] = []
    pos = 0
    length = len(source)
    while pos < length:
        # Check for HTML comments first (skip_non_code doesn't handle these)
        if source[pos:pos + 4] == "<!--":
            end = source.find("-->", pos + 4)
            if end != -1:
                pos = end + 3
            else:
                pos = length
            continue

        # Use skip_non_code for JS comments, strings, and regex
        new_pos, skipped = skip_non_code(source, pos)
        if skipped:
            two = source[pos:pos + 2]
            if two == "//":
                # Single-line comment: skip but preserve newline
                result.append("\n")
                pos = new_pos
            elif two == "/*":
                # Block comment: skip entirely
                pos = new_pos
            else:
                # String or regex literal: preserve as-is
                result.append(source[pos:new_pos])
                pos = new_pos
            continue

        result.append(source[pos])
        pos += 1
    return "".join(result)


def _strip_trailing_line_comment(val: str) -> str:
    """Remove a trailing ``// …`` comment from a JS value, respecting strings.

    Walks the value character-by-character using :func:`skip_non_code` so that
    ``//`` inside string literals is left alone.
    """
    i = 0
    while i < len(val):
        new_i, skipped = skip_non_code(val, i)
        if skipped:
            # If skip_non_code jumped past a // comment, everything from i
            # onward is the comment — trim it.
            if val[i:i+2] == "//":
                return val[:i].rstrip()
            i = new_i
            continue
        i += 1
    return val


def extract_value_at(source: str, pos: int) -> str:
    """Extract a full JS value expression starting at pos.

    Walks forward from pos, tracking [], {}, () depth and skipping
    strings/comments. Stops at a , or } only when depth is 0 and not
    inside a string/comment. Returns the extracted value, stripped.
    """
    # Skip leading whitespace
    while pos < len(source) and source[pos] in " \t\n\r":
        pos += 1
    start = pos
    depth = 0
    while pos < len(source):
        new_pos, skipped = skip_non_code(source, pos)
        if skipped:
            pos = new_pos
            continue
        ch = source[pos]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                # Closing brace of the outer object — stop before it
                break
            depth -= 1
        elif ch == "," and depth == 0:
            break
        pos += 1
    val = source[start:pos].strip()
    # Strip trailing single-line comments (// ...) that got captured with the value.
    # E.g. "0 // default count" → "0".  Must not strip inside strings.
    stripped = _strip_trailing_line_comment(val)
    return stripped


def extract_brace_block(source: str, open_brace_pos: int) -> str:
    """Extract content between matching { } braces, skipping strings/comments/regex.

    Args:
        source: The full source text.
        open_brace_pos: Index of the opening '{'.

    Returns:
        The text between the braces (exclusive of the braces themselves).
    """
    depth = 0
    pos = open_brace_pos
    while pos < len(source):
        new_pos, skipped = skip_non_code(source, pos)
        if skipped:
            pos = new_pos
            continue
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace_pos + 1: pos]
        pos += 1
    return source[open_brace_pos + 1:]


def extract_property_names(object_body: str) -> list[str]:
    """Extract top-level property names from a JS object literal body.

    Uses an expect_key flag: only captures identifiers right after a comma
    or at block start. This prevents false positives from nested code
    (e.g., function calls like clearInterval inside method bodies).

    Returns deduplicated list preserving first-occurrence order.
    """
    names = []
    depth = 0
    expect_key = True
    pos = 0
    while pos < len(object_body):
        ch = object_body[pos]
        # Handle quoted string keys at depth 0 before skip_non_code consumes them
        if depth == 0 and expect_key and ch in ("'", '"'):
            end = skip_string(object_body, pos)
            key = object_body[pos + 1: end - 1]  # strip quotes
            rest = object_body[end:].lstrip()
            if rest and rest[0] in (":", "("):
                names.append(key)
                expect_key = False
            pos = end
            continue
        new_pos, skipped = skip_non_code(object_body, pos)
        if skipped:
            pos = new_pos
            continue
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        elif depth == 0 and ch == ",":
            expect_key = True
        elif depth == 0 and expect_key and (ch.isalpha() or ch in "_$"):
            match = re.match(r"(?:async\s+)?(\w+)", object_body[pos:])
            if match:
                names.append(match.group(1))
                expect_key = False
                pos += match.end() - 1
        pos += 1
    return list(dict.fromkeys(names))
