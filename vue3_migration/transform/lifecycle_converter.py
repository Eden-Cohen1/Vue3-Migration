"""Convert Vue 2 lifecycle hooks to Vue 3 composition API form."""
import re
import textwrap
from ..core.js_parser import skip_non_code, extract_brace_block, strip_comments
from .this_rewriter import rewrite_this_refs

_MAX_SIGNATURE_SCAN = 400  # max chars to scan from hook name to opening brace

HOOK_MAP: dict[str, str | None] = {
    "beforeCreate": None,   # inline in setup (no wrapper needed)
    "created":      None,   # inline in setup
    "beforeMount":  "onBeforeMount",
    "mounted":      "onMounted",
    "beforeUpdate": "onBeforeUpdate",
    "updated":      "onUpdated",
    "beforeDestroy": "onBeforeUnmount",
    "beforeUnmount": "onBeforeUnmount",
    "destroyed":    "onUnmounted",
    "unmounted":    "onUnmounted",
    "activated":    "onActivated",
    "deactivated":  "onDeactivated",
    "errorCaptured": "onErrorCaptured",
}

# Vue 2 destroy hook names (used for fallback scanning)
_DESTROY_HOOKS = {"beforeDestroy", "destroyed", "beforeUnmount", "unmounted"}


def _build_exclusion_context(
    mixin_source: str, exclude_sections: bool = True,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Build non-code spans and section exclusion zones for hook scanning.

    Returns (non_code_spans, excluded_zones) where each is a list of
    (start, end) character offset ranges.  Used by both
    ``extract_hook_body`` and ``extract_hook_params`` to skip false
    positives inside strings, comments, and nested option blocks.
    """
    non_code: list[tuple[int, int]] = []
    pos = 0
    while pos < len(mixin_source):
        new_pos, skipped = skip_non_code(mixin_source, pos)
        if skipped:
            non_code.append((pos, new_pos))
            pos = new_pos
        else:
            pos += 1

    excluded: list[tuple[int, int]] = []
    if exclude_sections:
        export_match = re.search(r'export\s+default\s*\{', mixin_source)
        if export_match:
            obj_start = export_match.end() - 1
            obj_body = extract_brace_block(mixin_source, obj_start)
            content_start = obj_start + 1

            for section in ('methods', 'computed', 'watch', 'directives'):
                sm = re.search(rf'\b{section}\s*:\s*\{{', mixin_source[content_start:content_start + len(obj_body)])
                if sm:
                    abs_brace = content_start + sm.end() - 1
                    blk = extract_brace_block(mixin_source, abs_brace)
                    excluded.append((abs_brace, abs_brace + 1 + len(blk) + 1))

            dm = re.search(r'\bdata\s*\(\s*\)\s*\{', mixin_source[content_start:content_start + len(obj_body)])
            if dm:
                abs_brace = content_start + dm.end() - 1
                blk = extract_brace_block(mixin_source, abs_brace)
                excluded.append((abs_brace, abs_brace + 1 + len(blk) + 1))

    return non_code, excluded


def _should_skip(pos: int, source: str, non_code: list, excluded: list) -> bool:
    """Check if a match position should be skipped (non-code, excluded, or dot-access)."""
    if any(s <= pos < e for s, e in non_code):
        return True
    if any(s <= pos < e for s, e in excluded):
        return True
    if pos > 0 and source[pos - 1] == '.':
        return True
    return False


def extract_hook_body(mixin_source: str, hook_name: str, exclude_sections: bool = True) -> str | None:
    """Extract the body of a named function/property from mixin source.

    Handles patterns:
      hookName() { ... }
      hookName: function() { ... }
      hookName: () => { ... }

    Safety measures:
    - Skips hook name occurrences in strings/comments (R-1)
    - Skips hook name occurrences inside methods/computed/data/directives blocks (R-2)
      (only when exclude_sections=True; set False to extract members
       that live *inside* those blocks, e.g. a method or computed property)

    Uses extract_brace_block for correct nested-brace handling.
    Returns the text between the outer braces, or None if not found.
    """
    non_code, excluded = _build_exclusion_context(mixin_source, exclude_sections)

    pattern = re.compile(rf'\b{re.escape(hook_name)}\b')
    for match in pattern.finditer(mixin_source):
        if _should_skip(match.start(), mixin_source, non_code, excluded):
            continue
        pos = match.end()
        brace_pos = None
        limit = pos + _MAX_SIGNATURE_SCAN
        while pos < min(len(mixin_source), limit):
            new_pos, skipped = skip_non_code(mixin_source, pos)
            if skipped:
                pos = new_pos
                continue
            ch = mixin_source[pos]
            if ch == '{':
                brace_pos = pos
                break
            if ch == '(':
                # Skip parenthesized parameter list to avoid breaking
                # on commas inside e.g. hookName(err, vm, info) { ... }
                depth = 1
                pos += 1
                while pos < len(mixin_source) and depth > 0:
                    if mixin_source[pos] == '(':
                        depth += 1
                    elif mixin_source[pos] == ')':
                        depth -= 1
                    pos += 1
                continue
            if ch in (',', '}'):
                break
            pos += 1
        if brace_pos is not None:
            return extract_brace_block(mixin_source, brace_pos)
    return None


def extract_hook_body_with_offset(
    mixin_source: str, hook_name: str,
) -> tuple[str, int, int] | None:
    """Like ``extract_hook_body`` but also returns character offsets.

    Returns ``(body_text, hook_name_offset, brace_offset)`` or ``None``.
    """
    non_code, excluded = _build_exclusion_context(mixin_source)

    pattern = re.compile(rf'\b{re.escape(hook_name)}\b')
    for match in pattern.finditer(mixin_source):
        if _should_skip(match.start(), mixin_source, non_code, excluded):
            continue
        pos = match.end()
        brace_pos = None
        limit = pos + _MAX_SIGNATURE_SCAN
        while pos < min(len(mixin_source), limit):
            new_pos, skipped = skip_non_code(mixin_source, pos)
            if skipped:
                pos = new_pos
                continue
            ch = mixin_source[pos]
            if ch == '{':
                brace_pos = pos
                break
            if ch == '(':
                depth = 1
                pos += 1
                while pos < len(mixin_source) and depth > 0:
                    if mixin_source[pos] == '(':
                        depth += 1
                    elif mixin_source[pos] == ')':
                        depth -= 1
                    pos += 1
                continue
            if ch in (',', '}'):
                break
            pos += 1
        if brace_pos is not None:
            body = extract_brace_block(mixin_source, brace_pos)
            return body, match.start(), brace_pos
    return None


def extract_hook_params(mixin_source: str, hook_name: str) -> str:
    """Extract the parameter list of a lifecycle hook.

    Uses the same exclusion logic as ``extract_hook_body`` so that hooks
    inside ``directives``, ``methods``, etc. are skipped.
    """
    non_code, excluded = _build_exclusion_context(mixin_source)

    pattern = re.compile(
        rf'\b{re.escape(hook_name)}\s*(?::\s*(?:async\s+)?function\s*)?\(([^)]*)\)'
    )
    for m in pattern.finditer(mixin_source):
        if _should_skip(m.start(), mixin_source, non_code, excluded):
            continue
        return m.group(1).strip()
    return ""


def convert_lifecycle_hooks(
    mixin_source: str,
    hooks: list[str],
    ref_members: list[str],
    plain_members: list[str],
    indent: str = "  ",
) -> tuple[list[str], list[str]]:
    """Convert Vue 2 lifecycle hooks to Vue 3 composition API calls.

    For beforeCreate/created: returns body lines as inline_lines (placed
    directly at the top of setup(), no wrapper).

    For all other hooks: returns wrapped lines like:
      onMounted(() => {
        <rewritten body>
      })

    Empty-body hooks are skipped.

    Args:
        mixin_source: Full mixin JS source.
        hooks: Hook names found in the mixin (from extract_lifecycle_hooks).
        ref_members: Passed to rewrite_this_refs (data + computed + watch).
        plain_members: Passed to rewrite_this_refs (methods).
        indent: Indentation for the setup() body (doubled for hook body).

    Returns:
        (inline_lines, wrapped_lines)
    """
    inner = indent + indent
    inline_lines: list[str] = []
    wrapped_lines: list[str] = []
    converted_hooks: set[str] = set()

    for hook in hooks:
        if hook not in HOOK_MAP:
            continue
        body = extract_hook_body(mixin_source, hook)
        if body is None or not body.strip():
            continue  # skip missing or empty hooks
        body_clean = textwrap.dedent(body).strip()
        rewritten = rewrite_this_refs(body_clean, ref_members, plain_members)
        vue3_fn = HOOK_MAP[hook]
        if vue3_fn is None:
            dedented = textwrap.dedent(rewritten)
            inline_lines.extend(
                f"{indent}{line.rstrip()}" for line in dedented.splitlines()
                if line.strip()
            )
        else:
            params = extract_hook_params(mixin_source, hook)
            param_str = f"({params})" if params else "()"
            body_lines = [
                f"{inner}{line}" if line.strip() else ""
                for line in rewritten.splitlines()
            ]
            wrapped_lines.append(f"{indent}{vue3_fn}({param_str} => {{")
            wrapped_lines.extend(body_lines)
            wrapped_lines.append(f"{indent}}})")
        converted_hooks.add(hook)

    # Fallback: if mounted was converted but no destroy/unmount hook was in the
    # list, do a direct scan of the mixin source and convert any found.
    has_mount = "mounted" in converted_hooks or "beforeMount" in converted_hooks
    has_destroy = bool(converted_hooks & _DESTROY_HOOKS)
    if has_mount and not has_destroy:
        for dh in ("beforeDestroy", "destroyed", "beforeUnmount", "unmounted"):
            if dh in converted_hooks:
                continue
            body = extract_hook_body(mixin_source, dh)
            if body is None or not body.strip():
                continue
            body_clean = textwrap.dedent(body).strip()
            rewritten = rewrite_this_refs(body_clean, ref_members, plain_members)
            vue3_fn = HOOK_MAP[dh]
            if vue3_fn is not None:
                params = extract_hook_params(mixin_source, dh)
                param_str = f"({params})" if params else "()"
                body_lines = [
                    f"{inner}{line}" if line.strip() else ""
                    for line in rewritten.splitlines()
                ]
                wrapped_lines.append(f"{indent}{vue3_fn}({param_str} => {{")
                wrapped_lines.extend(body_lines)
                wrapped_lines.append(f"{indent}}})")
                converted_hooks.add(dh)

    return inline_lines, wrapped_lines


def find_lifecycle_referenced_members(
    mixin_source: str,
    hooks: list[str],
    member_names: list[str],
) -> list[str]:
    """Find mixin members referenced inside lifecycle hook bodies.

    When a mixin's created() calls this.checkAuth(), the member checkAuth
    must be included in the composable destructure even though the component
    itself never references it.
    """
    referenced: list[str] = []
    for hook in hooks:
        body = extract_hook_body(mixin_source, hook)
        if not body:
            continue
        body = strip_comments(body)
        for member in member_names:
            if member not in referenced and re.search(
                rf"(?<!\w){re.escape(member)}(?!\w)", body
            ):
                referenced.append(member)
    return referenced


def get_required_imports(hooks: list[str], mixin_source: str | None = None) -> list[str]:
    """Return Vue composition API import names needed for the given hooks.

    Excludes beforeCreate and created (they inline directly in setup()).

    When *mixin_source* is provided, performs a fallback scan for destroy/unmount
    hooks that might not appear in the *hooks* list but are present in the source.
    """
    result = []
    for hook in hooks:
        vue3_fn = HOOK_MAP.get(hook)
        if vue3_fn is not None:
            result.append(vue3_fn)

    # Fallback: if mounted is in the list but no destroy hook, scan source
    if mixin_source is not None:
        has_mount = any(h in ("mounted", "beforeMount") for h in hooks)
        has_destroy = any(h in _DESTROY_HOOKS for h in hooks)
        if has_mount and not has_destroy:
            for dh in ("beforeDestroy", "destroyed", "beforeUnmount", "unmounted"):
                body = extract_hook_body(mixin_source, dh)
                if body and body.strip():
                    vue3_fn = HOOK_MAP.get(dh)
                    if vue3_fn is not None:
                        result.append(vue3_fn)
                    break  # one destroy hook is enough

    return list(dict.fromkeys(result))
