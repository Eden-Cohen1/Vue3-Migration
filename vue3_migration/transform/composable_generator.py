"""Generate a new Vue 3 composable file from a Vue 2 mixin source."""
import re
import textwrap
from ..core.js_parser import extract_brace_block
from ..core.warning_collector import (
    collect_mixin_warnings, compute_confidence, inject_inline_warnings,
)
from ..models import MigrationWarning, MixinMembers
from .composable_patcher import (
    _extract_data_default,
    _extract_watch_section_body,
    parse_watch_entry,
    generate_watch_call,
    parse_getter_setter_computed,
    generate_getter_setter_computed,
)
from .lifecycle_converter import convert_lifecycle_hooks, get_required_imports
from .this_rewriter import rewrite_this_refs, rewrite_this_dollar_refs


def _extract_section_body(mixin_source: str, section: str) -> str:
    """Return the content of `section: { ... }` from a mixin, or empty string."""
    m = re.search(rf'\b{re.escape(section)}\s*:\s*\{{', mixin_source)
    if not m:
        return ""
    return extract_brace_block(mixin_source, m.end() - 1)


def _extract_func_body(section_body: str, name: str) -> str | None:
    """Extract the body of a named function from inside an object section body.

    Works by calling extract_hook_body on just the section content so the
    R-2 exclusion (which excludes methods/computed blocks when parsing the
    full mixin source) does not fire.
    """
    from .lifecycle_converter import extract_hook_body
    return extract_hook_body(section_body, name)


def _extract_func_params(section_body: str, name: str) -> str:
    """Extract the parameter list of a named function inside a section body."""
    m = re.search(rf'\b{re.escape(name)}\s*\(([^)]*)\)', section_body)
    return m.group(1) if m else ""


def _is_async(section_body: str, name: str) -> bool:
    """Check if a named function in a section body is declared async."""
    return bool(re.search(rf'\basync\s+{re.escape(name)}\b', section_body))


def mixin_stem_to_composable_name(stem: str) -> str:
    """Convert a mixin file stem to a Vue 3 composable function name.

    Examples:
        authMixin      -> useAuth
        selectionMixin -> useSelection
        auth           -> useAuth
        paginationmixin -> usePagination
    """
    base = re.sub(r'[Mm]ixin$', '', stem).strip()
    if not base:
        base = stem
    return 'use' + base[0].upper() + base[1:]


