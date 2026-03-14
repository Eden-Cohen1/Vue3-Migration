# Session 3: Watch Transformation Bugs

## Context

This is a Vue 2 → Vue 3 migration tool. It converts `this.$watch()` calls from Vue 2 mixins into Vue 3 Composition API `watch()` calls. There are 2 bugs where the tool passes through Vue 2-only handler formats that are invalid in Vue 3.

## Issues to fix (read each file fully before starting)

All issue files are in `issues/group-3-watch-transform/`:

1. **issue-watch-string-handler.md** — `this.$watch('prop', 'methodName')` becomes `watch(ref, 'methodName')`. Vue 3's `watch()` doesn't accept string handlers. The string should be resolved to the actual function reference: `watch(ref, methodName)`.

2. **issue-watch-array-handlers.md** — `this.$watch('prop', ['handler1', 'handler2', 'handler3'])` becomes `watch(ref, ['handler1', 'handler2', 'handler3'])`. Vue 3's `watch()` doesn't accept arrays of string handlers. The tool should generate a single wrapper callback that invokes all handlers in order:
   ```js
   watch(ref, (newVal, oldVal) => {
     handler1(newVal, oldVal)
     handler2(newVal, oldVal)
     handler3(newVal, oldVal)
   })
   ```

## Instructions

- Read both issue files first — they're closely related and likely share the same code path
- Use `pytest tests/` to run the full test suite before and after changes
- The `this.$watch` transformation logic is the place to look — find where watch calls are parsed and converted
- The string-handler case (issue 1) is simpler — fix it first, then extend for the array case
- Write tests for each fix
