"""
Composable analysis — extract identifiers, return keys, and function names
from Vue 3 composable source files.
"""

import re
from typing import Optional

from .js_parser import extract_brace_block


_NOISE = {
    "const", "let", "var", "function", "return", "if", "else", "new",
    "true", "false", "null", "undefined", "async", "await", "from", "import",
}


def extract_declared_identifiers(source: str) -> list[str]:
    """Extract identifiers that have actual declarations (const/let/var/function/destructure).

    Does NOT include return-statement keys — only names with real definitions.
    """
    ids: set[str] = set()

    # const/let/var name = ...
    ids.update(re.findall(r"\b(?:const|let|var)\s+(\w+)", source))

    # function name(...)
    ids.update(re.findall(r"\bfunction\s+(\w+)", source))

    # Destructured: const { a, b: renamed, c = default } = ...
    for match in re.finditer(r"\b(?:const|let|var)\s*\{([^}]+)\}", source):
        for part in match.group(1).split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                ids.add(part.split(":")[1].strip().split("=")[0].strip())
            else:
                ids.add(part.split("=")[0].strip())

    return sorted(ids - _NOISE)


def extract_all_identifiers(source: str) -> list[str]:
    """Extract ALL identifiers defined anywhere in a composable file.

    Covers: variable declarations, function declarations, destructuring,
    and return statement keys.
    """
    ids = set(extract_declared_identifiers(source))

    # Return keys: return { foo, bar, baz: val } — use LAST match to skip nested returns
    ret_matches = list(re.finditer(r"\breturn\s*\{", source))
    ret = ret_matches[-1] if ret_matches else None
    if ret:
        block = extract_brace_block(source, ret.end() - 1)
        ids.update(re.findall(r"\b(\w+)\s*[,}\n:]", block))

    return sorted(ids - _NOISE)


def extract_return_keys(source: str) -> list[str]:
    """Extract ONLY the keys from the composable's return { ... } statement.

    Members must be in the return statement to be accessible by the component.
    Handles both direct returns (return { a, b }) and indirect returns
    (const obj = { a, b }; return obj).
    """
    noise = {
        "const", "let", "var", "function", "return", "true", "false",
        "null", "undefined", "new", "value",
    }

    # Case 1: direct return { ... } — use LAST match to skip nested returns
    matches = list(re.finditer(r"\breturn\s*\{", source))
    ret = matches[-1] if matches else None
    if ret:
        block = extract_brace_block(source, ret.end() - 1)
        keys = re.findall(r"\b(\w+)\b", block)
        return list(dict.fromkeys(k for k in keys if k not in noise))

    # Case 2: indirect return — return varName  where varName = { ... }
    ret_var = re.search(r"\breturn\s+(\w+)\s*;?\s*\n?\s*\}", source)
    if ret_var:
        var_name = ret_var.group(1)
        if var_name in noise:
            return []
        # Find the variable's object literal assignment
        var_def = re.search(
            rf"\b(?:const|let|var)\s+{re.escape(var_name)}\s*=\s*\{{",
            source,
        )
        if var_def:
            block = extract_brace_block(source, var_def.end() - 1)
            keys = re.findall(r"\b(\w+)\b", block)
            return list(dict.fromkeys(k for k in keys if k not in noise))

    return []


def extract_function_name(source: str) -> Optional[str]:
    """Find the exported function name (e.g. useSelection) in a composable.

    Checks for:
      - export function useName(
      - export default function useName(
      - export const useName =
      - export default const useName =
    """
    # export function useName(  /  export default function useName(
    match = re.search(r"\bexport\s+(?:default\s+)?function\s+(\w+)", source)
    if match:
        return match.group(1)
    # export const useName = (
    match = re.search(r"\bexport\s+(?:default\s+)?const\s+(\w+)\s*=", source)
    if match:
        return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Identifier kind classification
# ---------------------------------------------------------------------------

# Vue reactivity wrappers that produce ref-like values
_REF_WRAPPERS = r"ref|shallowRef|reactive|shallowReactive|toRef|toRefs|customRef"
_COMPUTED_WRAPPERS = r"computed"


def classify_identifier_kind(name: str, source: str) -> str:
    """Classify what kind of value a declared identifier is in composable source.

    Returns one of: "ref", "computed", "function", "unknown".
    """
    esc = re.escape(name)

    # const/let/var name = ref(...) or ref<Type>(...)
    if re.search(rf"\b(?:const|let|var)\s+{esc}\s*=\s*(?:{_REF_WRAPPERS})\s*[<(]", source):
        return "ref"

    # const/let/var name = computed(...) or computed<Type>(...)
    if re.search(rf"\b(?:const|let|var)\s+{esc}\s*=\s*(?:{_COMPUTED_WRAPPERS})\s*[<(]", source):
        return "computed"

    # function name(...) or async function name(...)
    if re.search(rf"\b(?:async\s+)?function\s+{esc}\s*\(", source):
        return "function"

    # const name = (...) => or const name = async (...) =>
    if re.search(rf"\b(?:const|let|var)\s+{esc}\s*=\s*(?:async\s*)?\(", source):
        return "function"

    return "unknown"


def classify_all_identifier_kinds(source: str, names: list[str]) -> dict[str, str]:
    """Classify all named identifiers in composable source. Returns {name: kind}."""
    return {name: classify_identifier_kind(name, source) for name in names}
