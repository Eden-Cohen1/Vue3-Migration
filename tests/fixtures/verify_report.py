#!/usr/bin/env python3
"""Generate migration report for the dummy_project WITHOUT applying changes.

Usage:
    python tests/fixtures/verify_report.py

Output: tests/fixtures/dummy_project/VERIFY-REPORT.md
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from vue3_migration.workflows.auto_migrate_workflow import run as build_migration_plan
from vue3_migration.reporting.diff import write_migration_report
from vue3_migration.models import MigrationConfig

dummy = project_root / "tests" / "fixtures" / "dummy_project"
config = MigrationConfig(project_root=dummy)

print("Building migration plan...")
plan = build_migration_plan(dummy, config)

report_path = dummy / "VERIFY-REPORT.md"
# Use the built-in report writer but override the path
from vue3_migration.reporting.markdown import (
    build_action_plan,
    build_recipes_section,
)

sections = []
sections.append("# Verification Report\n")
sections.append("Generated for manual testing of report accuracy fixes.\n")

# Action plan — the main thing to verify
action_plan = build_action_plan(
    plan.entries_by_component,
    composable_changes=plan.composable_changes,
    project_root=dummy,
    component_changes=plan.component_changes,
)
if action_plan:
    sections.append(action_plan)

# Recipes
recipes = build_recipes_section(plan.entries_by_component)
if recipes:
    sections.append(recipes)

report_path.write_text("\n".join(sections), encoding="utf-8")
print(f"\nReport written to: {report_path}")
print(f"Open it and verify the 4 issues below:\n")
print("  Issue 1: Search 'useChart' — should NOT have 'skipped-lifecycle-only' step")
print("  Issue 2: Search 'usePolling' — should NOT appear in action plan at all")
print("  Issue 3: Search 'this.$once' — should be a SEPARATE step from 'this.$on'")
print("  Issue 4: Search 'useWatcher' — line refs should be 'mixin L28', NOT 'mixin L1'")
