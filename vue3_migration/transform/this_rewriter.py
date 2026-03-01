"""Rewrite this.x references in extracted mixin code for Vue 3 composable context."""
import re
from ..core.js_parser import skip_non_code


def rewrite_this_refs(
    code: str,
    ref_members: list[str],
    plain_members: list[str],
) -> str:
    """Rewrite this.x references for use in a Vue 3 composable.

    - this.refMember   -> refMember.value   (data, computed, watch)
    - this.plainMember -> plainMember        (methods)
    - this.unknown     -> this.unknown       (best-effort: left unchanged)

    Skips replacements inside strings, template literals, comments, and regexes.
    Template literal ${ } interpolations are treated as opaque strings by
    skip_non_code and will NOT have this-refs rewritten (known limitation).

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
    non_code_spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(code):
        new_pos, skipped = skip_non_code(code, pos)
        if skipped:
            non_code_spans.append((pos, new_pos))
            pos = new_pos
        else:
            pos += 1

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
