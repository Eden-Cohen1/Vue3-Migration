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


def _collect_param_spans(
    code: str, non_code_spans: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    """Identify character spans of function/method/arrow parameter lists.

    Returns a list of ``(start, end)`` tuples where *start* is the index of the
    opening ``(`` and *end* is one past the closing ``)`` for each parameter
    list that belongs to a function declaration or arrow function expression.

    Regular call-site parentheses (``doSomething(…)``, ``if(…)``, etc.) are NOT
    included — only actual parameter *definition* sites.
    """

    def _in_non_code(pos: int) -> bool:
        return any(s <= pos < e for s, e in non_code_spans)

    # --- Patterns that introduce function parameter lists ---
    # 1. `function NAME(` / `function(` / `async function NAME(` / `async function(`
    func_kw_re = re.compile(r'\bfunction\s*(?:\w+\s*)?\(')
    # 2. Arrow params: `(params) =>` — we handle this by scanning for `=>` and
    #    looking backwards for a matching `(…)`.
    # 3. Method shorthand in object literal: `name(` when preceded by identifier
    #    at start-of-statement position — hard to detect perfectly.  We limit
    #    ourselves to patterns (1) and (2) plus a heuristic for (3).

    spans: list[tuple[int, int]] = []

    # ---- Pass 1: `function …(` keyword matches ----
    for m in func_kw_re.finditer(code):
        if _in_non_code(m.start()):
            continue
        # The match ends right after '(' — we need to find the matching ')'
        open_paren = m.end() - 1  # index of '('
        depth = 1
        pos = m.end()
        while pos < len(code) and depth > 0:
            if _in_non_code(pos):
                # skip to end of non-code span
                for s, e in non_code_spans:
                    if s <= pos < e:
                        pos = e
                        break
                continue
            if code[pos] == '(':
                depth += 1
            elif code[pos] == ')':
                depth -= 1
            pos += 1
        # span covers from '(' to just after ')'
        spans.append((open_paren, pos))

    # ---- Pass 2: arrow function parameter lists `(…) =>` ----
    arrow_re = re.compile(r'=>')
    for m in arrow_re.finditer(code):
        if _in_non_code(m.start()):
            continue
        # Walk backwards from `=>` skipping whitespace to find `)`
        i = m.start() - 1
        while i >= 0 and code[i] in ' \t\n\r':
            i -= 1
        if i < 0 or code[i] != ')':
            continue
        # Now find the matching '(' by walking backwards tracking depth
        close_paren = i
        depth = 1
        i -= 1
        while i >= 0 and depth > 0:
            if _in_non_code(i):
                i -= 1
                continue
            if code[i] == ')':
                depth += 1
            elif code[i] == '(':
                depth -= 1
            i -= 1
        open_paren = i + 1
        # Make sure this isn't already captured by a `function` keyword match
        # and that what precedes the `(` is not a call-site identifier
        # Check if there's a `function` keyword just before — already handled
        pre = open_paren - 1
        while pre >= 0 and code[pre] in ' \t\n\r':
            pre -= 1
        if pre >= 0 and (code[pre].isalnum() or code[pre] in '_$'):
            # Could be `name(…) =>` — method/variable, still a param list
            # But make sure it's not something like `if(…) =>` which is invalid
            # anyway.  We include it as a param span.
            pass
        span = (open_paren, close_paren + 1)
        # Avoid duplicate with function keyword spans
        if span not in spans:
            spans.append(span)

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

    # Collect function parameter list spans so we can protect them
    param_spans = _collect_param_spans(code, non_code_spans)

    def _in_param_span(abs_pos: int) -> bool:
        return any(s <= abs_pos < e for s, e in param_spans)

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

    # Track the absolute offset of the current code segment being processed
    _seg_offset: list[int] = [0]  # mutable container for closure access

    def _replace(m: re.Match) -> str:
        # Compute absolute position of this match in the original code
        abs_pos = _seg_offset[0] + m.start()
        if _in_param_span(abs_pos):
            return m.group(0)  # inside function parameter list — leave unchanged
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
        _seg_offset[0] = prev
        result_parts.append(pattern.sub(_replace, code[prev:start]))
        # Preserve non-code verbatim
        result_parts.append(code[start:end])
        prev = end
    # Remaining code after last non-code span
    _seg_offset[0] = prev
    result_parts.append(pattern.sub(_replace, code[prev:]))

    code = "".join(result_parts)

    # Second pass: bracket notation this['name'] and this["name"]
    # Can't use regex on code segments because the quotes inside brackets
    # get classified as non-code strings. Use position-based matching instead.
    all_members_set = set(all_members)
    bracket_pattern = re.compile(
        r"""\bthis\[(['"])(\w+)\1\]"""
    )
    non_code_spans = _collect_non_code_spans(code)
    param_spans = _collect_param_spans(code, non_code_spans)

    def _in_non_code(pos: int) -> bool:
        return any(s <= pos < e for s, e in non_code_spans)

    def _in_param_span_2(pos: int) -> bool:
        return any(s <= pos < e for s, e in param_spans)

    replacements: list[tuple[int, int, str]] = []
    for m in bracket_pattern.finditer(code):
        if _in_non_code(m.start()):
            continue
        if _in_param_span_2(m.start()):
            continue
        name = m.group(2)
        if name not in all_members_set:
            continue
        if name in ref_set:
            replacements.append((m.start(), m.end(), f"{name}.value"))
        elif name in plain_set:
            replacements.append((m.start(), m.end(), name))

    # Apply from end to start to preserve positions
    for start, end, replacement in reversed(replacements):
        code = code[:start] + replacement + code[end:]

    return code


def _extract_paren_args(code: str, open_paren_pos: int) -> tuple[str, int] | None:
    """Extract content between matching ( ) parens, skipping strings/comments.

    Args:
        code: The full source text.
        open_paren_pos: Index of the opening '('.

    Returns:
        (content_between_parens, closing_paren_pos) or None if unmatched.
    """
    depth = 0
    pos = open_paren_pos
    while pos < len(code):
        new_pos, skipped = skip_non_code(code, pos)
        if skipped:
            pos = new_pos
            continue
        ch = code[pos]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return code[open_paren_pos + 1: pos], pos
        pos += 1
    return None


def _split_top_level_args(args_str: str) -> list[str]:
    """Split argument string at top-level commas, respecting all bracket types.

    Tracks depth across (), [], {} and skips strings/comments.
    """
    args: list[str] = []
    depth = 0
    current_start = 0
    pos = 0
    while pos < len(args_str):
        new_pos, skipped = skip_non_code(args_str, pos)
        if skipped:
            pos = new_pos
            continue
        ch = args_str[pos]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            args.append(args_str[current_start:pos].strip())
            current_start = pos + 1
        pos += 1
    # Last argument
    last = args_str[current_start:].strip()
    if last:
        args.append(last)
    return args


def _rewrite_watch_call(args_str: str) -> str | None:
    """Convert this.$watch() arguments to watch() arguments.

    Handles:
    - String key: 'prop' -> prop  (bare ref, matching generate_watch_call convention)
    - Dotted string key: 'a.b' -> () => a.value.b
    - Function getter: () => this.x -> () => x.value  (this. refs rewritten)

    Returns the rewritten argument string, or None if unparseable.
    """
    args = _split_top_level_args(args_str)
    if len(args) < 2:
        return None

    first_arg = args[0].strip()

    # Case 1: String literal key
    if (len(first_arg) >= 2 and
            first_arg[0] in ("'", '"') and first_arg[-1] == first_arg[0]):
        key = first_arg[1:-1]
        if not key or not all(c.isalnum() or c in "._$" for c in key):
            return None  # unparseable key
        if "." in key:
            # Dotted key -> getter function
            parts = key.split(".")
            root = parts[0]
            rest = ".".join(parts[1:])
            watch_source = f"() => {root}.value.{rest}"
        else:
            # Simple key -> bare ref name
            watch_source = key
        remaining = ", ".join(args[1:])
        return f"{watch_source}, {remaining}"

    # Case 2: Function expression getter (arrow or function keyword)
    # Detect arrow function or function keyword
    stripped = first_arg.lstrip()
    is_fn_expr = (
        stripped.startswith("(") or  # arrow: (params) => ...
        stripped.startswith("function") or  # function() { ... }
        re.match(r"^\w+\s*=>", stripped)  # arrow: x => ...
    )
    if is_fn_expr:
        # Best-effort rewrite of this.X -> X.value in the getter expression.
        # In the real pipeline, rewrite_this_refs() runs BEFORE this function
        # and handles member-aware rewriting (refs get .value, methods don't).
        # By the time we get here, most this.X references are already gone.
        # This catch-all only handles residual cases that rewrite_this_refs missed.
        # It doesn't skip strings/comments — acceptable since getters are typically
        # short expressions, not multi-line code with string literals.
        def _rewrite_this_in_getter(getter: str) -> str:
            return re.sub(r"\bthis\.(\w+)", lambda m: f"{m.group(1)}.value", getter)

        rewritten_getter = _rewrite_this_in_getter(first_arg)
        remaining = ", ".join(args[1:])
        return f"{rewritten_getter}, {remaining}"

    return None  # unparseable first argument


def rewrite_this_dollar_refs(code: str) -> tuple[str, list[str]]:
    """Rewrite this.$xxx patterns that have direct Vue 3 equivalents.

    Auto-rewrites:
    - this.$nextTick(cb)         -> nextTick(cb)
    - this.$set(obj, key, val)   -> obj[key] = val
    - this.$delete(obj, key)     -> delete obj[key]
    - this.$watch(key, handler)  -> watch(key, handler)

    Skips matches inside strings and comments.

    Returns (rewritten_code, list_of_required_imports).
    """
    if not code:
        return code, []

    imports: list[str] = []

    # Collect non-code spans so we only rewrite in actual code
    non_code_spans = _collect_non_code_spans(code)

    def _in_non_code(pos: int) -> bool:
        return any(start <= pos < end for start, end in non_code_spans)

    # Process replacements from end to start to preserve positions
    replacements: list[tuple[int, int, str]] = []

    # 1. this.$nextTick( -> nextTick(
    for m in re.finditer(r"this\.\$nextTick\b", code):
        if not _in_non_code(m.start()):
            replacements.append((m.start(), m.end(), "nextTick"))
            if "nextTick" not in imports:
                imports.append("nextTick")

    # 2. this.$set(obj, key, val) -> obj[key] = val
    for m in re.finditer(r"this\.\$set\(([^,]+),\s*([^,]+),\s*([^)]+)\)", code):
        if not _in_non_code(m.start()):
            obj = m.group(1).strip()
            key = m.group(2).strip()
            val = m.group(3).strip()
            replacements.append((m.start(), m.end(), f"{obj}[{key}] = {val}"))

    # 3. this.$delete(obj, key) -> delete obj[key]
    for m in re.finditer(r"this\.\$delete\(([^,]+),\s*([^)]+)\)", code):
        if not _in_non_code(m.start()):
            obj = m.group(1).strip()
            key = m.group(2).strip()
            replacements.append((m.start(), m.end(), f"delete {obj}[{key}]"))

    # 4. this.$watch(key/fn, handler[, options]) -> watch(source, handler[, options])
    for m in re.finditer(r"this\.\$watch\(", code):
        if _in_non_code(m.start()):
            continue
        open_paren = m.end() - 1  # index of '('
        result_args = _extract_paren_args(code, open_paren)
        if result_args is None:
            continue
        args_content, close_paren = result_args
        rewritten_args = _rewrite_watch_call(args_content)
        if rewritten_args is None:
            continue  # unparseable — leave unchanged, warning still fires
        replacements.append((m.start(), close_paren + 1, f"watch({rewritten_args})"))
        if "watch" not in imports:
            imports.append("watch")

    # Filter out replacements that overlap with larger ones (e.g. a $nextTick
    # match inside a $watch span would conflict — the $watch replacement already
    # covers the entire call including its arguments).
    replacements.sort(key=lambda r: (r[0], -(r[1] - r[0])))  # by start, largest first
    filtered: list[tuple[int, int, str]] = []
    for repl in replacements:
        start, end, text = repl
        if filtered and start >= filtered[-1][0] and end <= filtered[-1][1]:
            continue  # contained within the previous (larger) replacement
        filtered.append(repl)

    # Apply replacements from end to start to preserve positions
    filtered.sort(key=lambda r: r[0], reverse=True)
    result = code
    for start, end, replacement in filtered:
        result = result[:start] + replacement + result[end:]

    return result, imports


def rewrite_this_i18n_refs(code: str) -> tuple[str, set[str]]:
    """Rewrite this.$t/tc/te/d/n patterns to composable equivalents.

    Returns (rewritten_code, set_of_i18n_functions_used).
    The caller must arrange for: import { useI18n } from 'vue-i18n'
    and: const { t, te, ... } = useI18n()

    Mapping:
    - this.$t(   -> t(    (i18n function: t)
    - this.$tc(  -> t(    (i18n function: t; $tc merged into t in vue-i18n v9)
    - this.$te(  -> te(   (i18n function: te)
    - this.$d(   -> d(    (i18n function: d)
    - this.$n(   -> n(    (i18n function: n)
    """
    if not code:
        return code, set()

    # Mapping from Vue 2 pattern suffix to Vue 3 function name
    i18n_map = {
        '$t': 't',
        '$tc': 't',
        '$te': 'te',
        '$d': 'd',
        '$n': 'n',
    }

    used_functions: set[str] = set()

    # Collect non-code spans so we only rewrite in actual code
    non_code_spans = _collect_non_code_spans(code)

    def _in_non_code(pos: int) -> bool:
        return any(start <= pos < end for start, end in non_code_spans)

    # Process replacements from end to start to preserve positions
    replacements: list[tuple[int, int, str]] = []

    # Match this.$t(, this.$tc(, this.$te(, this.$d(, this.$n(
    # Use word boundary before 'this' and look for the opening paren
    for m in re.finditer(r'this\.(\$t(?:c|e)?|\$[dn])\(', code):
        if not _in_non_code(m.start()):
            key = m.group(1)
            func_name = i18n_map.get(key)
            if func_name:
                # Replace "this.$t(" with "t(" etc. — keep the opening paren
                replacements.append((m.start(), m.end() - 1, func_name))
                used_functions.add(func_name)

    # Apply replacements from end to start
    replacements.sort(key=lambda r: r[0], reverse=True)
    result = code
    for start, end, replacement in replacements:
        result = result[:start] + replacement + result[end:]

    return result, used_functions
