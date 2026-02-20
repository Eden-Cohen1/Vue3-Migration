#!/usr/bin/env python3
"""
Component Mixin Migration — thin wrapper.

This script delegates to the vue3_migration package.
Use `python -m vue3_migration component <path>` for the same functionality.
"""

import sys

from vue3_migration.models import MigrationConfig
from vue3_migration.workflows import component_workflow


def main():
    if len(sys.argv) < 2:
        print("Usage: python component_migrate.py <component_path>")
        sys.exit(1)
    component_workflow.run(sys.argv[1], MigrationConfig())


if __name__ == "__main__":
    main()
