"""
Mixin analysis — extract members and lifecycle hooks from Vue mixin source code.
"""

import os
import re
from pathlib import Path

from .js_parser import extract_brace_block, extract_property_names, skip_non_code, skip_string, strip_comments

VUE_LIFECYCLE_HOOKS = [
    "beforeCreate", "created", "beforeMount", "mounted",
    "beforeUpdate", "updated", "beforeDestroy", "destroyed",
    "beforeUnmount", "unmounted", "activated", "deactivated",
    "errorCaptured", "renderTracked", "renderTriggered",
    "onBeforeMount", "onMounted", "onBeforeUpdate", "onUpdated",
    "onBeforeUnmount", "onUnmounted", "onActivated", "onDeactivated",
    "onErrorCaptured", "onRenderTracked", "onRenderTriggered",
]


def extract_mixin_members(source: str) -> dict[str, list[str]]:
    """Extract data, computed, methods, and watch property names from a mixin.

    Returns:
        Dict with keys 'data', 'computed', 'methods', 'watch', each mapping to
        a list of property name strings.
    """
    members: dict[str, list[str]] = {"data": [], "computed": [], "methods": [], "watch": []}

    # data() { return { ... } }
    data_match = re.search(r"\bdata\s*\(\s*\)\s*(?::\s*\w+(?:<[^>]*>)?\s*)?\{", source)
    if data_match:
        body = source[data_match.end():]
        ret = re.search(r"\breturn\s*\{", body)
        if ret:
            brace_pos = ret.start() + ret.group().index("{")
            members["data"] = extract_property_names(extract_brace_block(body, brace_pos))

    # computed: { ... }, methods: { ... }, watch: { ... }
    for section in ("computed", "methods", "watch"):
        match = re.search(rf"\b{section}\s*:\s*\{{", source)
        if match:
            members[section] = extract_property_names(
                extract_brace_block(source, match.end() - 1)
            )

    return members


def find_external_this_refs(
    code: str, own_member_names: list[str]
) -> list[str]:
    """Find ``this.X`` references where X is NOT a member of the mixin itself.

    Skips:
    - Members in *own_member_names* (data, computed, methods, watch of this mixin)
    - ``this.$xxx`` references (handled by the ``this.$`` warning system)
    - Matches inside strings, comments, and template literals

    Returns a deduplicated list of external member names.
    """
    own_set = set(own_member_names)
    pattern = re.compile(r"\bthis\.(\w+)")
    seen: list[str] = []
    pos = 0
    while pos < len(code):
        new_pos, skipped = skip_non_code(code, pos)
        if skipped:
            pos = new_pos
            continue
        m = pattern.match(code, pos)
        if m:
            name = m.group(1)
            if name not in own_set and not name.startswith("$") and name not in seen:
                seen.append(name)
            pos = m.end()
        else:
            pos += 1
    return seen


def resolve_external_dep_sources(
    external_deps: list[str],
    sibling_entries: list,
    component_own_members: set[str],
    component_name: str,
    component_members_by_section: dict[str, list[str]] | None = None,
) -> dict[str, dict]:
    """Resolve where each external dependency comes from.

    For each dep, checks sibling mixin entries and the component's own members.
    Returns a dict mapping dep name to source info::

        {
            "entityId": {
                "kind": "component",  # or "sibling", "ambiguous", "unknown"
                "detail": "TaskDetailView.data",
                "sources": ["TaskDetailView.data"],
            }
        }

    Args:
        external_deps: Names of external ``this.X`` references.
        sibling_entries: Other MixinEntry objects for the same component.
        component_own_members: Members the component defines itself.
        component_name: Component file stem (for display in warnings).
        component_members_by_section: Optional categorized component members
            (keys: data, computed, methods, watch) for more detailed source info.
    """
    result: dict[str, dict] = {}
    for dep in external_deps:
        sources: list[str] = []

        # Check sibling mixin entries
        for sibling in sibling_entries:
            for section in ("data", "computed", "methods", "watch"):
                section_members = getattr(sibling.members, section, [])
                if dep in section_members:
                    sources.append(f"{sibling.mixin_stem}.{section}")
                    break  # one hit per sibling is enough

        # Check component's own members (with section detail if available)
        if dep in component_own_members:
            comp_section = None
            if component_members_by_section:
                for section in ("data", "computed", "methods", "watch"):
                    if dep in component_members_by_section.get(section, []):
                        comp_section = section
                        break
            if comp_section:
                sources.append(f"{component_name}.{comp_section}")
            else:
                sources.append(f"{component_name}")

        if len(sources) == 0:
            result[dep] = {"kind": "unknown", "detail": None, "sources": []}
        elif len(sources) == 1:
            src = sources[0]
            kind = "component" if src.startswith(component_name) else "sibling"
            result[dep] = {"kind": kind, "detail": src, "sources": sources}
        else:
            result[dep] = {"kind": "ambiguous", "detail": None, "sources": sources}

    return result


