"""
Code injection — add/remove imports, manipulate mixins arrays, inject setup() functions.

All functions operate on source text strings and return modified text.
They do NOT perform file I/O — callers handle reading/writing.
"""

import re

from ..core.js_parser import extract_brace_block, skip_non_code
from .this_rewriter import rewrite_this_refs


def add_composable_import(content: str, fn_name: str, import_path: str) -> str:
    """Add composable import at the top of <script>. No-op if already present."""
    if re.search(rf"\b{re.escape(fn_name)}\b", content):
        return content

    import_line = f"import {{ {fn_name} }} from '{import_path}'\n"

    # Insert after <script> tag
    script_match = re.search(r"(<script[^>]*>\s*\n?)", content)
    if script_match:
        pos = script_match.end()
        return content[:pos] + import_line + content[pos:]

    # For .js/.ts: after the last existing import
    last_import = None
    for match in re.finditer(r"^import\s+.+$", content, re.MULTILINE):
        last_import = match
    if last_import:
        pos = last_import.end() + 1
        return content[:pos] + import_line + content[pos:]

    return import_line + content


def remove_import_line(content: str, mixin_stem: str) -> str:
    """Delete the import line for a specific mixin."""
    pattern = rf"""^[ \t]*import\s+\w+\s+from\s+['"].*?{re.escape(mixin_stem)}(?:\.(?:js|ts))?['"].*\n?"""
    return re.sub(pattern, "", content, count=1, flags=re.MULTILINE)


def remove_mixin_from_array(content: str, local_name: str) -> str:
    """Remove a mixin from `mixins: [...]`. Drops the whole line if array empties."""
    match = re.search(r"(\s*)mixins\s*:\s*\[([^\]]*)\](\s*,?)", content)
    if not match:
        return content

    indent, inner, trailing = match.group(1), match.group(2), match.group(3)
    items = [x.strip() for x in inner.split(",") if x.strip()]
    remaining = [x for x in items if x != local_name]

    if not remaining:
        return re.sub(r"[ \t]*mixins\s*:\s*\[[^\]]*\]\s*,?[ \t]*\n?", "", content, count=1)

    rebuilt = f"{indent}mixins: [{', '.join(remaining)}]{trailing}"
    return content[:match.start()] + rebuilt + content[match.end():]


