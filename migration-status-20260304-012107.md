# Vue Migration Status Report
Generated: 2026-03-04 01:21:07

## Summary

- Components with mixins remaining: **60**
- Ready to migrate now: **52**
- Needs manual migration: **4**
- Blocked (composable missing or incomplete): **4**

## Mixin Overview

| Mixin | Used in | Composable |
|-------|---------|------------|
| selectionMixin | 10 | found |
| paginationMixin | 8 | found |
| validationMixin | 6 | found |
| asyncMixin | 4 | found |
| stateMixin | 4 | found |
| formMixin | 4 | found |
| tableMixin | 4 | found |
| loggingMixin | 4 | found |
| lifecycleMixin | 2 | found |
| metricsMixin | 2 | found |
| derivedMixin | 2 | found |
| toggleMixin | 2 | found (needs manual migration) |
| filterMixin | 2 | found |
| workflowMixin | 2 | found |
| actionsMixin | 2 | found |
| authMixin | 2 | needs generation |
| notificationMixin | 2 | needs generation |
| storageMixin | 2 | found (needs manual migration) |
| formattingMixin | 2 | found |
| itemsMixin | 2 | found |

## Components

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\AllLifecycleHooks.vue`
- Mixins: `lifecycleMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\AsyncMethods.vue`
- Mixins: `asyncMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ChainedComputed.vue`
- Mixins: `metricsMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ComplexDefaults.vue`
- Mixins: `stateMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ComplexThisPatterns.vue`
- Mixins: `validationMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ComputedOnlyMixin.vue`
- Mixins: `derivedMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ConditionalLogic.vue`
- Mixins: `validationMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\DataOnlyMixin.vue`
- Mixins: `stateMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\DestructuredParams.vue`
- Mixins: `asyncMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ExistingSetupMixin.vue`
- Mixins: `selectionMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\FullyCovered.vue`
- Mixins: `selectionMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\FuzzyMatch.vue`
- Mixins: `filterMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\GetterSetterComputed.vue`
- Mixins: `formMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\InternalMethodCalls.vue`
- Mixins: `workflowMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\LargeComponent.vue`
- Mixins: `tableMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\LifecycleHooks.vue`
- Mixins: `loggingMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\MethodsOnlyMixin.vue`
- Mixins: `actionsMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\NestedThisAccess.vue`
- Mixins: `tableMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\NotReturnedBlocker.vue`
- Mixins: `paginationMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\OverrideUnblocksComp.vue`
- Mixins: `paginationMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\PartiallyBlocked.vue`
- Mixins: `paginationMixin`, `selectionMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\StringCommentSafety.vue`
- Mixins: `validationMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\TemplateLiterals.vue`
- Mixins: `formattingMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\UnusedMixinMembers.vue`
- Mixins: `itemsMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\WatchHandlers.vue`
- Mixins: `formMixin`
- Status: **Ready** -- all composables found

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\WithOverrides.vue`
- Mixins: `selectionMixin`
- Status: **Ready** -- all composables found

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

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\DynamicReturn.vue`
- Mixins: `toggleMixin`
- Status: **Needs manual migration** -- composable uses reactive() or variable return

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\ReactiveGuard.vue`
- Mixins: `storageMixin`
- Status: **Needs manual migration** -- composable uses reactive() or variable return

### `tests\fixtures\dummy_project\src\components\DynamicReturn.vue`
- Mixins: `toggleMixin`
- Status: **Needs manual migration** -- composable uses reactive() or variable return

### `tests\fixtures\dummy_project\src\components\ReactiveGuard.vue`
- Mixins: `storageMixin`
- Status: **Needs manual migration** -- composable uses reactive() or variable return

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\MultiMixin.vue`
- Mixins: `selectionMixin`, `paginationMixin`, `authMixin`, `loggingMixin`
- Status: **Blocked** -- 1 composable(s) missing or incomplete

### `.worktrees\plan2-this-dollar\tests\fixtures\dummy_project\src\components\NoComposable.vue`
- Mixins: `notificationMixin`
- Status: **Blocked** -- 1 composable(s) missing or incomplete

### `tests\fixtures\dummy_project\src\components\MultiMixin.vue`
- Mixins: `selectionMixin`, `paginationMixin`, `authMixin`, `loggingMixin`
- Status: **Blocked** -- 1 composable(s) missing or incomplete

### `tests\fixtures\dummy_project\src\components\NoComposable.vue`
- Mixins: `notificationMixin`
- Status: **Blocked** -- 1 composable(s) missing or incomplete
