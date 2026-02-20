#!/usr/bin/env python3
"""
Mixin-to-Composable Migration Audit — thin wrapper.

This script delegates to the vue3_migration package.
Use `python -m vue3_migration audit <mixin> [composable]` for the same functionality.
"""

import sys

from vue3_migration.models import MigrationConfig
from vue3_migration.workflows import mixin_workflow


def main():
    if len(sys.argv) < 2:
        print("Usage: python mixin_audit.py <mixin_path> [composable_path]")
        sys.exit(1)
    composable = sys.argv[2] if len(sys.argv) > 2 else None
    mixin_workflow.run(sys.argv[1], composable, MigrationConfig())


if __name__ == "__main__":
    main()
