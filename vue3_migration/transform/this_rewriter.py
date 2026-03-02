"""Rewrite this.x references in extracted mixin code for Vue 3 composable context."""
import re
from ..core.js_parser import skip_non_code


def _collect_template_literal_spans(
    code: str, start: int, spans: list[tuple[int, int]]
) -> int:
    """Parse a template literal starting at ``start`` (the opening backtick).

    Literal text portions are added to *spans* as non-code.
    ``${…}`` interpolation bodies are left as code so that ``this.*``
    references inside them get rewritten.
    Returns the index after the closing backtick.
    """
    pos = start + 1  # skip opening backtick
    text_start = start  # beginning of current non-code (literal text) region

    while pos < len(code):
        ch = code[pos]
        if ch == "\\":
            pos += 2
            continue
        if code[pos: pos + 2] == "${":
            # Mark everything from text_start through ${ as non-code
            spans.append((text_start, pos + 2))
            pos += 2
            # Process the expression as code until matching }
            depth = 1
            while pos < len(code) and depth > 0:
                new_pos, skipped = skip_non_code(code, pos)
                if skipped:
                    # Strings/comments inside the interpolation are still non-code
                    spans.append((pos, new_pos))
                    pos = new_pos
                    continue
                if code[pos] == "{":
                    depth += 1
                elif code[pos] == "}":
                    depth -= 1
                    if depth == 0:
                        # The closing } starts a new non-code literal text region
                        text_start = pos
                        pos += 1
                        break
                pos += 1
        elif ch == "`":
            # Closing backtick — mark remaining text as non-code
            spans.append((text_start, pos + 1))
            return pos + 1
        else:
            pos += 1

    # Unterminated template literal
    spans.append((text_start, pos))
    return pos


def _collect_non_code_spans(code: str) -> list[tuple[int, int]]:
    """Collect non-code spans with template-literal interpolation awareness."""
    spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(code):
        if code[pos] == "`":
            pos = _collect_template_literal_spans(code, pos, spans)
        else:
            new_pos, skipped = skip_non_code(code, pos)
            if skipped:
                spans.append((pos, new_pos))
                pos = new_pos
            else:
                pos += 1
    return spans


def rewrite_this_refs(
    code: str,
    ref_members: list[str],
    plain_members: list[str],
) -> str:
    """Rewrite this.x references for use in a Vue 3 composable.

    - this.refMember   -> refMember.value   (data, computed, watch)
    - this.plainMember -> plainMember        (methods)
    - this.unknown     -> this.unknown       (best-effort: left unchanged)

    Skips replacements inside strings, comments, regex literals, and
    template literal text.  ``${…}`` interpolation bodies inside template
    literals ARE treated as code and will have this-refs rewritten.

    Args:
        code: JavaScript source fragment to rewrite.
        ref_members: Member names that become ref() values (need .value).
        plain_members: Member names that are plain callables (no .value).

    Returns:
        Rewritten source fragment.
    """
    if not ref_members and not plain_members:
        return code

    # Collect non-code spans [start, end) so we can skip them during substitution
    non_code_spans = _collect_non_code_spans(code)

    # Build combined regex for all known members
    # Longer names first to avoid partial matches (e.g. 'countTotal' before 'count')
    all_ref = sorted(ref_members, key=len, reverse=True)
    all_plain = sorted(plain_members, key=len, reverse=True)
    all_members = all_ref + all_plain

    pattern = re.compile(
        r"\bthis\.(" + "|".join(re.escape(m) for m in all_members) + r")\b"
    )

    ref_set = set(ref_members)
    plain_set = set(plain_members)

    def _replace(m: re.Match) -> str:
        name = m.group(1)
        if name in ref_set:
            return f"{name}.value"
        if name in plain_set:
            return name
        return m.group(0)  # unreachable: regex only matches names from all_members

    # Walk code segments (between non-code spans) applying substitution only on code
    result_parts: list[str] = []
    prev = 0
    for start, end in non_code_spans:
        # Apply substitution to code segment before this non-code span
        result_parts.append(pattern.sub(_replace, code[prev:start]))
        # Preserve non-code verbatim
        result_parts.append(code[start:end])
        prev = end
    # Remaining code after last non-code span
    result_parts.append(pattern.sub(_replace, code[prev:]))

    return "".join(result_parts)
