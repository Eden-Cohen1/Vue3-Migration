"""Generate a new Vue 3 composable file from a Vue 2 mixin source."""
import re
import textwrap
from pathlib import Path
from ..core.js_parser import extract_brace_block
from ..core.mixin_analyzer import (
    extract_mixin_imports, filter_imports_by_usage, rewrite_import_path,
    extract_member_line_ranges, find_internal_private_props,
)
from ..core.warning_collector import (
    collect_mixin_warnings, compute_confidence, inject_inline_warnings,
    suppress_resolved_warnings, suppress_covered_member_warnings,
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
from .this_rewriter import rewrite_this_refs, rewrite_this_dollar_refs, rewrite_this_i18n_refs


def _extract_factory_params(mixin_source: str) -> str:
    """Extract parameters from a factory function mixin signature.

    For `export default function createFoo(x, y = 1) { return { ... } }`,
    returns 'x, y = 1'.  Returns '' for non-factory mixins.
    """
    m = re.search(r'\bexport\s+default\s+function\s*\w*\s*\(([^)]*)\)', mixin_source)
    return m.group(1).strip() if m else ""


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

    Falls back to explicit pattern matching for function expressions and
    arrow functions if extract_hook_body returns None.
    """
    from .lifecycle_converter import extract_hook_body
    result = extract_hook_body(section_body, name)
    if result is not None:
        return result

    # Fallback: try name: function(...) { ... } pattern
    m = re.search(rf'\b{re.escape(name)}\s*:\s*function\s*\([^)]*\)\s*\{{', section_body)
    if m:
        return extract_brace_block(section_body, m.end() - 1)

    # Fallback: try name: (...) => { ... } arrow pattern
    m = re.search(rf'\b{re.escape(name)}\s*:\s*\([^)]*\)\s*=>\s*\{{', section_body)
    if m:
        return extract_brace_block(section_body, m.end() - 1)

    return None


def _extract_func_params(section_body: str, name: str) -> str:
    """Extract the parameter list of a named function inside a section body."""
    # Standard shorthand: name(params) {
    m = re.search(rf'\b{re.escape(name)}\s*\(([^)]*)\)\s*\{{', section_body)
    if m:
        return m.group(1)
    # name: function(params) {
    m = re.search(rf'\b{re.escape(name)}\s*:\s*function\s*\(([^)]*)\)\s*\{{', section_body)
    if m:
        return m.group(1)
    # name: (params) => {
    m = re.search(rf'\b{re.escape(name)}\s*:\s*\(([^)]*)\)\s*=>\s*\{{', section_body)
    if m:
        return m.group(1)
    # name: (params) => expr  (single-expression arrow without braces)
    m = re.search(rf'\b{re.escape(name)}\s*:\s*\(([^)]*)\)\s*=>', section_body)
    if m:
        return m.group(1)
    return ""


def _is_async(section_body: str, name: str) -> bool:
    """Check if a named function in a section body is declared async."""
    return bool(re.search(rf'\basync\s+{re.escape(name)}\b', section_body))


def _normalize_indentation(body: str, indent: str) -> str:
    """Normalize indentation in a code body to use the configured indent consistently.

    After textwrap.dedent, bodies may still have mixed tabs/spaces. This function
    re-indents each line using the configured indent string (e.g. 2 spaces).
    """
    lines = body.splitlines()
    normalized = []
    for line in lines:
        stripped = line.lstrip()
        if not stripped:
            normalized.append("")
            continue
        # Count leading spaces/tabs and convert to indent units
        leading = line[:len(line) - len(stripped)]
        level = 0
        i = 0
        while i < len(leading):
            if leading[i] == '\t':
                level += 1
                i += 1
            elif leading[i] == ' ':
                # Count consecutive spaces
                j = i
                while j < len(leading) and leading[j] == ' ':
                    j += 1
                spaces = j - i
                level += max(1, spaces // 2)
                i = j
            else:
                break
        normalized.append((indent * level) + stripped)
    return "\n".join(normalized)


def compute_scoped_members(
    mixin_source: str,
    mixin_members: MixinMembers,
    used_members: list[str],
    lifecycle_hooks: list[str],
) -> tuple[MixinMembers, list[str]]:
    """Compute the minimal set of mixin members a single component actually needs.

    Used by the single-component migration flow to avoid emitting every mixin
    member into a freshly generated composable.

    Returns ``(scoped_members, return_names)`` where:

    - ``scoped_members`` is a ``MixinMembers`` containing the transitive closure of
      members reachable from the component's ``used_members`` plus any member
      referenced by a preserved lifecycle hook body or by the handler body of a
      watcher that survives scoping. Original section order is kept.
    - ``return_names`` is the list of directly-used members present in the closure
      (order-preserved, dotted watch keys excluded) — exactly what belongs in the
      composable's ``return {...}``. Transitive-only helpers are declared but kept
      private (omitted here).
    """
    from .lifecycle_converter import extract_hook_body

    all_names = mixin_members.all_names
    name_set = set(all_names)
    methods_set = set(mixin_members.methods)
    computed_set = set(mixin_members.computed)
    data_set = set(mixin_members.data)

    methods_body = _extract_section_body(mixin_source, "methods")
    computed_body = _extract_section_body(mixin_source, "computed")

    # A surviving watcher's handler body is emitted into the composable, so its
    # references must be part of the closure too (a watcher fires when its target
    # member changes, so map each handler to its target's first path segment).
    watch_section = _extract_watch_section_body(mixin_source)
    watch_handlers: dict[str, str] = {}
    if watch_section:
        for w in mixin_members.watch:
            entry = parse_watch_entry(watch_section, w)
            if entry and entry.get("body"):
                target = w.split('.')[0]
                watch_handlers[target] = (
                    watch_handlers.get(target, "") + "\n" + entry["body"]
                )

    def body_of(name: str) -> str | None:
        if name in methods_set:
            return _extract_func_body(methods_body, name) if methods_body else None
        if name in computed_set:
            return _extract_func_body(computed_body, name) if computed_body else None
        if name in data_set:
            return _extract_data_default(mixin_source, name)
        return None

    def refs_in(text: str | None) -> set[str]:
        if not text:
            return set()
        return {
            n for n in all_names
            if re.search(rf"(?<!\w){re.escape(n)}(?!\w)", text)
        }

    def refs_of(name: str) -> set[str]:
        """References from a member's own body plus, if it's a watch target, the
        watcher handler that gets emitted alongside it."""
        refs = refs_in(body_of(name))
        if name in watch_handlers:
            refs |= refs_in(watch_handlers[name])
        return refs

    # Seed: component-used members that exist in this mixin, plus any member
    # referenced by a (always-preserved) lifecycle hook body.
    closure: set[str] = {m for m in used_members if m in name_set}
    for hook in lifecycle_hooks:
        closure |= refs_in(extract_hook_body(mixin_source, hook))

    # Fixpoint expansion: a member's body (or its watcher handler) may reference
    # other members it depends on; pull those in too.
    queue = list(closure)
    while queue:
        name = queue.pop()
        for ref in refs_of(name):
            if ref not in closure:
                closure.add(ref)
                queue.append(ref)

    scoped = MixinMembers(
        data=[n for n in mixin_members.data if n in closure],
        computed=[n for n in mixin_members.computed if n in closure],
        methods=[n for n in mixin_members.methods if n in closure],
        # A watch entry targets a data/computed member (dotted keys → first segment).
        watch=[w for w in mixin_members.watch if w.split('.')[0] in closure],
    )

    used_set = set(used_members)
    return_names = [n for n in scoped.all_names if n in used_set]
    return scoped, return_names


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
    mixin_path: Path | None = None,
    composable_path: Path | None = None,
    project_root: "Path | None" = None,
    return_members: "list[str] | None" = None,
    full_members: "MixinMembers | None" = None,
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

    When ``return_members`` is given (single-component scoped mode), only those
    members are returned (transitive-only helpers stay private) and ``full_members``
    supplies the complete member kind sets for correct ``this.x`` rewriting.
    """
    fn_name = mixin_stem_to_composable_name(mixin_stem)
    factory_params = _extract_factory_params(mixin_source)
    # `this.x` rewriting must classify every referenced member (refs vs methods),
    # including private transitive-only helpers, so source the kind sets from the
    # FULL member set when scoping is active. Defaults to mixin_members (full mode).
    member_src = full_members or mixin_members
    ref_members = member_src.data + member_src.computed + member_src.watch
    plain_members = member_src.methods

    methods_body = _extract_section_body(mixin_source, "methods")
    computed_body = _extract_section_body(mixin_source, "computed")

    # Generate member declarations using section-aware extraction.
    # Build separate lists for each section, then assemble in canonical order:
    # refs -> computed -> methods -> watch
    ref_lines: list[str] = []
    computed_lines: list[str] = []
    method_lines: list[str] = []
    watch_lines: list[str] = []

    for name in mixin_members.data:
        default = _extract_data_default(mixin_source, name)
        ref_lines.append(f"{indent}const {name} = ref({default})")

    for name in mixin_members.computed:
        body = _extract_func_body(computed_body, name) if computed_body else None
        if body and re.search(r'\bget\s*\(', body):
            gs = parse_getter_setter_computed(body)
            if gs:
                computed_lines.append(generate_getter_setter_computed(name, gs, ref_members, plain_members, indent))
            else:
                computed_lines.append(f"{indent}const {name} = computed(() => null) // TODO: getter/setter computed — migrate manually")
        elif body:
            rewritten = rewrite_this_refs(body.strip(), ref_members, plain_members)
            rewritten_lines = rewritten.strip().splitlines()
            # Check if it's a single return statement (can use arrow shorthand)
            if len(rewritten_lines) == 1 and rewritten_lines[0].strip().startswith("return "):
                expr = rewritten_lines[0].strip()[len("return "):].rstrip(";").strip()
                computed_lines.append(f"{indent}const {name} = computed(() => {expr})")
            else:
                # Multi-line body: use block form with proper indentation
                inner = indent + indent
                indented_body = f"\n{inner}" + f"\n{inner}".join(rewritten_lines) + f"\n{indent}"
                computed_lines.append(f"{indent}const {name} = computed(() => {{{indented_body}}})")
        else:
            computed_lines.append(f"{indent}const {name} = computed(() => null) // TODO: implement")

    for name in mixin_members.methods:
        params = _extract_func_params(methods_body, name) if methods_body else ""
        body = _extract_func_body(methods_body, name) if methods_body else None
        if body:
            body_clean = textwrap.dedent(body).strip()
            # Normalize indentation to use configured indent consistently
            body_clean = _normalize_indentation(body_clean, indent)
            rewritten = rewrite_this_refs(body_clean, ref_members, plain_members)
            inner = indent + indent
            body_lines = f"\n{inner}" + f"\n{inner}".join(rewritten.splitlines()) + f"\n{indent}"
            async_prefix = "async " if _is_async(methods_body, name) else ""
            method_lines.append(f"{indent}{async_prefix}function {name}({params}) {{{body_lines}}}")
        else:
            method_lines.append(f"{indent}function {name}({params}) {{}} // TODO: method body could not be extracted — implement manually")

    # Validate all methods were generated (safety net for Issue #8)
    generated_methods = {m for m in mixin_members.methods if any(f"function {m}(" in line for line in method_lines)}
    missing_methods = set(mixin_members.methods) - generated_methods
    for m in missing_methods:
        method_lines.append(f"{indent}function {m}() {{}} // TODO: method missing from extraction — implement manually")

    watch_section = _extract_watch_section_body(mixin_source)
    has_auto_watch = False
    for name in mixin_members.watch:
        entry = parse_watch_entry(watch_section, name) if watch_section else None
        if entry and not entry["complex"]:
            watch_lines.append(generate_watch_call(name, entry, ref_members, plain_members, indent))
            has_auto_watch = True
        else:
            watch_lines.append(f"{indent}// watch: {name} — migrate manually")

    # Assemble decl_lines from sections in canonical order with uniform blank-line separators
    decl_lines: list[str] = []
    for section in [ref_lines, computed_lines, method_lines, watch_lines]:
        if section:
            if decl_lines and decl_lines[-1] != "":
                decl_lines.append("")
            decl_lines.extend(section)

    # Convert lifecycle hooks
    inline_lines, wrapped_lines = convert_lifecycle_hooks(
        mixin_source, lifecycle_hooks, ref_members, plain_members, indent
    )

    # Reference check: scan lifecycle hook bodies for method references
    # that are in mixin_members.methods. Verify they were generated.
    from .lifecycle_converter import extract_hook_body
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

    # Return statement. In scoped (single-component) mode, return only the
    # directly-used members; transitive-only helpers stay private. Default
    # (None) returns every declared member — preserves full/mixin-mode output,
    # except `_`-prefixed scratch state (CG-1): the underscore convention marks
    # it private, so it stays a function-local const rather than widening the
    # composable's public API.
    if return_members is not None:
        return_list = return_members
    else:
        return_list = [m for m in mixin_members.all_names if not m.startswith("_")]
    return_items = ", ".join(return_list)
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

    # Localize this._xxx private scratch props (e.g. this._searchTimeout for debounce)
    # to non-reactive local variables — but ONLY ones the mixin actually ASSIGNS.
    # A read-only this._x comes from the component (external dependency); localizing
    # it to null would be a silent bug, so leave it as-is and let the external-dep
    # warning flag it. Uses the same helper as the warning system so the two agree.
    internal_props = find_internal_private_props(mixin_source, member_src.all_names)
    if internal_props:
        for p in internal_props:
            body = body.replace(f"this.{p}", p)
        internal_decls = "\n".join(f"{indent}let {p} = null" for p in sorted(internal_props))
        body = internal_decls + "\n\n" + body

    # Apply this.$ auto-rewrites ($nextTick, $set, $delete)
    body, dollar_imports = rewrite_this_dollar_refs(body)
    for imp in dollar_imports:
        if imp not in vue_imports:
            vue_imports.append(imp)

    # Apply this.$t/$tc/$te/$d/$n auto-rewrites to useI18n() equivalents
    body, i18n_functions = rewrite_this_i18n_refs(body)

    # Extract and filter non-Vue imports from the mixin source
    external_imports: list[str] = []
    if mixin_path is not None:
        mixin_imports = extract_mixin_imports(mixin_source)
        used_imports = filter_imports_by_usage(mixin_imports, body)
        mixin_dir = mixin_path.parent
        composable_dir = composable_path.parent if composable_path else mixin_dir
        external_imports = [
            rewrite_import_path(imp["line"], mixin_dir, composable_dir)
            for imp in used_imports
        ]

    # If i18n functions are used, prepend destructuring to body and prepare import
    i18n_import_line = ""
    if i18n_functions:
        sorted_fns = sorted(i18n_functions)
        i18n_import_line = "import { useI18n } from 'vue-i18n'\n"
        i18n_destructure = f"{indent}const {{ {', '.join(sorted_fns)} }} = useI18n()"
        body = i18n_destructure + "\n\n" + body

    # Assemble full file
    import_line = (
        f"import {{ {', '.join(vue_imports)} }} from 'vue'\n"
        if vue_imports else ""
    )
    if import_line and not i18n_import_line:
        import_line += "\n"  # extra blank line before function when no i18n import
    external_block = "\n".join(external_imports) + "\n" if external_imports else ""
    if i18n_import_line:
        i18n_import_line += "\n"  # blank line after last import
    result = f"{external_block}{import_line}{i18n_import_line}export function {fn_name}({factory_params}) {{\n{body}\n}}\n"

    # Collect warnings and suppress those already resolved by the generated code
    warnings = collect_mixin_warnings(
        mixin_source, mixin_members, lifecycle_hooks,
        mixin_path=mixin_path, project_root=project_root,
    )
    warnings = suppress_resolved_warnings(warnings, [], result)

    # In scoped (single-component) mode, members that were scoped out aren't in
    # the generated composable — so drop their warnings, which would otherwise
    # inflate the confidence header with manual steps for code that isn't here.
    if full_members is not None:
        dropped_members = set(full_members.all_names) - set(mixin_members.all_names)
        if dropped_members:
            warnings = suppress_covered_member_warnings(
                warnings, dropped_members, extract_member_line_ranges(mixin_source),
            )

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
