"""Divergence detection between mixin members and composable implementations.

Compares what the generator would produce against what the composable
actually contains, surfacing meaningful logic differences.
"""

import re

from .js_parser import extract_brace_block


def _strip_line_comment(line: str) -> str:
    """Remove // comments from a line, respecting string literals."""
    in_str: str | None = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in ("'", '"', "`"):
            in_str = ch
        elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
            return line[:i]
        i += 1
    return line


def normalize_for_comparison(code: str) -> list[str]:
    """Normalize code for comparison, stripping style noise.

    Returns a list of non-empty normalized lines.
    """
    # Strip block comments (safe — block comments can't appear inside strings)
    text = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)

    lines = []
    for line in text.splitlines():
        # Strip single-line comments, but respect strings (e.g. 'https://...')
        line = _strip_line_comment(line)
        line = line.strip()
        if not line:
            continue
        # Remove trailing semicolons
        line = line.rstrip(";")
        # Collapse whitespace
        line = re.sub(r"\s+", " ", line)
        # Remove trailing commas before } or )
        line = re.sub(r",\s*([}\)])", r" \1", line)
        # Clean up double spaces introduced by the above
        line = re.sub(r"\s+", " ", line)
        # Normalize quotes: double quotes → single (but not template literals with interpolation)
        line = re.sub(r'"([^"]*)"', r"'\1'", line)
        # Backticks without interpolation → single quotes
        if "`" in line and "${" not in line:
            line = re.sub(r"`([^`]*)`", r"'\1'", line)
        # Normalize const/let/var only for ref()/computed()/reactive()/shallowRef()/shallowReactive()/toRef()/toRefs() declarations
        line = re.sub(
            r"\b(let|var)\s+(\w+\s*=\s*(?:ref|computed|reactive|shallowRef|shallowReactive|toRef|toRefs|customRef)\s*\()",
            r"const \2",
            line,
        )
        if line:
            lines.append(line)

    # Collapse single-return computed/arrow blocks to shorthand:
    #   computed(() => { return expr }) → computed(() => expr)
    #   function name() { return expr } → (kept as-is, only computed)
    lines = _collapse_single_return_blocks(lines)

    return lines