def inject_setup(
    content: str,
    composable_calls: list[tuple],
    indent: str = "  ",
    lifecycle_calls: list[str] | None = None,
    inline_setup_lines: list[str] | None = None,
) -> str:
    """Create or merge setup() with multiple composable destructuring calls.

    Args:
        content: The component source text.
        composable_calls: List of tuples — either (fn_name, [members]) or
            (fn_name, import_path, [members]).  When import_path is provided,
            an import statement is added automatically.
        indent: Indentation string (default 2 spaces).
        lifecycle_calls: Lines to append at the END of setup() body (e.g.
            ``onMounted(() => {...})`` wrapped hooks).
        inline_setup_lines: Lines to prepend at the TOP of setup() body (e.g.
            ``created``/``beforeCreate`` hook bodies inlined directly).

    Returns:
        Modified source text with setup() containing inline setup lines,
        composable calls, and lifecycle wrapper calls in that order.
    """
    # Normalise 2-tuples and 3-tuples into a uniform structure
    parsed_calls: list[tuple[str, str | None, list[str]]] = []
    for call in composable_calls:
        if len(call) == 3:
            parsed_calls.append((call[0], call[1], call[2]))
        else:
            parsed_calls.append((call[0], None, call[1]))

    # Add composable imports for any call that provides an import_path
    for fn_name, import_path, _members in parsed_calls:
        if import_path is not None:
            content = add_composable_import(content, fn_name, import_path)

    all_returned_members = []
    call_lines = []
    for fn_name, _import_path, members in parsed_calls:
        call_lines.append(f"{indent}{indent}const {{ {', '.join(members)} }} = {fn_name}()")
        all_returned_members.extend(members)

    # Append inline lines AFTER composable calls (created/beforeCreate bodies
    # may reference composable-provided symbols, so they must come after)
    if inline_setup_lines:
        call_lines = call_lines + inline_setup_lines

    # Append lifecycle wrapper calls (onMounted, onBeforeUnmount, etc.)
    if lifecycle_calls:
        call_lines = call_lines + lifecycle_calls

    # --- Existing setup(): prepend calls, merge into return ---
    setup_match = re.search(r"\bsetup\s*\([^)]*\)\s*\{", content)
    if setup_match:
        # Insert composable calls as first lines
        insert_pos = setup_match.end()
        injection = "\n" + "\n".join(call_lines) + "\n"
        content = content[:insert_pos] + injection + content[insert_pos:]

        # Merge members into existing return statement
        ret_match = re.search(r"\breturn\s*\{", content[setup_match.start():])
        if ret_match:
            abs_pos = setup_match.start() + ret_match.end()
            block_start = abs_pos - 1
            existing_return = extract_brace_block(content, block_start)
            existing_keys = set(re.findall(r"\b(\w+)\b", existing_return))
            new_keys = [m for m in all_returned_members if m not in existing_keys]
            if new_keys:
                content = content[:abs_pos] + " " + ", ".join(new_keys) + "," + content[abs_pos:]
        else:
            # No return yet -- add one before closing brace
            body_start = setup_match.end() - 1
            body = extract_brace_block(content, body_start)
            close_pos = body_start + 1 + len(body)
            ret_stmt = f"\n{indent}{indent}return {{ {', '.join(all_returned_members)} }}\n{indent}"
            content = content[:close_pos] + ret_stmt + content[close_pos:]

        return content

    # --- No setup(): create one ---
    lines = [f"{indent}setup() {{"]
    lines.extend(call_lines)
    lines.append("")
    if all_returned_members:
        lines.append(f"{indent}{indent}return {{ {', '.join(all_returned_members)} }}")
    lines.append(f"{indent}}},")
    setup_block = "\n".join(lines) + "\n"

    # Insert before data()
    data_match = re.search(r"^(\s*)data\s*\(\s*\)\s*\{", content, re.MULTILINE)
    if data_match:
        return content[:data_match.start()] + setup_block + content[data_match.start():]

    # Fallback: after export default {
    export_match = re.search(r"export\s+default\s*\{[ \t]*\n?", content)
    if export_match:
        return content[:export_match.end()] + setup_block + content[export_match.end():]

    return content


def _find_all_this_refs(code: str) -> list[str]:
    """Return all ``this.xxx`` member names referenced in code, skipping non-code.

    Also catches Vue instance properties like ``this.$emit``, ``this.$refs``.
    """
    refs: list[str] = []
    for m in re.finditer(r"\bthis\.([$\w]+)", code):
        # Confirm the match isn't inside a string/comment
        pos = m.start()
        new_pos, skipped = skip_non_code(code, pos)
        if not skipped:
            refs.append(m.group(1))
    return refs


def _extract_methods_block(content: str) -> tuple[int, int, str] | None:
    """Find the methods: { ... } block. Returns (start, end, body) or None."""
    match = re.search(r"\bmethods\s*:\s*\{", content)
    if not match:
        return None
    brace_pos = match.end() - 1
    body = extract_brace_block(content, brace_pos)
    # start = match.start(), end = closing brace + 1 + optional trailing comma
    end = brace_pos + 1 + len(body) + 1
    # Skip trailing comma and whitespace
    if end < len(content) and content[end] == ",":
        end += 1
    return match.start(), end, body


def _extract_individual_methods(body: str) -> list[tuple[str, str, str]]:
    """Extract individual methods from a methods block body.

    Returns list of (name, params, method_body) tuples.
    Handles: ``name(params) { body }`` and ``async name(params) { body }``
    """
    methods = []
    pattern = re.compile(r"(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{")
    pos = 0
    while pos < len(body):
        new_pos, skipped = skip_non_code(body, pos)
        if skipped:
            pos = new_pos
            continue
        m = pattern.match(body, pos)
        if m:
            name = m.group(1)
            params = m.group(2).strip()
            brace_pos = m.end() - 1
            method_body = extract_brace_block(body, brace_pos)
            methods.append((name, params, method_body))
            pos = brace_pos + 1 + len(method_body) + 1
            continue
        pos += 1
    return methods


