# Migration Report: <span style="color:#2ea043">tests\fixtures\dummy_project\src\components\MultiMixin.vue</span>

## Mixin: selectionMixin

**File:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\mixins\selectionMixin.js</span>

**data:** selectedItems, selectionMode

**computed:** hasSelection, selectionCount

**methods:** selectItem, clearSelection, toggleItem


**Used by component:** selectionCount

**Composable:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\composables\useSelection.js</span>
**Function:** `useSelection`
**Import path:** `@/composables/useSelection`
> <span style="color:#d29922">Verify the above path and function name are correct.</span>

**Status: READY** -- all needed members are present and returned.

---

## Mixin: paginationMixin

**File:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\mixins\paginationMixin.js</span>

**data:** currentPage, pageSize, totalItems

**computed:** totalPages, hasNextPage, hasPrevPage

**methods:** nextPage, prevPage, goToPage, resetPagination


**Used by component:** currentPage

**Composable:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\composables\usePagination.js</span>
**Function:** `usePagination`
**Import path:** `@/composables/usePagination`
> <span style="color:#d29922">Verify the above path and function name are correct.</span>

**Status: READY** -- all needed members are present and returned.

---

## Mixin: authMixin

**File:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\mixins\authMixin.js</span>

**data:** isAuthenticated, currentUser, token

**computed:** isAdmin

**methods:** login, logout, checkAuth


**Lifecycle hooks:** created
> Must be manually migrated (e.g. `mounted` -> `onMounted`).


**Used by component:** isAuthenticated, currentUser

**Composable:** <span style="color:#d29922">NOT FOUND</span>

---

## Mixin: loggingMixin

**File:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\mixins\loggingMixin.js</span>

**data:** logs

**methods:** log


**Lifecycle hooks:** created, mounted, beforeDestroy
> Must be manually migrated (e.g. `mounted` -> `onMounted`).


**Used by component:** logs

**Composable:** <span style="color:#2ea043">C:\Users\eden7\projects\vue3-migration\tests\fixtures\dummy_project\src\composables\useLogging.js</span>
**Function:** `useLogging`
**Import path:** `@/composables/useLogging`
> <span style="color:#d29922">Verify the above path and function name are correct.</span>

**Status: READY** -- all needed members are present and returned.

---


## Action Items

### authMixin: Create composable
- <span style="color:#d29922">A composable needs to be created</span> for `authMixin`.
- It must expose: isAuthenticated, currentUser

### Ready for injection
- `selectionMixin` -> `useSelection` (1 members)
- `paginationMixin` -> `usePagination` (1 members)
- `loggingMixin` -> `useLogging` (1 members)

3 of 4 mixin(s) are ready for partial injection.
