"""Tests proving TypeScript failure modes of the current string-based parser.

Each test documents a specific TS construct that breaks the parser.
These tests are expected to FAIL with the current parser, proving
the limitation exists. After AST migration, they should PASS.

Run with: pytest tests/test_typescript_failures.py -v
"""

import re
from pathlib import Path

import pytest

from vue3_migration.core.js_parser import (
    extract_declaration_names,
    extract_property_names,
    extract_brace_block,
    extract_value_at,
)
from vue3_migration.core.mixin_analyzer import (
    extract_mixin_members,
    extract_mixin_imports,
    find_external_this_refs,
)

TS_FIXTURES = Path(__file__).parent / "fixtures" / "ts_dummy_project"
MIXINS_DIR = TS_FIXTURES / "src" / "mixins"


def _read(name: str) -> str:
    return (MIXINS_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Failure Mode 1: Type annotations on variable declarations
# extract_declaration_names uses regex `\b(?:const|let|var)\s+(\w+)\s*=`
# which fails when a type annotation sits between the name and `=`.
# ---------------------------------------------------------------------------

class TestTypedVariableDeclarations:
    """Failure 1: `const x: string = ...` not detected by extract_declaration_names."""

    def test_typed_const_detected(self):
        """extract_declaration_names must find 'count' in 'const count: number = ref(0)'."""
        body = "const count: number = ref(0)"
        names = extract_declaration_names(body)
        assert "count" in names, (
            f"Expected 'count' in declaration names, got {names}. "
            "The regex can't handle type annotations between name and ="
        )

    def test_typed_let_detected(self):
        """extract_declaration_names must find 'label' in 'let label: string = ...'."""
        body = 'let label: string = "default"'
        names = extract_declaration_names(body)
        assert "label" in names

    def test_typed_complex_type_detected(self):
        """extract_declaration_names must find 'items' in 'const items: string[] = ...'."""
        body = "const items: string[] = []"
        names = extract_declaration_names(body)
        assert "items" in names

    def test_typed_generic_type_detected(self):
        """extract_declaration_names must find 'map' in 'const map: Map<string, number> = ...'."""
        body = "const map: Map<string, number> = new Map()"
        names = extract_declaration_names(body)
        assert "map" in names

    def test_typed_union_type_detected(self):
        """extract_declaration_names must find 'value' in 'const value: string | null = ...'."""
        body = "const value: string | null = null"
        names = extract_declaration_names(body)
        assert "value" in names


# ---------------------------------------------------------------------------
# Failure Mode 2: TypeScript parameter types leak into generated code
# _extract_func_params captures everything between ( and ), including `: string`.
# Also, return type annotations like ): void { break the regex match.
# ---------------------------------------------------------------------------

class TestTypedParameterExtraction:
    """Failure 2: Function parameter type annotations survive into generated code."""

    def test_return_type_does_not_break_method_detection(self):
        """Methods with return types like `search(...): void {` must still be detected."""
        source = _read("typedMethodsMixin.ts")
        members = extract_mixin_members(source)
        assert "search" in members["methods"], (
            f"Expected 'search' in methods, got {members['methods']}. "
            "Return type annotation ': void' between ) and { breaks the regex"
        )

    def test_params_extracted_without_types(self):
        """Extracted params for 'search' should be 'query, limit', not 'query: string, limit: number'."""
        # Import the private function for direct testing
        from vue3_migration.transform.composable_generator import _extract_func_params

        source = _read("typedMethodsMixin.ts")
        methods_match = re.search(r"\bmethods\s*:\s*\{", source)
        methods_body = extract_brace_block(source, methods_match.end() - 1)

        params = _extract_func_params(methods_body, "search")
        # Should be clean params without types
        assert "string" not in params, (
            f"Params contain type annotations: '{params}'. "
            "Expected clean JS params like 'query, limit'"
        )

    def test_optional_param_type_not_in_output(self):
        """Optional param `currency: string = 'USD'` should become `currency = 'USD'`."""
        from vue3_migration.transform.composable_generator import _extract_func_params

        source = _read("typedMethodsMixin.ts")
        methods_match = re.search(r"\bmethods\s*:\s*\{", source)
        methods_body = extract_brace_block(source, methods_match.end() - 1)

        params = _extract_func_params(methods_body, "format")
        # Should strip `: number` and `: string` but keep `= 'USD'`
        assert "number" not in params, (
            f"Params contain type annotations: '{params}'"
        )

    def test_async_method_with_promise_return_type(self):
        """async fetchData(...): Promise<void> must still be detected as a method."""
        source = _read("typedMethodsMixin.ts")
        members = extract_mixin_members(source)
        assert "fetchData" in members["methods"], (
            f"Expected 'fetchData' in methods, got {members['methods']}. "
            "Promise<void> return type breaks detection"
        )


# ---------------------------------------------------------------------------
# Failure Mode 3: TypeScript type assertions and generics
# `as Type` syntax and `Array<{...}>` generics confuse extract_value_at()
# because <> are not tracked for depth.
# ---------------------------------------------------------------------------

class TestGenericAndTypeAssertions:
    """Failure 3: `null as string | null` and `Array<{...}>` break value extraction."""

    def test_as_assertion_in_data_value(self):
        """extract_value_at must handle 'null as string | null' without truncation."""
        # Simulating what the patcher sees when extracting data defaults
        obj_body = "selected: null as string | null, entries: [] as Array<{ id: number; name: string }>"
        # Find position after "selected: "
        pos = obj_body.index("null")
        val = extract_value_at(obj_body, pos)
        # The value should capture either just 'null' (stripping the assertion)
        # or 'null as string | null' (preserving it). But it should NOT truncate
        # at the pipe character or get confused by the assertion.
        assert "null" in val, f"Value extraction failed entirely: '{val}'"
        # The key test: did it capture the NEXT property's value too?
        # If the pipe | confused the parser, it might stop at the wrong place.
        assert "entries" not in val, (
            f"Value extraction over-captured into next property: '{val}'"
        )

    def test_generic_array_type_in_data(self):
        """extract_value_at must not be confused by Array<{ id: number }> generics."""
        obj_body = "entries: [] as Array<{ id: number; name: string }>, config: {}"
        pos = obj_body.index("[]")
        val = extract_value_at(obj_body, pos)
        # Should extract `[] as Array<{ id: number; name: string }>` or at minimum `[]`
        # but must NOT eat into 'config' property
        assert "config" not in val, (
            f"Value extraction over-captured past generics: '{val}'"
        )

    def test_data_members_extracted_from_generic_mixin(self):
        """All data members must be found even with type assertions."""
        source = _read("genericRefsMixin.ts")
        members = extract_mixin_members(source)
        expected = {"selected", "entries", "config", "count"}
        actual = set(members["data"])
        assert expected == actual, (
            f"Expected data members {expected}, got {actual}. "
            "Type assertions likely confused property extraction"
        )


# ---------------------------------------------------------------------------
# Failure Mode 4: Optional chaining `this?.x` not detected
# The regex `\bthis\.(\w+)` requires a literal `.` but optional chaining
# uses `?.` which doesn't match.
# ---------------------------------------------------------------------------

class TestOptionalChaining:
    """Failure 4: `this?.x` references are invisible to the parser."""

    def test_optional_chain_this_detected(self):
        """find_external_this_refs must detect 'this?.count' as referencing 'count'."""
        code = "const current = this?.count ?? 0"
        # 'count' is the mixin's own member, but we pass empty own_members
        # to see if the parser even FINDS the reference
        refs = find_external_this_refs(code, [])
        assert "count" in refs, (
            f"Expected 'count' in external refs, got {refs}. "
            "Optional chaining `this?.count` is invisible to the `this\\.` regex"
        )

    def test_optional_chain_method_call(self):
        """find_external_this_refs must detect 'this?.reset?.()' as referencing 'reset'."""
        code = "this?.reset?.()"
        refs = find_external_this_refs(code, [])
        assert "reset" in refs, (
            f"Expected 'reset' in external refs, got {refs}. "
            "Optional chaining on method call not detected"
        )

    def test_mixed_normal_and_optional_chain(self):
        """Both `this.isActive` and `this?.count` must be found in the same block."""
        code = """
        if (this.isActive) {
          return this?.count
        }
        return this?.label ?? 'none'
        """
        refs = find_external_this_refs(code, [])
        assert "isActive" in refs, "Normal this.isActive should be found"
        assert "count" in refs, (
            "Optional this?.count should also be found but isn't"
        )
        assert "label" in refs, (
            "Optional this?.label should also be found but isn't"
        )

    def test_mixin_members_with_optional_chain_usage(self):
        """extract_mixin_members should work on the optionalChain mixin despite TS syntax."""
        source = _read("optionalChainMixin.ts")
        members = extract_mixin_members(source)
        assert "safeIncrement" in members["methods"]
        assert "safeReset" in members["methods"]
        assert "conditionalAccess" in members["methods"]


# ---------------------------------------------------------------------------
# Failure Mode 5: `import type` loses type-only semantics
# The parser strips the `type` keyword, turning `import type { Foo }`
# into `import { Foo }` in generated output.
# ---------------------------------------------------------------------------

class TestImportTypePreservation:
    """Failure 5: `import type { X }` must preserve the `type` keyword."""

    def test_import_type_detected(self):
        """extract_mixin_imports must capture 'import type { UserConfig }' line."""
        source = _read("importTypeMixin.ts")
        imports = extract_mixin_imports(source)
        import_lines = [imp["line"] for imp in imports]
        # At minimum, the import should be captured (even if type is lost)
        has_user_config_import = any("UserConfig" in line for line in import_lines)
        assert has_user_config_import, (
            f"UserConfig import not captured at all. Lines: {import_lines}"
        )

    def test_import_type_keyword_preserved(self):
        """The captured import line must retain 'import type', not just 'import'."""
        source = _read("importTypeMixin.ts")
        imports = extract_mixin_imports(source)
        type_imports = [
            imp["line"] for imp in imports
            if "UserConfig" in imp["line"]
        ]
        assert len(type_imports) == 1, f"Expected 1 UserConfig import, got {type_imports}"
        line = type_imports[0]
        assert "import type" in line, (
            f"Expected 'import type' in line, got '{line}'. "
            "The 'type' keyword was stripped — generated code will try to "
            "import a type as a runtime value"
        )

    def test_value_import_not_affected(self):
        """Regular import `import { validateConfig }` should still work normally."""
        source = _read("importTypeMixin.ts")
        imports = extract_mixin_imports(source)
        validate_imports = [
            imp for imp in imports
            if "validateConfig" in str(imp["identifiers"])
        ]
        assert len(validate_imports) == 1, (
            f"Expected validateConfig import, got {validate_imports}"
        )
