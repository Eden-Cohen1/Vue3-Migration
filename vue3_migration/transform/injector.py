"""
Code injection — add/remove imports, manipulate mixins arrays, inject setup() functions.

All functions operate on source text strings and return modified text.
They do NOT perform file I/O — callers handle reading/writing.
"""

import re

from ..core.js_parser import extract_brace_block


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
    composable_calls: list[tuple[str, list[str]]],
    indent: str = "  ",
    lifecycle_calls: list[str] | None = None,
    inline_setup_lines: list[str] | None = None,
) -> str:
    """Create or merge setup() with multiple composable destructuring calls.

    Args:
        content: The component source text.
        composable_calls: List of (fn_name, [member1, member2, ...]) tuples.
        indent: Indentation string (default 2 spaces).
        lifecycle_calls: Lines to append at the END of setup() body (e.g.
            ``onMounted(() => {...})`` wrapped hooks).
        inline_setup_lines: Lines to prepend at the TOP of setup() body (e.g.
            ``created``/``beforeCreate`` hook bodies inlined directly).

    Returns:
        Modified source text with setup() containing all composable calls,
        inline setup lines, and lifecycle wrapper calls in that order.
    """
    all_returned_members = []
    call_lines = []
    for fn_name, members in composable_calls:
        call_lines.append(f"{indent}{indent}const {{ {', '.join(members)} }} = {fn_name}()")
        all_returned_members.extend(members)

    # Prepend inline lines (created/beforeCreate bodies inlined in setup)
    if inline_setup_lines:
        call_lines = list(inline_setup_lines) + call_lines

    # Append lifecycle wrapper calls (onMounted, onBeforeUnmount, etc.)
    if lifecycle_calls:
        call_lines = call_lines + list(lifecycle_calls)

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


def find_mixin_import_name(content: str, mixin_stem: str) -> str | None:
    """Find the local import name for a mixin by its file stem."""
    pattern = rf"""import\s+(\w+)\s+from\s+['"].*?{re.escape(mixin_stem)}(?:\.(?:js|ts))?['"]"""
    match = re.search(pattern, content)
    return match.group(1) if match else None
