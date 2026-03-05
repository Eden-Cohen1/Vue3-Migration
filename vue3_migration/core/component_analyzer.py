"""
Component analysis — parse imports, mixins arrays, member usage, and
component-defined members from Vue component source code.
"""

import re

from .js_parser import extract_brace_block, extract_property_names


def parse_imports(component_source: str) -> dict[str, str]:
    """Parse import statements. Returns { local_name: import_path }."""
    imports = {}
    # Default imports: import X from 'path'
    for match in re.finditer(r"""import\s+(\w+)\s+from\s+['"]([^'"]+)['"]""", component_source):
        imports[match.group(1)] = match.group(2)
    # Named imports: import { X } from 'path' or import { X as Y } from 'path'
    for match in re.finditer(
        r"""import\s+\{([^}]+)\}\s+from\s+['"]([^'"]+)['"]""",
        component_source,
    ):
        names_str = match.group(1)
        path = match.group(2)
        for name_part in names_str.split(","):
            name_part = name_part.strip()
            if not name_part:
                continue
            if " as " in name_part:
                _, local = name_part.split(" as ", 1)
                imports[local.strip()] = path
            else:
                imports[name_part] = path
    return imports


def parse_mixins_array(component_source: str) -> list[str]:
    """Extract the local variable names from `mixins: [A, B, C]`."""
    match = re.search(r"mixins\s*:\s*\[([^\]]*)\]", component_source)
    if not match:
        return []
    return [name.strip() for name in match.group(1).split(",") if name.strip()]


def find_used_members(component_source: str, member_names: list[str]) -> list[str]:
    """Find which mixin members are referenced in the component (script + template).

    For .vue files, searches within <script> and <template> sections.
    Uses word-boundary regex to avoid partial matches.
    """
    sections = []
    for tag in ("script", "template"):
        tag_match = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", component_source, re.DOTALL)
        if tag_match:
            sections.append(tag_match.group(1))
    search_text = "\n".join(sections) if sections else component_source

    return [
        member for member in member_names
        if re.search(rf"(?<!\w){re.escape(member)}(?!\w)", search_text)
    ]


def extract_data_property_names(component_source: str) -> list[str]:
    """Extract property names from a component's data() return object.

    Parses patterns like:
        data() { return { key1: value1, key2: value2 } }
        data: function() { return { key1: value1 } }

    Returns a list of property name strings found in the data() return block.
    """
    # Find data() or data: function() return block
    m = re.search(r'\bdata\s*(?:\(\)|:\s*function\s*\(\))\s*(?::\s*\w+(?:<[^>]*>)?\s*)?\{', component_source)
    if not m:
        return []

    # Extract the data function body first
    data_body = extract_brace_block(component_source, m.end() - 1)
    if not data_body:
        return []

    # Find return { ... } in the body
    ret_m = re.search(r'\breturn\s*\{', data_body)
    if not ret_m:
        return []

    return_block = extract_brace_block(data_body, ret_m.end() - 1)
    if not return_block:
        return []

    # Extract property names using the existing property name extractor
    return extract_property_names(return_block)


def extract_own_members(component_source: str) -> set[str]:
    """Extract member names defined in the component's OWN data/computed/methods/watch.

    These are members the component defines itself (not inherited from mixins).
    When a component overrides a mixin member, the component's version takes
    precedence, so the composable doesn't need to provide it.
    """
    own_members: set[str] = set()

    # Extract just the <script> section for .vue files
    script_match = re.search(r"<script[^>]*>(.*?)</script>", component_source, re.DOTALL)
    source = script_match.group(1) if script_match else component_source

    # data() { return { ... } }
    data_match = re.search(r"\bdata\s*\(\s*\)\s*(?::\s*\w+(?:<[^>]*>)?\s*)?\{", source)
    if data_match:
        body = source[data_match.end():]
        ret = re.search(r"\breturn\s*\{", body)
        if ret:
            brace_pos = ret.start() + ret.group().index("{")
            own_members.update(extract_property_names(extract_brace_block(body, brace_pos)))

    # computed, methods, watch sections
    for section in ("computed", "methods", "watch"):
        match = re.search(rf"\b{section}\s*:\s*\{{", source)
        if match:
            own_members.update(
                extract_property_names(extract_brace_block(source, match.end() - 1))
            )

    return own_members
