"""
Mixin analysis — extract members and lifecycle hooks from Vue mixin source code.
"""

import re

from .js_parser import extract_brace_block, extract_property_names

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


def extract_lifecycle_hooks(source: str) -> list[str]:
    """Find Vue lifecycle hooks defined in the mixin source."""
    return [
        hook for hook in VUE_LIFECYCLE_HOOKS
        if re.search(rf"\b{hook}\s*(?:\(|:\s*(?:function|\())", source)
    ]