def _collapse_single_return_blocks(lines: list[str]) -> list[str]:
    """Collapse multi-line computed blocks with a single return to shorthand.

    Turns:  ['const x = computed(() => {', 'return expr', '})']
    Into:   ['const x = computed(() => expr)']
    """
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Match: const name = computed(() => {
        if (i + 2 < len(lines)
            and re.search(r"computed\s*\(\s*\(\s*\)\s*=>\s*\{\s*$", line)
            and lines[i + 1].strip().startswith("return ")
            and re.match(r"^\}\s*\)", lines[i + 2].strip())):
            expr = lines[i + 1].strip()[len("return "):].rstrip(";").strip()
            # Replace the opening line's block with the expression
            collapsed = re.sub(r"(computed\s*\(\s*\(\s*\)\s*=>\s*)\{.*$", rf"\1{expr})", line)
            result.append(collapsed)
            i += 3
        else:
            result.append(line)
            i += 1
    return result


def extract_composable_member_body(source: str, member_name: str) -> tuple[str, int] | None:
    """Extract the full declaration of a named member from composable source.

    Returns (declaration_text, start_line) where start_line is 1-based,
    or None if the member wasn't found.
    """
    esc = re.escape(member_name)

    def _line_at(offset: int) -> int:
        return source[:offset].count("\n") + 1

    # Pattern 1: function declaration — function name(...) { ... }
    fn_match = re.search(rf"\b(?:async\s+)?function\s+{esc}\s*\(", source)
    if fn_match:
        rest = source[fn_match.start():]
        brace_pos = rest.find("{")
        if brace_pos >= 0:
            abs_brace = fn_match.start() + brace_pos
            inner = extract_brace_block(source, abs_brace)
            text = source[fn_match.start():abs_brace + 1 + len(inner) + 1]
            return text, _line_at(fn_match.start())

    # Pattern 2: const/let/var name = ...
    decl_match = re.search(rf"\b(?:const|let|var)\s+{esc}\s*=\s*", source)
    if decl_match:
        after_eq = source[decl_match.end():]
        start_line = _line_at(decl_match.start())

        # Sub-pattern 2a: arrow function with block body — (...) => { ... }
        arrow_block = re.match(r"(?:async\s+)?\([^)]*\)\s*=>\s*\{", after_eq)
        if arrow_block:
            brace_start = decl_match.end() + after_eq.index("{")
            inner = extract_brace_block(source, brace_start)
            return source[decl_match.start():brace_start + 1 + len(inner) + 1], start_line

        # Sub-pattern 2b: computed/ref/reactive with nested braces
        call_with_brace = re.match(r"\w+\s*\(\s*(?:\([^)]*\)\s*=>\s*)?\{", after_eq)
        if call_with_brace:
            brace_start = decl_match.end() + after_eq.index("{")
            inner = extract_brace_block(source, brace_start)
            end_pos = brace_start + 1 + len(inner) + 1
            while end_pos < len(source) and source[end_pos] in ") \t":
                end_pos += 1
            return source[decl_match.start():end_pos], start_line

        # Sub-pattern 2c: simple single-line expression (ref(x), computed(() => expr), etc.)
        newline_pos = after_eq.find("\n")
        if newline_pos >= 0:
            return source[decl_match.start():decl_match.end() + newline_pos].rstrip(), start_line
        return source[decl_match.start():].rstrip(), start_line

    return None


def _extract_body_content(code: str, kind: str) -> str:
    """Strip declaration wrapper, returning only the body content for comparison.

    - function name(...) { BODY } → BODY
    - const name = ref(VALUE) → VALUE
    - const name = computed(() => EXPR) → EXPR
    - const name = computed(() => { BODY }) → BODY
    """
    # Strip comments line-by-line (using string-aware stripper to preserve code)
    lines = code.strip().splitlines()
    lines = [_strip_line_comment(l) for l in lines]
    stripped = "\n".join(l.rstrip() for l in lines).strip()
    # Also strip block comments
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL).strip()

    if kind == "data":
        # const name = ref(VALUE) → VALUE
        m = re.match(r"(?:const|let|var)\s+\w+\s*=\s*ref\((.+)\)\s*$", stripped, re.DOTALL)
        if m:
            return m.group(1).strip()
        return stripped

    if kind == "computed":
        # Arrow form: const name = computed(() => EXPR) or computed(() => { BODY })
        m = re.search(r"computed\(\s*\(\s*\)\s*=>\s*", stripped)
        if m:
            after_arrow = stripped[m.end():].strip()
            # Block form: { BODY }
            if after_arrow.startswith("{"):
                # Find matching closing brace
                depth = 0
                for i, ch in enumerate(after_arrow):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            body = after_arrow[1:i].strip()
                            break
                else:
                    body = after_arrow[1:].strip()
                if body.startswith("return "):
                    body = body[len("return "):].strip()
                return body
            # Inline form: EXPR) or EXPR (if closing paren was stripped with comment)
            body = after_arrow.rstrip(")").strip()
            return body
        # Object form (getter/setter): const name = computed({ get: ..., set: ... })
        m = re.search(r"computed\(\s*\{", stripped)
        if m:
            after_brace = stripped[m.end()-1:]  # include the {
            depth = 0
            for i, ch in enumerate(after_brace):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return after_brace[1:i].strip()
            return after_brace[1:].strip()
        return stripped

    if kind in ("methods", "watch"):
        # function name(...) { BODY } → BODY (empty body → empty string)
        m = re.search(r"\{(.*)\}\s*$", stripped, re.DOTALL)
        if m:
            return m.group(1).strip()
        # Arrow: const name = (...) => { BODY } → BODY
        m = re.search(r"=>\s*\{(.*)\}\s*$", stripped, re.DOTALL)
        if m:
            return m.group(1).strip()
        return stripped

    return stripped


# ---- Divergence detection ----

# Patterns the tool genuinely cannot auto-convert — lines with these are "manual review".
# Note: this.$t, this.$tc, this.$watch, this.$nextTick, this.$set, this.$delete
# ARE converted by rewrite_this_dollar_refs / rewrite_this_i18n_refs (applied above),
# so they should NOT be listed here.
_NON_CONVERTIBLE_PATTERNS = [
    re.compile(r"this\.\$emit\b"),
    re.compile(r"\bemit\s*\("),
    re.compile(r"this\.\$refs\b"),
    re.compile(r"\$refs\b"),
    re.compile(r"this\.\$router\b"),
    re.compile(r"this\.\$route\b"),
    re.compile(r"this\.\$store\b"),
    re.compile(r"this\.\$"),  # catch-all for any remaining this.$X the rewriters missed
]


def _is_non_convertible(line: str) -> bool:
    """Check if a normalized line contains a non-convertible pattern."""
    return any(p.search(line) for p in _NON_CONVERTIBLE_PATTERNS)


def _determine_mixin_kind(name: str, mixin_members) -> str:
    if name in mixin_members.data:
        return "data"
    if name in mixin_members.computed:
        return "computed"
    if name in mixin_members.methods:
        return "methods"
    if name in mixin_members.watch:
        return "watch"
    return "unknown"


def detect_divergences(
    mixin_source: str,
    composable_source: str,
    mixin_members,
    covered_members: list[str],
    ref_members: list[str],
    plain_members: list[str],
    mixin_line_ranges: dict[str, tuple[int, int]] | None = None,
) -> list:
    """Detect meaningful divergences between mixin members and composable implementations.

    Uses generate_member_declaration() internally to determine IF a member diverges,
    then stores the raw mixin/composable source for presentation.
    """
    from ..models import MemberDivergence
    from ..transform.composable_patcher import generate_member_declaration

    divergences: list[MemberDivergence] = []

    for name in covered_members:
        kind = _determine_mixin_kind(name, mixin_members)
        if kind == "unknown":
            continue

        # Generate what the composable member should look like
        expected_raw = generate_member_declaration(
            name, mixin_source, mixin_members, ref_members, plain_members, indent="",
        )

        # Skip members the generator can't handle
        if "// TODO" in expected_raw or "migrate manually" in expected_raw:
            continue

        # Skip getter/setter computeds — the generator produces a fundamentally
        # different syntax (get: () => {}, set: () => {}) than what humans write
        # (get() {}, set() {}), making comparison unreliable
        if kind == "computed" and "get:" in expected_raw and "set:" in expected_raw:
            continue

        # Extract what the composable actually has
        extraction = extract_composable_member_body(composable_source, name)
        if extraction is None:
            continue
        actual_raw, composable_start_line = extraction

        # Apply this.$ rewriters that generate_member_declaration doesn't run
        from ..transform.this_rewriter import rewrite_this_dollar_refs, rewrite_this_i18n_refs
        expected_raw, _ = rewrite_this_dollar_refs(expected_raw)
        expected_raw, _ = rewrite_this_i18n_refs(expected_raw)

        # Strip declaration wrappers — compare only body content
        expected_body = _extract_body_content(expected_raw, kind)
        actual_body = _extract_body_content(actual_raw, kind)

        # Normalize both sides for comparison
        expected_lines = normalize_for_comparison(expected_body)
        actual_lines = normalize_for_comparison(actual_body)

        # Check if normalized lines differ, ignoring lines the generator
        # couldn't convert (this. references in expected)
        if _lines_match_ignoring_unconverted(expected_lines, actual_lines):
            continue

        # Divergence detected — store raw sources for side-by-side display
        mixin_lines_range = mixin_line_ranges.get(name) if mixin_line_ranges else None
        comp_end_line = composable_start_line + actual_raw.count("\n")

        divergences.append(MemberDivergence(
            member_name=name,
            mixin_kind=kind,
            mixin_source=_extract_raw_mixin_member(mixin_source, name, kind),
            composable_source=actual_raw.strip(),
            mixin_lines=mixin_lines_range,
            composable_lines=(composable_start_line, comp_end_line),
        ))

    return divergences


def _lines_match_ignoring_unconverted(expected: list[str], actual: list[str]) -> bool:
    """Check if expected and actual match, ignoring diffs caused by unconverted this. patterns.

    Uses SequenceMatcher to align lines, then checks if all non-equal opcodes
    are explainable by this. references (i.e., the generator couldn't convert them).
    """
    import difflib
    matcher = difflib.SequenceMatcher(None, expected, actual)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        # Check if ALL expected lines in this opcode have this. (unconverted)
        exp_lines = expected[i1:i2]
        all_expected_unconverted = all("this." in l for l in exp_lines) if exp_lines else False
        if all_expected_unconverted:
            continue  # This diff is just unconverted lines — ignore
        # Real divergence found
        return False
    return True


def _extract_raw_mixin_member(mixin_source: str, name: str, kind: str) -> str:
    """Extract the raw source of a mixin member for display purposes."""
    from ..transform.lifecycle_converter import extract_hook_body

    if kind == "data":
        from ..transform.composable_patcher import _extract_data_default
        default = _extract_data_default(mixin_source, name)
        return f"{name}: {default}"

    body = extract_hook_body(mixin_source, name, exclude_sections=False)
    if body:
        import textwrap
        body_clean = textwrap.dedent(body).strip()
        sig_match = re.search(
            rf"(?:async\s+)?\b{re.escape(name)}\s*\([^)]*\)",
            mixin_source,
        )
        sig = sig_match.group(0) if sig_match else f"{name}()"
        return f"{sig} {{\n{body_clean}\n}}"

    return name


