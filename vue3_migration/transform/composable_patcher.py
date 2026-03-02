"""Patch existing composables to fix BLOCKED_NOT_RETURNED and BLOCKED_MISSING_MEMBERS."""
import re
from ..core.composable_analyzer import extract_all_identifiers
from ..core.js_parser import extract_brace_block, skip_non_code
from ..models import MixinMembers
from .this_rewriter import rewrite_this_refs
from .lifecycle_converter import extract_hook_body


def add_keys_to_return(content: str, keys: list[str]) -> str:
    """Add missing keys to the composable's return { } statement.

    Uses the LAST return statement (Risk R-3: avoids patching early-exit returns).
    Skips keys already present (idempotent).
    Returns content unchanged if no 'return {' statement is found (Risk R-4).
    """
    matches = list(re.finditer(r'\breturn\s*\{', content))
    if not matches:
        print(
            "  [composable_patcher] WARNING: No 'return {' found. "
            "Composable may use a variable return — manual migration required."
        )
        return content
    m = matches[-1]  # use LAST return (R-3 fix)
    return_block = extract_brace_block(content, m.end() - 1)
    existing = set(re.findall(r'\b(\w+)\b', return_block))
    new_keys = [k for k in keys if k not in existing]
    if not new_keys:
        return content
    insert_pos = m.end()
    prefix = " " + ", ".join(new_keys) + ","
    return content[:insert_pos] + prefix + content[insert_pos:]


def add_members_to_composable(content: str, member_lines: list[str]) -> str:
    """Insert new member declarations just before the return statement.

    Skips any line whose declared name already appears in the composable (idempotent).
    Returns content unchanged if no return statement is found.
    """
    # Normalize CRLF (R-7)
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    m = re.search(r'\n([ \t]*)\breturn\s*\{', content)
    if not m:
        return content
    existing_ids = set(extract_all_identifiers(content))
    lines_to_add = []
    for line in member_lines:
        name_match = re.search(r'\b(?:const|let|var|function)\s+(\w+)', line)
        if name_match:
            if name_match.group(1) not in existing_ids:
                lines_to_add.append(line)
        else:
            lines_to_add.append(line)  # no name detected — add anyway
    if not lines_to_add:
        return content
    insertion = "\n".join(lines_to_add)
    return content[:m.start()] + "\n" + insertion + content[m.start():]


def _extract_data_default(mixin_source: str, name: str) -> str:
    """Try to extract the default value of a data property from mixin source."""
    data_match = re.search(r'\bdata\s*\(\s*\)\s*\{', mixin_source)
    if not data_match:
        return "null"
    data_body = extract_brace_block(mixin_source, data_match.end() - 1)
    ret_match = re.search(r'\breturn\s*\{', data_body)
    if not ret_match:
        return "null"
    ret_body = extract_brace_block(data_body, ret_match.end() - 1)
    val_match = re.search(
        rf'\b{re.escape(name)}\s*:\s*([^,\n}}]+)',
        ret_body
    )
    return val_match.group(1).strip() if val_match else "null"


def generate_member_declaration(
    name: str,
    mixin_source: str,
    mixin_members: MixinMembers,
    ref_members: list[str],
    plain_members: list[str],
    indent: str = "  ",
) -> str:
    """Generate a Vue 3 composable declaration for a single mixin member.

    - data:     const name = ref(<initial_value>)
    - computed: const name = computed(() => { <rewritten body> })
               (getter/setter computed → // TODO comment)
    - methods:  function name(<params>) { <rewritten body> }
    - watch:    // watch: name — manual migration needed
    """
    if name in mixin_members.data:
        default = _extract_data_default(mixin_source, name)
        return f"{indent}const {name} = ref({default})"

    if name in mixin_members.computed:
        body = extract_hook_body(mixin_source, name)  # reuse brace extractor
        # R-5: getter/setter computed guard
        if body and re.search(r'\bget\s*\(', body):
            return f"{indent}const {name} = computed(() => null) // TODO: getter/setter computed — migrate manually"
        if body:
            rewritten = rewrite_this_refs(body.strip(), ref_members, plain_members)
            return f"{indent}const {name} = computed(() => {{ {rewritten} }})"
        return f"{indent}const {name} = computed(() => null) // TODO: implement"

    if name in mixin_members.methods:
        sig_match = re.search(
            rf'\b{re.escape(name)}\s*\(([^)]*)\)\s*\{{',
            mixin_source
        )
        params = sig_match.group(1) if sig_match else ""
        body = extract_hook_body(mixin_source, name)
        if body:
            rewritten = rewrite_this_refs(body.strip(), ref_members, plain_members)
            inner = indent + indent
            body_lines = f"\n{inner}" + f"\n{inner}".join(rewritten.splitlines()) + f"\n{indent}"
            # Detect async
            async_match = re.search(rf'\basync\s+{re.escape(name)}\b', mixin_source)
            async_prefix = "async " if async_match else ""
            return f"{indent}{async_prefix}function {name}({params}) {{{body_lines}}}"
        return f"{indent}function {name}({params}) {{}} // TODO: implement"

    if name in mixin_members.watch:
        return f"{indent}// watch: {name} — migrate manually"

    return f"{indent}// {name} — could not classify, migrate manually"


def patch_composable(
    composable_content: str,
    mixin_content: str,
    not_returned: list[str],
    missing: list[str],
    mixin_members: MixinMembers,
    indent: str = "  ",
) -> str:
    """Orchestrate composable patching for both blocked cases.

    R-6: If the composable uses reactive(), skip auto-patching and warn.

    Step 1 (not_returned): Add keys to the return statement.
    Step 2 (missing): Generate declarations and insert before return,
                      then add the names to the return statement.

    Returns modified composable content (unchanged if reactive() guard triggered).
    """
    # R-6: reactive() guard
    if 'reactive(' in composable_content:
        print(
            "  [composable_patcher] WARNING: Composable uses reactive() — "
            "skipping auto-patch, manual migration required."
        )
        return composable_content

    content = composable_content
    ref_members = mixin_members.data + mixin_members.computed + mixin_members.watch
    plain_members = mixin_members.methods

    # Step 1: fix BLOCKED_NOT_RETURNED
    if not_returned:
        content = add_keys_to_return(content, not_returned)

    # Step 2: fix BLOCKED_MISSING_MEMBERS
    if missing:
        declarations = [
            generate_member_declaration(
                name, mixin_content, mixin_members, ref_members, plain_members, indent
            )
            for name in missing
        ]
        content = add_members_to_composable(content, declarations)
        content = add_keys_to_return(content, missing)

    return content
