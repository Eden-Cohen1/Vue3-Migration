"""Patch existing composables to fix BLOCKED_NOT_RETURNED and BLOCKED_MISSING_MEMBERS."""
import re
import textwrap
from pathlib import Path
from ..core.composable_analyzer import extract_declared_identifiers
from ..core.js_parser import extract_brace_block, extract_value_at
from ..core.mixin_analyzer import extract_mixin_imports, filter_imports_by_usage, rewrite_import_path
from ..core.warning_collector import (
    collect_mixin_warnings, compute_confidence, inject_inline_warnings,
    suppress_resolved_warnings,
)
from ..models import MixinMembers
from .this_rewriter import rewrite_this_refs, rewrite_this_dollar_refs, rewrite_this_i18n_refs
from .lifecycle_converter import (
    extract_hook_body, convert_lifecycle_hooks, get_required_imports, HOOK_MAP,
    find_lifecycle_referenced_members,
)


def _remove_stale_comments(source: str) -> str:
    """Remove stale 'NOT defined' / 'NOT returned' comments that contradict the actual code.

    When the patcher adds a member that was previously missing, any inline comments
    saying it is 'NOT defined' or 'NOT returned' become stale and misleading.
    This function detects such contradictions and removes the stale comment lines.
    """
    lines = source.split('\n')
    result_lines = []

    for line in lines:
        # Check for "NOT defined" or "NOT returned" comments
        # Match patterns like: "count is NOT defined", "count NOT returned",
        # "count is NOT returned", "canDelete and hasRole are NOT defined"
        not_match = re.search(r'//.*?\b(\w+)\s+(?:(?:is|are)\s+)?NOT\s+(?:defined|returned)', line)
        if not_match:
            # Extract all lowercase-starting identifiers before "NOT" in the comment
            comment_start = line.index('//')
            comment_text = line[comment_start:]
            not_word = re.search(r'\bNOT\b', comment_text)
            not_pos = not_word.start() if not_word else comment_text.index('NOT')
            before_not = comment_text[:not_pos]
            noise = {'is', 'are', 'and', 'or', 'not', 'in', 'this', 'composable', 'the', 'from'}
            identifiers = [m for m in re.findall(r'\b([a-z]\w*)\b', before_not) if m not in noise]

            if identifiers:
                # All mentioned identifiers must be defined for the comment to be stale
                all_defined = all(
                    re.search(rf'\b(?:const|let|var|function)\s+{re.escape(name)}\b', source)
                    or re.search(rf'\breturn\s*\{{[^}}]*\b{re.escape(name)}\b', source, re.DOTALL)
                    for name in identifiers
                )
                if all_defined:
                    continue  # Remove stale comment
            else:
                # Fallback to single-member logic
                member_name = not_match.group(1)
                if member_name.upper() == member_name and len(member_name) > 2:
                    result_lines.append(line)
                    continue
                is_defined = (
                    re.search(rf'\b(?:const|let|var|function)\s+{re.escape(member_name)}\b', source)
                    or re.search(rf'\breturn\s*\{{[^}}]*\b{re.escape(member_name)}\b', source, re.DOTALL)
                )
                if is_defined:
                    continue

        result_lines.append(line)

    return '\n'.join(result_lines)


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


