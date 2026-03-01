"""Convert Vue 2 lifecycle hooks to Vue 3 composition API form."""
import re
from ..core.js_parser import skip_non_code, extract_brace_block
from .this_rewriter import rewrite_this_refs

HOOK_MAP: dict[str, str | None] = {
    "beforeCreate": None,   # inline in setup (no wrapper needed)
    "created":      None,   # inline in setup
    "beforeMount":  "onBeforeMount",
    "mounted":      "onMounted",
    "beforeUpdate": "onBeforeUpdate",
    "updated":      "onUpdated",
    "beforeDestroy": "onBeforeUnmount",
    "destroyed":    "onUnmounted",
    "activated":    "onActivated",
    "deactivated":  "onDeactivated",
    "errorCaptured": "onErrorCaptured",
}


def extract_hook_body(mixin_source: str, hook_name: str) -> str | None:
    """Extract the body of a lifecycle hook from mixin source.

    Handles patterns:
      hookName() { ... }
      hookName: function() { ... }
      hookName: () => { ... }

    Safety measures:
    - Skips hook name occurrences in strings/comments (R-1)
    - Skips hook name occurrences inside methods/computed/data blocks (R-2)

    Uses extract_brace_block for correct nested-brace handling.
    Returns the text between the outer braces, or None if not found.
    """
    # R-1: Build non-code spans to skip string/comment false positives
    non_code: list[tuple[int, int]] = []
    pos = 0
    while pos < len(mixin_source):
        new_pos, skipped = skip_non_code(mixin_source, pos)
        if skipped:
            non_code.append((pos, new_pos))
            pos = new_pos
        else:
            pos += 1

    def _in_non_code(p: int) -> bool:
        return any(s <= p < e for s, e in non_code)

    # R-2: Build exclusion zones for methods/computed/data sub-blocks
    excluded: list[tuple[int, int]] = []
    export_match = re.search(r'export\s+default\s*\{', mixin_source)
    if export_match:
        obj_start = export_match.end() - 1  # position of {
        obj_body = extract_brace_block(mixin_source, obj_start)
        content_start = obj_start + 1  # first char inside {}

        for section in ('methods', 'computed'):
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

    def _in_excluded(p: int) -> bool:
        return any(s <= p < e for s, e in excluded)

    pattern = re.compile(rf'\b{re.escape(hook_name)}\b')
    for match in pattern.finditer(mixin_source):
        if _in_non_code(match.start()) or _in_excluded(match.start()):
            continue
        pos = match.end()
        brace_pos = None
        limit = pos + 400  # enough for any realistic hook signature
        while pos < min(len(mixin_source), limit):
            new_pos, skipped = skip_non_code(mixin_source, pos)
            if skipped:
                pos = new_pos
                continue
            ch = mixin_source[pos]
            if ch == '{':
                brace_pos = pos
                break
            if ch in (',', '}'):
                break
            pos += 1
        if brace_pos is not None:
            return extract_brace_block(mixin_source, brace_pos)
    return None


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

    for hook in hooks:
        if hook not in HOOK_MAP:
            continue
        body = extract_hook_body(mixin_source, hook)
        if body is None or not body.strip():
            continue  # skip missing or empty hooks
        rewritten = rewrite_this_refs(body.strip(), ref_members, plain_members)
        body_lines = [
            f"{inner}{line}" if line.strip() else ""
            for line in rewritten.splitlines()
        ]
        vue3_fn = HOOK_MAP[hook]
        if vue3_fn is None:
            inline_lines.extend(
                f"{indent}{line.strip()}" for line in rewritten.splitlines()
                if line.strip()
            )
        else:
            wrapped_lines.append(f"{indent}{vue3_fn}(() => {{")
            wrapped_lines.extend(body_lines)
            wrapped_lines.append(f"{indent}}})")

    return inline_lines, wrapped_lines


def get_required_imports(hooks: list[str]) -> list[str]:
    """Return Vue composition API import names needed for the given hooks.

    Excludes beforeCreate and created (they inline directly in setup()).
    """
    result = []
    for hook in hooks:
        vue3_fn = HOOK_MAP.get(hook)
        if vue3_fn is not None:
            result.append(vue3_fn)
    return list(dict.fromkeys(result))