def generate_composable_from_mixin(
    mixin_source: str,
    mixin_stem: str,
    mixin_members: MixinMembers,
    lifecycle_hooks: list[str],
    indent: str = "  ",
) -> str:
    """Generate a complete Vue 3 composable file from a mixin.

    Produces:
    - Vue imports (ref, computed, lifecycle hooks as needed)
    - export function useXxx() { ... }
      - data     -> const name = ref(<default>)
      - computed -> const name = computed(() => { ... })
      - methods  -> function name(...) { ... }
      - watch    -> // watch: name — migrate manually
      - lifecycle (created/beforeCreate) inlined directly in function body
      - lifecycle (mounted/etc) wrapped in onMounted(() => { ... })
    - return { all members }
    """
    fn_name = mixin_stem_to_composable_name(mixin_stem)
    ref_members = mixin_members.data + mixin_members.computed + mixin_members.watch
    plain_members = mixin_members.methods

    methods_body = _extract_section_body(mixin_source, "methods")
    computed_body = _extract_section_body(mixin_source, "computed")

    # Generate member declarations using section-aware extraction
    decl_lines: list[str] = []

    for name in mixin_members.data:
        default = _extract_data_default(mixin_source, name)
        decl_lines.append(f"{indent}const {name} = ref({default})")

    if mixin_members.data and (mixin_members.computed or mixin_members.methods or mixin_members.watch):
        decl_lines.append("")

    for name in mixin_members.computed:
        body = _extract_func_body(computed_body, name) if computed_body else None
        if body and re.search(r'\bget\s*\(', body):
            gs = parse_getter_setter_computed(body)
            if gs:
                decl_lines.append(generate_getter_setter_computed(name, gs, ref_members, plain_members, indent))
            else:
                decl_lines.append(f"{indent}const {name} = computed(() => null) // TODO: getter/setter computed — migrate manually")
        elif body:
            rewritten = rewrite_this_refs(body.strip(), ref_members, plain_members)
            decl_lines.append(f"{indent}const {name} = computed(() => {{ {rewritten} }})")
        else:
            decl_lines.append(f"{indent}const {name} = computed(() => null) // TODO: implement")

    if mixin_members.computed and (mixin_members.methods or mixin_members.watch):
        decl_lines.append("")

    for name in mixin_members.methods:
        params = _extract_func_params(methods_body, name) if methods_body else ""
        body = _extract_func_body(methods_body, name) if methods_body else None
        if body:
            body_clean = textwrap.dedent(body).strip()
            rewritten = rewrite_this_refs(body_clean, ref_members, plain_members)
            inner = indent + indent
            body_lines = f"\n{inner}" + f"\n{inner}".join(rewritten.splitlines()) + f"\n{indent}"
            async_prefix = "async " if _is_async(methods_body, name) else ""
            decl_lines.append(f"{indent}{async_prefix}function {name}({params}) {{{body_lines}}}")
        else:
            decl_lines.append(f"{indent}function {name}({params}) {{}} // TODO: implement")

    if mixin_members.methods and mixin_members.watch:
        decl_lines.append("")

    watch_section = _extract_watch_section_body(mixin_source)
    has_auto_watch = False
    for name in mixin_members.watch:
        entry = parse_watch_entry(watch_section, name) if watch_section else None
        if entry and not entry["complex"]:
            decl_lines.append(generate_watch_call(name, entry, ref_members, plain_members, indent))
            has_auto_watch = True
        else:
            decl_lines.append(f"{indent}// watch: {name} — migrate manually")

    # Convert lifecycle hooks
    inline_lines, wrapped_lines = convert_lifecycle_hooks(
        mixin_source, lifecycle_hooks, ref_members, plain_members, indent
    )

    # Reference check: scan lifecycle hook bodies for method references
    # that are in mixin_members.methods. Verify they were generated.
    from .lifecycle_converter import extract_hook_body
    _generated_method_names = set(mixin_members.methods)
    _lifecycle_ref_warnings: list[str] = []
    for hook in lifecycle_hooks:
        hook_body = extract_hook_body(mixin_source, hook)
        if not hook_body:
            continue
        for method_name in mixin_members.methods:
            if re.search(rf"(?<!\w){re.escape(method_name)}(?!\w)", hook_body):
                # Check if method was actually generated (has body in decl_lines)
                method_generated = any(
                    f"function {method_name}(" in line for line in decl_lines
                )
                if not method_generated:
                    _lifecycle_ref_warnings.append(
                        f"Lifecycle hook '{hook}' references method '{method_name}' "
                        f"but it was not generated in the composable."
                    )

    # Determine Vue imports needed
    vue_imports: list[str] = []
    if mixin_members.data or mixin_members.watch:
        vue_imports.append("ref")
    if mixin_members.computed:
        vue_imports.append("computed")
    if has_auto_watch:
        vue_imports.append("watch")
    for hook_fn in get_required_imports(lifecycle_hooks, mixin_source):
        if hook_fn not in vue_imports:
            vue_imports.append(hook_fn)

    # Assemble body
    body_parts: list[str] = []
    body_parts.extend(decl_lines)
    if inline_lines:
        if decl_lines and decl_lines[-1] != "":
            body_parts.append("")
        body_parts.extend(inline_lines)
    if wrapped_lines:
        if body_parts and body_parts[-1] != "":
            body_parts.append("")
        body_parts.extend(wrapped_lines)
    if body_parts and body_parts[-1] != "":
        body_parts.append("")

    # Return statement
    all_members = mixin_members.all_names
    return_items = ", ".join(all_members)
    body_parts.append(f"{indent}return {{ {return_items} }}")

    body = "\n".join(body_parts)

    # Post-generation validation: check lifecycle hooks are not nested inside
    # computed/method blocks (brace depth > 0 relative to function body)
    _lifecycle_calls = (
        "onMounted(", "onBeforeUnmount(", "onActivated(", "onDeactivated(",
        "onUpdated(", "onBeforeMount(", "onUnmounted(", "onBeforeUpdate(",
        "onErrorCaptured(",
    )
    _nested_lifecycle_warnings: list[str] = []
    depth = 0
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        else:
            for lc in _lifecycle_calls:
                if body[i:i + len(lc)] == lc and depth > 0:
                    _nested_lifecycle_warnings.append(
                        f"MIGRATION: {lc[:-1]}) appears nested at brace depth {depth} "
                        f"— it should be at top-level scope of the composable."
                    )
        i += 1

    # Apply this.$ auto-rewrites ($nextTick, $set, $delete)
    body, dollar_imports = rewrite_this_dollar_refs(body)
    for imp in dollar_imports:
        if imp not in vue_imports:
            vue_imports.append(imp)

    # Assemble full file
    import_line = (
        f"import {{ {', '.join(vue_imports)} }} from 'vue'\n\n"
        if vue_imports else ""
    )
    result = f"{import_line}export function {fn_name}() {{\n{body}\n}}\n"

    # Collect warnings and inject inline comments + confidence header
    warnings = collect_mixin_warnings(mixin_source, mixin_members, lifecycle_hooks)

    # Add nested-lifecycle warnings from post-generation validation
    for msg in _nested_lifecycle_warnings:
        warnings.append(MigrationWarning(
            mixin_stem="",
            category="nested-lifecycle",
            message=msg,
            action_required="Move lifecycle hook call to top-level scope of composable",
            line_hint=None,
            severity="warning",
        ))

    # Add lifecycle method reference warnings
    for msg in _lifecycle_ref_warnings:
        warnings.append(MigrationWarning(
            mixin_stem="",
            category="missing-lifecycle-method",
            message=msg,
            action_required="Ensure the referenced method is included in the composable",
            line_hint=None,
            severity="warning",
        ))

    # Add missing cleanup warnings
    from ..core.warning_collector import detect_missing_cleanup
    cleanup_warnings = detect_missing_cleanup(result)
    for msg in cleanup_warnings:
        warnings.append(MigrationWarning(
            mixin_stem="",
            category="missing-cleanup",
            message=msg,
            action_required="Add cleanup code in onBeforeUnmount",
            line_hint=None,
            severity="warning",
        ))

    confidence = compute_confidence(result, warnings)
    result = inject_inline_warnings(result, warnings, confidence, len(warnings))

    return result
