"""Patch existing composables to fix BLOCKED_NOT_RETURNED and BLOCKED_MISSING_MEMBERS."""
import re
import textwrap
from ..core.composable_analyzer import extract_all_identifiers
from ..core.js_parser import extract_brace_block, extract_value_at
from ..core.warning_collector import (
    collect_mixin_warnings, compute_confidence, inject_inline_warnings,
)
from ..models import MixinMembers
from .this_rewriter import rewrite_this_refs, rewrite_this_dollar_refs
from .lifecycle_converter import (
    extract_hook_body, convert_lifecycle_hooks, get_required_imports, HOOK_MAP,
)


def _add_vue_import(content: str, name: str) -> str:
    """Add a name to the existing ``import { ... } from 'vue'`` line.

    If no vue import line exists, prepend one.
    """
    m = re.search(r"(import\s*\{)([^}]*)(}\s*from\s*['\"]vue['\"])", content)
    if m:
        existing = m.group(2)
        if not re.search(rf'\b{re.escape(name)}\b', existing):
            new_imports = existing.rstrip() + ", " + name + " "
            return content[:m.start(1)] + m.group(1) + new_imports + m.group(3) + content[m.end():]
        return content
    # No vue import line — prepend one
    return f"import {{ {name} }} from 'vue'\n" + content


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
            "Composable may use a variable return -- manual migration required."
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
    data_match = re.search(r'\bdata\s*\(\s*\)\s*(?::\s*\w+(?:<[^>]*>)?\s*)?\{', mixin_source)
    if not data_match:
        return "null"
    data_body = extract_brace_block(mixin_source, data_match.end() - 1)
    ret_match = re.search(r'\breturn\s*\{', data_body)
    if not ret_match:
        return "null"
    ret_body = extract_brace_block(data_body, ret_match.end() - 1)
    val_match = re.search(
        rf'\b{re.escape(name)}\s*:\s*',
        ret_body
    )
    if not val_match:
        return "null"
    return extract_value_at(ret_body, val_match.end())


def parse_getter_setter_computed(body: str) -> dict | None:
    """Parse a getter/setter computed property body.

    Expects the body of a computed entry like:
      get() { return this.first + ' ' + this.last },
      set(val) { ... }

    Returns dict with keys: get_body, set_body (optional), set_params.
    Returns None if no get() found.
    """
    get_m = re.search(r'\bget\s*\(\s*\)', body)
    if not get_m:
        return None
    rest = body[get_m.end():].lstrip()
    if not rest.startswith("{"):
        return None
    get_body = extract_brace_block(rest, 0)

    set_m = re.search(r'\bset\s*\(([^)]*)\)', body)
    set_body = None
    set_params = ""
    if set_m:
        set_params = set_m.group(1)
        rest2 = body[set_m.end():].lstrip()
        if rest2.startswith("{"):
            set_body = extract_brace_block(rest2, 0)

    return {"get_body": get_body, "set_body": set_body, "set_params": set_params}


def generate_getter_setter_computed(
    name: str,
    gs: dict,
    ref_members: list[str],
    plain_members: list[str],
    indent: str,
) -> str:
    """Generate a writable computed() call from getter/setter parts."""
    get_body = textwrap.dedent(gs["get_body"]).strip()
    get_rewritten = rewrite_this_refs(get_body, ref_members, plain_members)

    parts = [f"{indent}const {name} = computed({{"]
    parts.append(f"{indent}  get: () => {{ {get_rewritten} }},")

    if gs["set_body"]:
        set_body = textwrap.dedent(gs["set_body"]).strip()
        set_rewritten = rewrite_this_refs(set_body, ref_members, plain_members)
        set_params = gs["set_params"]
        parts.append(f"{indent}  set: ({set_params}) => {{ {set_rewritten} }},")

    parts.append(f"{indent}}})")
    return "\n".join(parts)


def _extract_watch_section_body(mixin_source: str) -> str:
    """Return the content of `watch: { ... }` from a mixin, or empty string."""
    m = re.search(r'\bwatch\s*:\s*\{', mixin_source)
    if not m:
        return ""
    return extract_brace_block(mixin_source, m.end() - 1)


def parse_watch_entry(watch_body: str, name: str) -> dict | None:
    """Parse a single watch entry from the watch section body.

    Returns a dict with keys:
      - params: str (parameter list)
      - body: str (handler function body)
      - options: dict (deep, immediate, etc.)
      - complex: bool (True if string/array handler — can't auto-convert)

    Returns None if the entry can't be found.
    """
    m = re.search(rf'\b{re.escape(name)}\s*(?:\(|:)', watch_body)
    if not m:
        return None

    after_name = watch_body[m.end() - 1:]

    # Form 1: shorthand — name(params) { body }
    if after_name[0] == "(":
        params_m = re.match(r'\(([^)]*)\)', after_name)
        if params_m:
            params = params_m.group(1)
            rest = after_name[params_m.end():].lstrip()
            if rest.startswith("{"):
                body = extract_brace_block(rest, 0)
                return {"params": params, "body": body, "options": {}, "complex": False}

    # After the colon
    if after_name[0] == ":":
        value_start = after_name[1:].lstrip()

        # String handler — name: 'methodName'
        if value_start and value_start[0] in ("'", '"'):
            return {"params": "", "body": "", "options": {}, "complex": True}

        # Array handler — name: [handler1, handler2]
        if value_start and value_start[0] == "[":
            return {"params": "", "body": "", "options": {}, "complex": True}

        # Function property — name: function(params) { body }
        func_m = re.match(r'function\s*\(([^)]*)\)', value_start)
        if func_m:
            params = func_m.group(1)
            rest = value_start[func_m.end():].lstrip()
            if rest.startswith("{"):
                body = extract_brace_block(rest, 0)
                return {"params": params, "body": body, "options": {}, "complex": False}

        # Options object — name: { handler(params) { body }, deep: true }
        if value_start and value_start[0] == "{":
            obj_body = extract_brace_block(value_start, 0)
            handler_m = re.search(r'\bhandler\s*\(([^)]*)\)', obj_body)
            if handler_m:
                params = handler_m.group(1)
                rest = obj_body[handler_m.end():].lstrip()
                if rest.startswith("{"):
                    body = extract_brace_block(rest, 0)
                    options = {}
                    for opt in ("deep", "immediate", "flush"):
                        opt_m = re.search(rf'\b{opt}\s*:\s*(\w+)', obj_body)
                        if opt_m:
                            options[opt] = opt_m.group(1)
                    return {"params": params, "body": body, "options": options, "complex": False}

    return None


