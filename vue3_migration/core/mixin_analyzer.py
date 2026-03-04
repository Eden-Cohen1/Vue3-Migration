"""
Mixin analysis — extract members and lifecycle hooks from Vue mixin source code.
"""

import re

from .js_parser import extract_brace_block, extract_property_names, skip_non_code

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


def extract_lifecycle_hooks(source: str) -> list[str]:
    """Find Vue lifecycle hooks defined in the mixin source."""
    return [
        hook for hook in VUE_LIFECYCLE_HOOKS
        if re.search(rf"\b{hook}\s*(?:\(|:\s*(?:function|\())", source)
    ]
