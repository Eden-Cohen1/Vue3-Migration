# Session 2: Code Generation & Detection Bugs

## Context

This is a Vue 2 → Vue 3 migration tool. It parses mixin files, generates Vue 3 composables, and rewrites `this.x` references. There are 3 bugs where the generated composable code is incorrect or warnings fire on false positives.

## Issues to fix (read each file fully before starting)

All issue files are in `issues/group-2-codegen-detection/`:

1. **issue-sort-reactivity-bug.md** — When a mixin's `data()` property is initialized from a factory-function parameter (e.g., `sortKey: defaultKey`), the tool generates `let sortKey = defaultKey` instead of `const sortKey = ref(defaultKey)`. This breaks reactivity. All `this.sortKey` rewrites also miss `.value`. The data-to-ref transform likely skips `ref()` wrapping when the initial value is a variable rather than a literal.

2. **issue-syntax-error-in-generated-code.md** — The `eventBusMixin` generates a composable where `handleUserAction`'s function body is replaced with object-literal syntax (`'data-updated': handleDataUpdate,`). This is invalid JS. The method body extraction is confusing an object assignment inside `registerEvents` (`this.eventHandlers = { 'data-updated': ... }`) with the `handleUserAction` method body.

3. **issue-string-literal-false-positives.md** — The tool flags `this.$emit`, `this.$refs`, `this.$router`, `this.$route`, `this.$store` inside string literals (single quotes, double quotes, template literals) as real Vue API calls. This produces false `// ❌` inline comments and bogus report steps. The detection regex needs to exclude matches inside string contexts.

## Instructions

- Read all 3 issue files first to understand the full scope
- Use `pytest tests/` to run the full test suite before and after changes
- Use the test fixtures (`tests/fixtures/dummy_project/`) to verify fixes work end-to-end
- Each issue file has an "Investigation" section with hints on where to look
- Issue 2 (syntax error) is the hardest — it's a method-body extraction bug in the JS parser. Be careful with the fix, the parser is hand-rolled string manipulation (`core/js_parser.py`)
- Write tests for each fix
