# Mixin Audit: selectionMixin.js

## Mixin Members

**data:** selectedItems, selectionMode

**computed:** hasSelection, selectionCount

**methods:** selectItem, clearSelection, toggleItem


## Lifecycle Hooks

*No lifecycle hooks found in this mixin.*


## Files Importing the Mixin (4)

### tests\fixtures\dummy_project\src\components\FullyCovered.vue

Uses: selectedItems, hasSelection, selectionCount, clearSelection, toggleItem

### tests\fixtures\dummy_project\src\components\MultiMixin.vue

Uses: selectionCount

### tests\fixtures\dummy_project\src\components\PartiallyBlocked.vue

Uses: selectionCount

### tests\fixtures\dummy_project\src\components\WithOverrides.vue

Uses: selectedItems, selectionMode, selectionCount, clearSelection


## Composable Status

All used members are present in the composable.


## Summary

- Total mixin members: 7

- Lifecycle hooks: 0

- Members used across codebase: 6

- Unused members (candidates for removal): selectItem
