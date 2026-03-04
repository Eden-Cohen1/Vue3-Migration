# Vue Migration Status Report
Generated: 2026-03-03 20:55:53

## Summary

- Components with mixins remaining: **30**
- Ready to migrate now: **28**
- Blocked (composable missing or incomplete): **2**

## Mixin Overview

| Mixin | Used in | Composable |
|-------|---------|------------|
| selectionMixin | 5 | ✓ found |
| paginationMixin | 4 | ✓ found |
| validationMixin | 3 | ✓ found |
| asyncMixin | 2 | ✓ found |
| stateMixin | 2 | ✓ found |
| formMixin | 2 | ✓ found |
| tableMixin | 2 | ✓ found |
| loggingMixin | 2 | ✓ found |
| lifecycleMixin | 1 | ✓ found |
| metricsMixin | 1 | ✓ found |
| derivedMixin | 1 | ✓ found |
| toggleMixin | 1 | ✓ found |
| filterMixin | 1 | ✓ found |
| workflowMixin | 1 | ✓ found |
| actionsMixin | 1 | ✓ found |
| authMixin | 1 | needs generation |
| notificationMixin | 1 | needs generation |
| storageMixin | 1 | ✓ found |
| formattingMixin | 1 | ✓ found |
| itemsMixin | 1 | ✓ found |

## Components

### `tests\fixtures\dummy_project\src\components\AllLifecycleHooks.vue`
- Mixins: `lifecycleMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\AsyncMethods.vue`
- Mixins: `asyncMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ChainedComputed.vue`
- Mixins: `metricsMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ComplexDefaults.vue`
- Mixins: `stateMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ComplexThisPatterns.vue`
- Mixins: `validationMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ComputedOnlyMixin.vue`
- Mixins: `derivedMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ConditionalLogic.vue`
- Mixins: `validationMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\DataOnlyMixin.vue`
- Mixins: `stateMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\DestructuredParams.vue`
- Mixins: `asyncMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\DynamicReturn.vue`
- Mixins: `toggleMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ExistingSetupMixin.vue`
- Mixins: `selectionMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\FullyCovered.vue`
- Mixins: `selectionMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\FuzzyMatch.vue`
- Mixins: `filterMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\GetterSetterComputed.vue`
- Mixins: `formMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\InternalMethodCalls.vue`
- Mixins: `workflowMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\LargeComponent.vue`
- Mixins: `tableMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\LifecycleHooks.vue`
- Mixins: `loggingMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\MethodsOnlyMixin.vue`
- Mixins: `actionsMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\NestedThisAccess.vue`
- Mixins: `tableMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\NotReturnedBlocker.vue`
- Mixins: `paginationMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\OverrideUnblocksComp.vue`
- Mixins: `paginationMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\PartiallyBlocked.vue`
- Mixins: `paginationMixin`, `selectionMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\ReactiveGuard.vue`
- Mixins: `storageMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\StringCommentSafety.vue`
- Mixins: `validationMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\TemplateLiterals.vue`
- Mixins: `formattingMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\UnusedMixinMembers.vue`
- Mixins: `itemsMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\WatchHandlers.vue`
- Mixins: `formMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\WithOverrides.vue`
- Mixins: `selectionMixin`
- Status: **Ready** -- all composables found

### `tests\fixtures\dummy_project\src\components\MultiMixin.vue`
- Mixins: `selectionMixin`, `paginationMixin`, `authMixin`, `loggingMixin`
- Status: **Blocked** -- 1 composable(s) missing or incomplete

### `tests\fixtures\dummy_project\src\components\NoComposable.vue`
- Mixins: `notificationMixin`
- Status: **Blocked** -- 1 composable(s) missing or incomplete