def _add_keys_to_indirect_return(content: str, keys: list[str]) -> str:
    """Handle indirect return pattern: ``const obj = { ... }; return obj``.

    Finds ``return varName``, locates the variable's object literal, and adds
    missing keys to that literal.  Falls back to a warning if no match.
    """
    noise = {"const", "let", "var", "function", "return", "true", "false",
             "null", "undefined", "new", "value"}
    ret_var = re.search(r'\breturn\s+(\w+)\s*;?\s*$', content, re.MULTILINE)
    if not ret_var or ret_var.group(1) in noise:
        print(
            "  [composable_patcher] WARNING: No 'return {' found. "
            "Composable may use a variable return -- manual migration required."
        )
        return content
    var_name = ret_var.group(1)
    var_def = re.search(
        rf'\b(?:const|let|var)\s+{re.escape(var_name)}\s*=\s*\{{',
        content,
    )
    if not var_def:
        print(
            f"  [composable_patcher] WARNING: Could not find definition of '{var_name}'. "
            "Manual migration required."
        )
        return content
    # Reuse add_keys_to_return on a synthetic direct-return form:
    # We treat the variable assignment's object literal the same way.
    brace_start = var_def.end() - 1
    obj_block = extract_brace_block(content, brace_start)
    existing = set(re.findall(r'\b(\w+)\b', obj_block))
    new_keys = [k for k in keys if k not in existing]
    if not new_keys:
        return content
    # Find closing brace
    depth = 0
    close_pos = brace_start
    for i in range(brace_start, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                close_pos = i
                break
    full_obj = content[var_def.start():close_pos + 1]
    # Detect indentation of the variable line
    line_start = content.rfind('\n', 0, var_def.start()) + 1
    var_indent = content[line_start:var_def.start()]
    is_multiline = '\n' in full_obj
    if is_multiline:
        member_indent = var_indent + "  "
        for line in full_obj.splitlines()[1:]:
            stripped = line.lstrip()
            if stripped and not stripped.startswith('}'):
                member_indent = line[:len(line) - len(stripped)]
                break
        before_close = content[:close_pos].rstrip()
        if before_close and before_close[-1] not in (',', '{'):
            before_close += ','
        line_start_of_close = content.rfind('\n', 0, close_pos)
        close_indent = content[line_start_of_close + 1:close_pos] if line_start_of_close >= 0 else ''
        new_key_lines = "\n".join(f"{member_indent}{k}," for k in new_keys)
        return before_close + "\n" + new_key_lines + "\n" + close_indent + content[close_pos:]
    else:
        inner = obj_block[1:-1].strip()
        all_items = inner + ", " + ", ".join(new_keys) if inner else ", ".join(new_keys)
        # Rebuild the single-line object literal with new keys
        new_obj = f"{{ {all_items} }}"
        return content[:brace_start] + new_obj + content[close_pos + 1:]


def add_keys_to_return(content: str, keys: list[str]) -> str:
    """Add missing keys to the composable's return { } statement.

    Uses the LAST return statement (Risk R-3: avoids patching early-exit returns).
    Skips keys already present (idempotent).
    Returns content unchanged if no 'return {' statement is found (Risk R-4).

    When the return statement is multi-line, new keys are added on their own
    lines matching the existing indentation. When single-line and adding keys
    would exceed 80 characters, the return is converted to multi-line.
    """
    matches = list(re.finditer(r'\breturn\s*\{', content))
    if not matches:
        # Case 2: indirect return — return varName where varName = { ... }
        return _add_keys_to_indirect_return(content, keys)
    m = matches[-1]  # use LAST return (R-3 fix)
    return_block = extract_brace_block(content, m.end() - 1)
    existing = set(re.findall(r'\b(\w+)\b', return_block))
    new_keys = [k for k in keys if k not in existing]
    if not new_keys:
        return content

    # Determine the full span of the return statement (from 'return' to closing '}')
    brace_start = m.end() - 1
    # Find the closing brace by counting
    depth = 0
    close_pos = brace_start
    for i in range(brace_start, len(content)):
        if content[i] == '{':
            depth += 1
        elif content[i] == '}':
            depth -= 1
            if depth == 0:
                close_pos = i
                break
    full_return = content[m.start():close_pos + 1]

    # Detect return indentation (leading whitespace of the return line)
    line_start = content.rfind('\n', 0, m.start()) + 1
    return_indent = content[line_start:m.start()]

    # Check if the existing return is multi-line
    is_multiline = '\n' in full_return

    if is_multiline:
        # Multi-line return: detect the member indentation from existing lines
        return_lines = full_return.splitlines()
        # Find indentation of existing members (lines between { and })
        member_indent = return_indent + "  "
        for line in return_lines[1:]:
            stripped = line.lstrip()
            if stripped and not stripped.startswith('}'):
                member_indent = line[:len(line) - len(stripped)]
                break

        # Strip trailing whitespace before closing }, add comma if needed
        before_close = content[:close_pos].rstrip()
        if before_close and before_close[-1] not in (',', '{'):
            before_close += ','

        # Detect the closing brace's indentation from the original content
        line_start_of_close = content.rfind('\n', 0, close_pos)
        if line_start_of_close >= 0:
            close_indent = content[line_start_of_close + 1:close_pos]
        else:
            close_indent = ''

        # Insert new keys between last member and closing }
        new_key_lines = "\n".join(f"{member_indent}{k}," for k in new_keys)
        return before_close + "\n" + new_key_lines + "\n" + close_indent + content[close_pos:]
    else:
        # Single-line return: check if adding keys would make it too long
        # Extract existing keys from the return block content
        inner = return_block[1:-1].strip()  # strip { and }
        all_items = inner + ", " + ", ".join(new_keys) if inner else ", ".join(new_keys)
        candidate_line = f"{return_indent}return {{ {all_items} }}"
        if len(candidate_line) <= 80:
            # Keep single-line, insert new keys
            insert_pos = m.end()
            prefix = " " + ", ".join(new_keys) + ","
            return content[:insert_pos] + prefix + content[insert_pos:]
        else:
            # Convert to multi-line
            member_indent = return_indent + "  "
            # Parse existing items from inner
            existing_items = [item.strip().rstrip(',') for item in inner.split(',') if item.strip()]
            all_items_list = existing_items + new_keys
            members_block = "".join(f"{member_indent}{item},\n" for item in all_items_list)
            new_return = f"return {{\n{members_block}{return_indent}}}"
            return content[:m.start()] + new_return + content[close_pos + 1:]


def add_members_to_composable(content: str, member_lines: list[str]) -> str:
    """Insert new member declarations just before the return statement.

    Skips any line whose declared name already appears in the composable (idempotent).
    Returns content unchanged if no return statement is found.
    """
    # Normalize CRLF (R-7)
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    matches = list(re.finditer(r'\n([ \t]*)\breturn\s*\{', content))
    if not matches:
        # Fallback: indirect return (return varName) — insert before return line
        matches = list(re.finditer(r'\n([ \t]*)\breturn\s+\w+', content))
        if not matches:
            return content
    m = matches[-1]
    existing_ids = set(extract_declared_identifiers(content))
    lines_to_add = []
    in_block = False  # True when we're adding a multi-line block (e.g. lifecycle hook)
    for line in member_lines:
        name_match = re.search(r'\b(?:const|let|var|function)\s+(\w+)', line)
        if name_match:
            in_block = name_match.group(1) not in existing_ids
            if in_block:
                lines_to_add.append(line)
        else:
            # No extractable name — could be a lifecycle hook opener or continuation line.
            # Check if this starts a new block (e.g. "onMounted(() => {")
            hook_match = re.match(r'\s*(on\w+)\s*\(', line)
            if hook_match:
                # Lifecycle hook opener — check if this exact hook is already in content
                in_block = not re.search(rf'\b{re.escape(hook_match.group(1))}\s*\(', content)
                if in_block:
                    lines_to_add.append(line)
            elif in_block:
                # Continuation of a block being added (body lines, closing braces)
                lines_to_add.append(line)
            else:
                # Standalone line (e.g. inline hook body) — add if significant content not present
                stripped = line.strip()
                if stripped and not stripped.startswith('//') and stripped not in content:
                    lines_to_add.append(line)
                elif not stripped or stripped.startswith('//'):
                    # Blank lines and comments — always add
                    lines_to_add.append(line)
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
    # For dotted names (e.g. 'nested.path'), search for the quoted form
    if '.' in name:
        m = re.search(
            rf"""(?:['"]){re.escape(name)}(?:['"])\s*(?:\(|:)""",
            watch_body,
        )
    else:
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
            str_match = re.match(r"""^(['"])(\w+)\1""", value_start)
            if str_match:
                method_name = str_match.group(2)
                return {
                    "params": "",
                    "body": f"{method_name}()",
                    "options": {},
                    "complex": False,
                }
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

        # Options object — name: { handler(...) { body }, deep: true }
        if value_start and value_start[0] == "{":
            obj_body = extract_brace_block(value_start, 0)
            # Try multiple handler forms:
            #   handler(params) { ... }           — shorthand
            #   handler: function(params) { ... } — function expression
            #   handler: (params) => { ... }      — arrow function
            handler_m = re.search(
                r'\bhandler\s*(?::\s*(?:function\s*)?)?\(([^)]*)\)',
                obj_body,
            )
            if handler_m:
                params = handler_m.group(1)
                rest = obj_body[handler_m.end():].lstrip()
                # Skip arrow `=>` if present
                if rest.startswith("=>"):
                    rest = rest[2:].lstrip()
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

    # For dotted watch keys like 'nested.path', generate a getter function:
    #   watch(() => nested.value.path, ...)
    if '.' in name:
        parts = name.split('.')
        root = parts[0]
        rest = '.'.join(parts[1:])
        watch_source = f"() => {root}.value.{rest}"
    else:
        watch_source = name

    lines = rewritten.splitlines()
    if len(lines) <= 1:
        return f"{indent}watch({watch_source}, ({params}) => {{ {rewritten} }}{options_str})"

    inner = indent + indent
    body_lines = "\n".join(f"{inner}{line}" for line in lines)
    return f"{indent}watch({watch_source}, ({params}) => {{\n{body_lines}\n{indent}}}{options_str})"


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
            rewritten_lines = rewritten.strip().splitlines()
            # Check if it's a single return statement (can use arrow shorthand)
            if len(rewritten_lines) == 1 and rewritten_lines[0].strip().startswith("return "):
                expr = rewritten_lines[0].strip()[len("return "):].rstrip(";").strip()
                return f"{indent}const {name} = computed(() => {expr})"
            else:
                # Multi-line body: use block form with proper indentation
                inner = indent + indent
                indented_body = f"\n{inner}" + f"\n{inner}".join(rewritten_lines) + f"\n{indent}"
                return f"{indent}const {name} = computed(() => {{{indented_body}}})"
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


def _inline_body_present(composable_src: str, hook_body: str) -> bool:
    """Check if the significant statements from a hook body are already in the composable."""
    lines = textwrap.dedent(hook_body).strip().splitlines()
    significant = [l.strip() for l in lines if l.strip() and not l.strip().startswith('//')]
    if not significant:
        return False
    return all(line in composable_src for line in significant)


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
    mixin_path: Path | None = None,
    composable_path: Path | None = None,
    project_root: "Path | None" = None,
) -> str:
    """Orchestrate composable patching for both blocked cases.

    R-6: If the composable uses reactive(), skip auto-patching and warn.

    Step 1 (not_returned): Add keys to the return statement.
    Step 2 (missing): Generate declarations and insert before return,
                      then add the names to the return statement.
    Step 3 (lifecycle_hooks): Convert and insert lifecycle hooks that the
                              composable doesn't already contain.

    Returns modified composable content.
    """
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

        # Add required imports for generated declarations
        if any("watch(" in d for d in declarations):
            content = _add_vue_import(content, "watch")
        if any("ref(" in d for d in declarations):
            content = _add_vue_import(content, "ref")
        if any("computed(" in d for d in declarations):
            content = _add_vue_import(content, "computed")

    # Step 3: add lifecycle hooks not yet present in the composable
    if lifecycle_hooks:
        hooks_to_add = _missing_hooks(content, lifecycle_hooks)
        # Filter out inline hooks (created/beforeCreate) whose body is already present
        filtered = []
        for hook in hooks_to_add:
            if HOOK_MAP.get(hook) is None:
                body = extract_hook_body(mixin_content, hook)
                if body:
                    # Check with rewritten body (this.x → x.value / x())
                    rewritten_body = rewrite_this_refs(body, ref_members, plain_members)
                    if _inline_body_present(content, rewritten_body):
                        continue
            filtered.append(hook)
        hooks_to_add = filtered
        if hooks_to_add:
            # Step 3a: Find mixin members referenced inside lifecycle hook bodies
            # that are not yet in the composable (e.g. _handleEscapeKey).
            all_member_names = (
                mixin_members.data + mixin_members.computed
                + mixin_members.methods + mixin_members.watch
            )
            lifecycle_deps = find_lifecycle_referenced_members(
                mixin_content, hooks_to_add, all_member_names,
            )
            existing_ids = set(extract_declared_identifiers(content))
            missing_deps = [m for m in lifecycle_deps if m not in existing_ids]
            if missing_deps:
                dep_decls = [
                    generate_member_declaration(
                        name, mixin_content, mixin_members,
                        ref_members, plain_members, indent,
                    )
                    for name in missing_deps
                ]
                content = add_members_to_composable(content, dep_decls)
                content = add_keys_to_return(content, missing_deps)
                if any("watch(" in d for d in dep_decls):
                    content = _add_vue_import(content, "watch")
                if any("ref(" in d for d in dep_decls):
                    content = _add_vue_import(content, "ref")
                if any("computed(" in d for d in dep_decls):
                    content = _add_vue_import(content, "computed")

            # Step 3b: Convert and insert lifecycle hooks
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

    # Apply this.$t/$tc/$te/$d/$n auto-rewrites to useI18n() equivalents
    content, i18n_functions = rewrite_this_i18n_refs(content)
    if i18n_functions:
        sorted_fns = sorted(i18n_functions)
        # Add import { useI18n } from 'vue-i18n' if not already present
        if "useI18n" not in content:
            # Insert after the Vue import line
            vue_import_m = re.search(r"import\s*\{[^}]*\}\s*from\s*['\"]vue['\"].*\n", content)
            if vue_import_m:
                insert_pos = vue_import_m.end()
                content = content[:insert_pos] + "import { useI18n } from 'vue-i18n'\n" + content[insert_pos:]
            else:
                content = "import { useI18n } from 'vue-i18n'\n" + content
        # Add const { t, ... } = useI18n() if not already present
        if "useI18n()" not in content or "= useI18n()" not in content:
            # Find the opening of the composable function body
            fn_m = re.search(r'export\s+function\s+\w+\s*\([^)]*\)\s*\{', content)
            if fn_m:
                insert_pos = fn_m.end()
                destructure = f"\n{indent}const {{ {', '.join(sorted_fns)} }} = useI18n()\n"
                content = content[:insert_pos] + destructure + content[insert_pos:]

    # Propagate non-Vue imports from mixin source
    if mixin_path is not None:
        mixin_imports = extract_mixin_imports(mixin_content)
        used_imports = filter_imports_by_usage(mixin_imports, content)
        mixin_dir = mixin_path.parent
        composable_dir = composable_path.parent if composable_path else mixin_dir
        for imp in used_imports:
            rewritten_line = rewrite_import_path(imp["line"], mixin_dir, composable_dir)
            # Skip if any identifier from this import already appears in an existing import line
            already_present = any(
                re.search(rf"\b{re.escape(name)}\b", line)
                for name in imp["identifiers"]
                for line in content.split("\n")
                if line.strip().startswith("import ")
            )
            if not already_present:
                content = rewritten_line + "\n" + content

    # Remove stale "NOT defined" / "NOT returned" comments that contradict actual code
    content = _remove_stale_comments(content)

    # Collect warnings and suppress those already resolved by the generated code
    warnings = collect_mixin_warnings(
        mixin_content, mixin_members, lifecycle_hooks or [],
        mixin_path=mixin_path, project_root=project_root,
    )
    warnings = suppress_resolved_warnings(warnings, [], content)
    confidence = compute_confidence(content, warnings)
    content = inject_inline_warnings(content, warnings, confidence, len(warnings))

    return content