def generate_watch_call(
    name: str,
    watch_entry: dict,
    ref_members: list[str],
    plain_members: list[str],
    indent: str,
) -> str:
    """Generate a watch() call from a parsed watch entry."""
    params = watch_entry["params"]
    body = textwrap.dedent(watch_entry["body"]).strip()
    rewritten = rewrite_this_refs(body, ref_members, plain_members)
    options = watch_entry["options"]

    options_str = ""
    if options:
        opts = ", ".join(f"{k}: {v}" for k, v in options.items())
        options_str = f", {{ {opts} }}"

    lines = rewritten.splitlines()
    if len(lines) <= 1:
        return f"{indent}watch({name}, ({params}) => {{ {rewritten} }}{options_str})"

    inner = indent + indent
    body_lines = "\n".join(f"{inner}{line}" for line in lines)
    return f"{indent}watch({name}, ({params}) => {{\n{body_lines}\n{indent}}}{options_str})"


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
        body = extract_hook_body(mixin_source, name, exclude_sections=False)
        # Getter/setter computed — auto-convert
        if body and re.search(r'\bget\s*\(', body):
            gs = parse_getter_setter_computed(body)
            if gs:
                return generate_getter_setter_computed(name, gs, ref_members, plain_members, indent)
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
        body = extract_hook_body(mixin_source, name, exclude_sections=False)
        if body:
            body_clean = textwrap.dedent(body).strip()
            rewritten = rewrite_this_refs(body_clean, ref_members, plain_members)
            inner = indent + indent
            body_lines = f"\n{inner}" + f"\n{inner}".join(rewritten.splitlines()) + f"\n{indent}"
            # Detect async
            async_match = re.search(rf'\basync\s+{re.escape(name)}\b', mixin_source)
            async_prefix = "async " if async_match else ""
            return f"{indent}{async_prefix}function {name}({params}) {{{body_lines}}}"
        return f"{indent}function {name}({params}) {{}} // TODO: implement"

    if name in mixin_members.watch:
        watch_body = _extract_watch_section_body(mixin_source)
        entry = parse_watch_entry(watch_body, name) if watch_body else None
        if entry and not entry["complex"]:
            return generate_watch_call(name, entry, ref_members, plain_members, indent)
        return f"{indent}// watch: {name} — migrate manually"

    return f"{indent}// {name} — could not classify, migrate manually"


def _missing_hooks(composable_src: str, hooks: list[str]) -> list[str]:
    """Return lifecycle hooks not yet present in the composable source.

    For wrapped hooks (onMounted etc.), checks for ``fnName(`` to detect calls.
    Inline hooks (beforeCreate/created) are always considered missing since
    there's no reliable wrapper to detect.
    """
    missing: list[str] = []
    for hook in hooks:
        vue3_fn = HOOK_MAP.get(hook)
        if vue3_fn is None:
            # beforeCreate/created — inline, always treat as missing
            missing.append(hook)
        elif f"{vue3_fn}(" not in composable_src:
            missing.append(hook)
    return missing


def patch_composable(
    composable_content: str,
    mixin_content: str,
    not_returned: list[str],
    missing: list[str],
    mixin_members: MixinMembers,
    lifecycle_hooks: list[str] | None = None,
    indent: str = "  ",
) -> str:
    """Orchestrate composable patching for both blocked cases.

    R-6: If the composable uses reactive(), skip auto-patching and warn.

    Step 1 (not_returned): Add keys to the return statement.
    Step 2 (missing): Generate declarations and insert before return,
                      then add the names to the return statement.
    Step 3 (lifecycle_hooks): Convert and insert lifecycle hooks that the
                              composable doesn't already contain.

    Returns modified composable content (unchanged if reactive() guard triggered).
    """
    # R-6: reactive() guard
    if 'reactive(' in composable_content:
        print(
            "  [composable_patcher] WARNING: Composable uses reactive() -- "
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

    # Step 3: add lifecycle hooks not yet present in the composable
    if lifecycle_hooks:
        hooks_to_add = _missing_hooks(content, lifecycle_hooks)
        if hooks_to_add:
            inline_lines, wrapped_lines = convert_lifecycle_hooks(
                mixin_content, hooks_to_add, ref_members, plain_members, indent,
            )
            hook_lines = inline_lines + wrapped_lines
            if hook_lines:
                content = add_members_to_composable(content, hook_lines)
            for imp in get_required_imports(hooks_to_add):
                content = _add_vue_import(content, imp)

    # Apply this.$ auto-rewrites ($nextTick, $set, $delete)
    content, dollar_imports = rewrite_this_dollar_refs(content)
    for imp in dollar_imports:
        content = _add_vue_import(content, imp)

    # Collect warnings and inject inline comments + confidence header
    warnings = collect_mixin_warnings(mixin_content, mixin_members, lifecycle_hooks or [])
    confidence = compute_confidence(content, warnings)
    content = inject_inline_warnings(content, warnings, confidence, len(warnings))

    return content
