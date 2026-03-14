# Session 1: Report Accuracy Bugs

## Context

This is a Vue 2 → Vue 3 migration tool. It analyzes mixins, generates composables, and produces a migration report with manual steps for the user. There are 4 bugs where the report gives wrong/misleading information.

## Issues to fix (read each file fully before starting)

All issue files are in `issues/group-1-report-accuracy/`:

1. **issue-lifecycle-already-converted.md** — Report emits a `skipped-lifecycle-only` step telling users to "manually convert lifecycle hooks" even when the generated composable already contains `onMounted`/`onBeforeUnmount`. The composable header comment count also mismatches the report step count.

2. **issue-missing-composable-files.md** — Report lists manual steps and "unused members" for composables that were never generated (skipped due to `skipped-lifecycle-only`). Users follow steps pointing to files that don't exist on disk.

3. **issue-once-mislabeled-as-on.md** — `this.$once` calls are grouped under the `this.$on` label in the report. They're different APIs needing different migration recipes. `$once` should get its own step/label.

4. **issue-wrong-line-number-refs.md** — Report steps for `this.$watch` always reference "mixin L1" instead of the actual line numbers where `this.$watch` calls appear. Other patterns like `this.$emit` resolve lines correctly.

## Instructions

- Read all 4 issue files first to understand the full scope
- Use `pytest tests/` to run the full test suite before and after changes
- Use the test fixtures (`tests/fixtures/dummy_project/`) to verify fixes work end-to-end
- Each issue file has an "Investigation" section with hints on where to look in the codebase
- Fix bugs in order — issues 1 and 2 are closely related (both involve `skipped-lifecycle-only`)
- Write tests for each fix