def migrate_methods_to_setup(
    content: str,
    composable_members: set[str],
    ref_members: list[str],
    plain_members: list[str],
    indent: str = "  ",
) -> str:
    """Move component methods into setup() when they only use composable members.

    For each method in the ``methods: { ... }`` block:
    - If all ``this.xxx`` references are in composable_members, convert it
      to a plain function inside setup() and add it to the return statement.
    - If any ``this.xxx`` reference is NOT in composable_members, leave it.

    Removes the ``methods`` block entirely if all methods are migrated.
    """
    methods_info = _extract_methods_block(content)
    if not methods_info:
        return content

    methods_start, methods_end, methods_body = methods_info
    individual = _extract_individual_methods(methods_body)

    if not individual:
        return content

    migrated_names: list[str] = []
    migrated_functions: list[str] = []
    kept_methods: list[tuple[str, str, str]] = []

    for name, params, method_body in individual:
        this_refs = _find_all_this_refs(method_body)
        # $emit, $refs, $router, etc. are never in composable_members
        all_resolved = all(ref in composable_members for ref in this_refs)

        if all_resolved and this_refs:  # at least one this.* ref resolved
            rewritten = rewrite_this_refs(method_body.strip(), ref_members, plain_members)
            # Build function declaration
            lines = [f"{indent}{indent}function {name}({params}) {{"]
            for line in rewritten.splitlines():
                if line.strip():
                    lines.append(f"{indent}{indent}  {line.strip()}")
                else:
                    lines.append("")
            lines.append(f"{indent}{indent}}}")
            migrated_functions.append("\n".join(lines))
            migrated_names.append(name)
        else:
            kept_methods.append((name, params, method_body))

    if not migrated_names:
        return content  # nothing to migrate

    # Insert migrated functions into setup() (before return statement)
    setup_match = re.search(r"\bsetup\s*\([^)]*\)\s*\{", content)
    if not setup_match:
        return content  # no setup() to insert into

    # Find the return statement in setup()
    ret_match = re.search(r"\breturn\s*\{", content[setup_match.start():])
    if ret_match:
        abs_ret_pos = setup_match.start() + ret_match.start()
        # Insert functions before the return
        func_block = "\n".join(migrated_functions) + "\n\n"
        content = content[:abs_ret_pos] + func_block + content[abs_ret_pos:]

        # Add migrated names to the return statement
        ret_match2 = re.search(r"\breturn\s*\{", content[setup_match.start():])
        if ret_match2:
            abs_pos = setup_match.start() + ret_match2.end()
            content = content[:abs_pos] + " " + ", ".join(migrated_names) + "," + content[abs_pos:]

    # Remove or rebuild the methods block
    # Re-find methods block since content may have shifted
    methods_info2 = _extract_methods_block(content)
    if methods_info2:
        m_start, m_end, _ = methods_info2
        if not kept_methods:
            # Remove entire methods block (including trailing newline)
            while m_end < len(content) and content[m_end] in " \t\n":
                m_end += 1
            content = content[:m_start] + content[m_end:]
        else:
            # Rebuild with only kept methods
            inner = indent
            rebuilt_parts = []
            for name, params, body in kept_methods:
                rebuilt_parts.append(f"{inner}{indent}{name}({params}) {{{body}}},")
            rebuilt = f"{inner}methods: {{\n" + "\n".join(rebuilt_parts) + f"\n{inner}}},\n"
            content = content[:m_start] + rebuilt + content[m_end:]

    return content


def find_mixin_import_name(content: str, mixin_stem: str) -> str | None:
    """Find the local import name for a mixin by its file stem."""
    pattern = rf"""import\s+(\w+)\s+from\s+['"].*?{re.escape(mixin_stem)}(?:\.(?:js|ts))?['"]"""
    match = re.search(pattern, content)
    return match.group(1) if match else None
