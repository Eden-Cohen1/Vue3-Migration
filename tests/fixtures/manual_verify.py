#!/usr/bin/env python3
"""Manual verification script for kind-mismatch and this.$options detection.

Run: python tests/fixtures/manual_verify.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from vue3_migration.models import MixinMembers, ComposableCoverage
from vue3_migration.core.composable_analyzer import (
    classify_all_identifier_kinds,
    extract_all_identifiers,
    extract_declared_identifiers,
    extract_return_keys,
)
from vue3_migration.core.warning_collector import collect_mixin_warnings

FIXTURE = Path(__file__).parent / "dummy_project"

print("=" * 60)
print("TASK 1: Kind Mismatch Detection")
print("=" * 60)

mixin_src = (FIXTURE / "src/mixins/verifyKindMixin.js").read_text()
comp_src = (FIXTURE / "src/composables/useVerifyKind.js").read_text()

members = MixinMembers(
    data=["results"],
    computed=["total"],
    methods=["isLoading", "fetchData"],
)

declared = extract_declared_identifiers(comp_src)
kinds = classify_all_identifier_kinds(comp_src, declared)

print(f"\nComposable identifier kinds:")
for name, kind in sorted(kinds.items()):
    print(f"  {name}: {kind}")

coverage = ComposableCoverage(
    file_path=FIXTURE / "src/composables/useVerifyKind.js",
    fn_name="useVerifyKind",
    import_path="@/composables/useVerifyKind",
    all_identifiers=extract_all_identifiers(comp_src),
    declared_identifiers=declared,
    return_keys=extract_return_keys(comp_src),
    identifier_kinds=kinds,
)

used = members.data + members.computed + members.methods
classification = coverage.classify_members(used, set(), mixin_members=members)

print(f"\nKind mismatches found: {len(classification.kind_mismatched)}")
for name, mixin_kind, comp_kind in classification.kind_mismatched:
    print(f"  MISMATCH: '{name}' is {mixin_kind} in mixin but {comp_kind} in composable")

print(f"\nis_ready (should be True — mismatches are warnings, not blockers): {classification.is_ready}")

# Verify expected mismatches
expected = {("isLoading", "methods", "ref"), ("total", "computed", "function")}
actual = {tuple(m) for m in classification.kind_mismatched}
assert actual == expected, f"Expected {expected}, got {actual}"
print("PASS: Exactly the expected mismatches were detected")

print()
print("=" * 60)
print("TASK 2: this.$options Warning Detection")
print("=" * 60)

options_src = (FIXTURE / "src/mixins/verifyOptionsMixin.js").read_text()
warnings = collect_mixin_warnings(options_src, MixinMembers(methods=["getMixinMethod", "getComponentName"]), [])

print(f"\nWarnings found: {len(warnings)}")
for w in warnings:
    print(f"  [{w.severity.upper()}] {w.category}: {w.message}")

# Verify expected warnings
cats = {w.category for w in warnings}
assert "this.$options.mixins" in cats, "Missing this.$options.mixins warning"
assert "this.$options" in cats, "Missing this.$options warning"
assert all(w.severity == "error" for w in warnings if "$options" in w.category), "All $options warnings should be errors"
# Verify no duplicate — general $options should NOT fire for the .mixins line
options_general = [w for w in warnings if w.category == "this.$options"]
assert len(options_general) == 1, f"Expected exactly 1 general $options warning, got {len(options_general)}"
print("PASS: Both patterns detected as errors, no duplicates")

print()
print("=" * 60)
print("ALL MANUAL VERIFICATION CHECKS PASSED")
print("=" * 60)