def extract_member_line_ranges(source: str) -> dict[str, tuple[int, int]]:
    """Map mixin member names to their (start_line, end_line) in source.

    Scans ``methods``, ``computed``, and ``watch`` sections.  For each
    property inside those sections, records the 1-based inclusive line
    range from the property name through the closing ``}`` of its body.

    Lifecycle hooks and ``data()`` are intentionally excluded.

    Returns:
        Dict mapping member name → (start_line, end_line), e.g.
        ``{"submit": (10, 18), "total": (20, 22)}``.
    """

    def _line_at(offset: int) -> int:
        return source[:offset].count("\n") + 1

    ranges: dict[str, tuple[int, int]] = {}

    for section in ("computed", "methods", "watch"):
        match = re.search(rf"\b{section}\s*:\s*\{{", source)
        if not match:
            continue
        section_open = match.end() - 1  # points at '{'
        section_body = extract_brace_block(source, section_open)
        # Absolute char offset in `source` where section_body begins
        abs_start = section_open + 1

        # Walk the section body using the same expect_key + depth approach
        # as extract_property_names, but record positions too.
        depth = 0
        expect_key = True
        pos = 0
        while pos < len(section_body):
            ch = section_body[pos]
            new_pos, skipped = skip_non_code(section_body, pos)
            if skipped:
                pos = new_pos
                continue
            if ch in "{[(":
                depth += 1
            elif ch in "}])":
                depth -= 1
            elif depth == 0 and ch == ",":
                expect_key = True
                pos += 1
                continue
            elif depth == 0 and expect_key and (ch.isalpha() or ch in "_$'\""):
                name: str | None = None
                name_start = pos  # position of property name in section_body

                if ch in ("'", '"'):
                    end = skip_string(section_body, pos)
                    rest = section_body[end:].lstrip()
                    if rest and rest[0] in (":", "("):
                        name = section_body[pos + 1 : end - 1]
                    pos = end
                else:
                    m = re.match(r"(?:async\s+)?(\w+)", section_body[pos:])
                    if m:
                        name = m.group(1)
                        pos += m.end()
                    else:
                        pos += 1
                        continue

                if name is None:
                    expect_key = False
                    continue

                expect_key = False

                # Scan forward from current pos for the opening '{'
                scan = pos
                while scan < len(section_body):
                    sp, sk = skip_non_code(section_body, scan)
                    if sk:
                        scan = sp
                        continue
                    if section_body[scan] == "{":
                        break
                    if section_body[scan] == ",":
                        # No brace block (e.g. shorthand or arrow without braces)
                        break
                    scan += 1

                if scan < len(section_body) and section_body[scan] == "{":
                    inner = extract_brace_block(section_body, scan)
                    close_pos = scan + 1 + len(inner)  # '}' position in section_body
                    ranges[name] = (
                        _line_at(abs_start + name_start),
                        _line_at(abs_start + close_pos),
                    )
                    pos = close_pos + 1
                    continue
            pos += 1

    return ranges


def extract_lifecycle_hooks(source: str) -> list[str]:
    """Find Vue lifecycle hooks defined in the mixin source."""
    return [
        hook for hook in VUE_LIFECYCLE_HOOKS
        if re.search(rf"\b{hook}\s*(?:\(|:\s*(?:function|\())", source)
    ]


def extract_mixin_imports(mixin_source: str) -> list[dict]:
    """Parse all ES module import lines from mixin source, excluding Vue imports.

    Returns a list of dicts, each with:
      - "line": the full import statement string
      - "identifiers": list of locally-bound names (aliases, not originals)

    Skips side-effect imports (no identifiers) and imports from 'vue'.
    """
    results = []
    for m in re.finditer(
        r"""^(import\s+.+?\s+from\s+['"]([^'"]+)['"]\s*;?)""",
        mixin_source,
        re.MULTILINE,
    ):
        line = m.group(1)
        module_path = m.group(2)

        # Skip vue imports
        if module_path == "vue" or module_path.startswith("vue/"):
            continue

        identifiers: list[str] = []

        # import * as X from '...'
        ns = re.match(r"import\s+\*\s+as\s+(\w+)", line)
        if ns:
            identifiers.append(ns.group(1))
        else:
            # import { A, B as C } from '...'
            named = re.search(r"import\s*\{([^}]+)\}", line)
            if named:
                for part in named.group(1).split(","):
                    part = part.strip()
                    if not part:
                        continue
                    # "original as alias" -> alias
                    as_match = re.match(r"\w+\s+as\s+(\w+)", part)
                    if as_match:
                        identifiers.append(as_match.group(1))
                    else:
                        identifiers.append(part)

            # import DefaultExport from '...' (possibly alongside named)
            default = re.match(r"import\s+(\w+)(?:\s*,\s*\{)?", line)
            if default and default.group(1) not in ("type", "typeof"):
                name = default.group(1)
                if name not in identifiers:
                    identifiers.append(name)

        if identifiers:
            results.append({"line": line, "identifiers": identifiers})

    return results


def filter_imports_by_usage(imports: list[dict], code: str) -> list[dict]:
    """Return only imports that have at least one identifier referenced in code.

    Uses word-boundary matching to avoid false positives (e.g. 'item' won't
    match 'itemCount').
    """
    used = []
    stripped = strip_comments(code)
    for imp in imports:
        if any(re.search(rf"\b{re.escape(name)}\b", stripped) for name in imp["identifiers"]):
            used.append(imp)
    return used


def rewrite_import_path(import_line: str, mixin_dir: Path, composable_dir: Path) -> str:
    """Rewrite a relative import path from mixin's directory to composable's directory.

    Only rewrites paths starting with './' or '../'. Aliased paths (@/...),
    bare specifiers (lodash), and absolute paths are returned unchanged.
    """
    m = re.search(r"""(from\s+)(['"])(\.\.?[/\\][^'"]*)\2""", import_line)
    if not m:
        return import_line

    quote = m.group(2)
    old_path = m.group(3)

    # Resolve the import target against the mixin's directory
    resolved = (mixin_dir / old_path).resolve()

    # Compute new relative path from composable's directory
    try:
        new_rel = os.path.relpath(resolved, composable_dir).replace("\\", "/")
    except ValueError:
        return import_line  # different drives on Windows

    if not new_rel.startswith("."):
        new_rel = "./" + new_rel

    return import_line[:m.start(3)] + new_rel + import_line[m.end(3):]
