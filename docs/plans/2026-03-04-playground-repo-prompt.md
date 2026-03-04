# Claude Code Prompt: Build Vue 3 Migration Playground

> **Usage:** Copy everything below the line into a new Claude Code session in an empty directory.
> This prompt instructs Claude Code to build a fully runnable Vue 3 project management app
> that uses Options API + mixins — the perfect playground for testing `vue3-migration` (npm).

---

## THE PROMPT

Build a fully runnable **Vue 3 project management application** (Jira-like) that serves as a migration playground. The app must use **Options API + mixins everywhere** — the goal is to test the `vue3-migration` npm tool that converts Options API + mixins → Composition API + composables.

### Critical Requirements

1. **The app MUST work** — `npm run dev` starts the app, all pages render with mock data, navigation works, interactions work (clicking, forms, filtering, sorting). No backend needed — use in-memory mock data services.
2. **~60 Vue components** across views, layout, and feature modules.
3. **20 mixins** covering every migration pattern.
4. **10 composables** (for half the mixins) — with intentionally varying quality (some complete, some incomplete).
5. **6 Pinia stores** for state management.
6. **Vue Router 4** with multiple routes, nested routes, and route guards.
7. Every component uses Options API (`data()`, `computed`, `methods`, `watch`, lifecycle hooks). **Zero `<script setup>` usage.**

---

### Tech Stack

```
Vue 3.3+ (Options API only — no <script setup>)
Vue Router 4
Pinia
Vite
Tailwind CSS (for quick, realistic UI)
```

Initialize with: `npm create vite@latest . -- --template vue` then add router, pinia, tailwind.

---

### Project Structure

```
src/
├── App.vue
├── main.js
├── router/
│   └── index.js                    # All routes + guards
├── stores/                         # 6 Pinia stores
│   ├── auth.js
│   ├── projects.js
│   ├── tasks.js
│   ├── users.js
│   ├── notifications.js
│   └── settings.js
├── services/                       # Mock data layer
│   ├── mockData.js                 # All seed data
│   └── api.js                      # Simulated async API (setTimeout)
├── mixins/                         # 20 mixins
│   ├── authMixin.js
│   ├── formMixin.js
│   ├── validationMixin.js
│   ├── tableMixin.js
│   ├── paginationMixin.js
│   ├── searchMixin.js
│   ├── filterMixin.js
│   ├── sortMixin.js
│   ├── selectionMixin.js
│   ├── modalMixin.js
│   ├── loadingMixin.js
│   ├── notificationMixin.js
│   ├── dragDropMixin.js
│   ├── chartMixin.js
│   ├── exportMixin.js
│   ├── permissionMixin.js
│   ├── commentMixin.js
│   ├── keyboardShortcutMixin.js
│   ├── themeMixin.js
│   └── undoRedoMixin.js
├── composables/                    # 10 composables (for HALF the mixins)
│   ├── useForm.js
│   ├── useTable.js
│   ├── useSearch.js
│   ├── useModal.js
│   ├── useLoading.js
│   ├── useSelection.js
│   ├── useChart.js
│   ├── usePermission.js
│   ├── usePagination.js
│   └── useValidation.js
├── components/
│   ├── layout/                     # ~5 layout components
│   │   ├── AppHeader.vue
│   │   ├── AppSidebar.vue
│   │   ├── AppFooter.vue
│   │   ├── AppBreadcrumb.vue
│   │   └── ThemeSwitcher.vue
│   ├── common/                     # ~12 shared components
│   │   ├── BaseModal.vue
│   │   ├── ConfirmDialog.vue
│   │   ├── DataTable.vue
│   │   ├── SearchBar.vue
│   │   ├── FilterPanel.vue
│   │   ├── PaginationBar.vue
│   │   ├── LoadingSpinner.vue
│   │   ├── EmptyState.vue
│   │   ├── StatusBadge.vue
│   │   ├── FileUploader.vue
│   │   ├── RichTextEditor.vue
│   │   └── ExportButton.vue
│   ├── dashboard/                  # ~5 dashboard components
│   │   ├── StatsOverview.vue
│   │   ├── RecentActivity.vue
│   │   ├── ProjectSummaryChart.vue
│   │   ├── TaskDistribution.vue
│   │   └── UpcomingDeadlines.vue
│   ├── projects/                   # ~7 project components
│   │   ├── ProjectCard.vue
│   │   ├── ProjectList.vue
│   │   ├── ProjectForm.vue
│   │   ├── ProjectBoard.vue
│   │   ├── ProjectMembers.vue
│   │   ├── ProjectSettings.vue
│   │   └── ProjectTimeline.vue
│   ├── tasks/                      # ~8 task components
│   │   ├── TaskCard.vue
│   │   ├── TaskList.vue
│   │   ├── TaskForm.vue
│   │   ├── TaskDetail.vue
│   │   ├── TaskComments.vue
│   │   ├── TaskBoard.vue
│   │   ├── KanbanColumn.vue
│   │   └── TaskFilters.vue
│   ├── users/                      # ~5 user components
│   │   ├── UserCard.vue
│   │   ├── UserList.vue
│   │   ├── UserForm.vue
│   │   ├── UserAvatar.vue
│   │   └── UserProfile.vue
│   ├── reports/                    # ~4 report components
│   │   ├── ReportBuilder.vue
│   │   ├── ReportChart.vue
│   │   ├── ReportTable.vue
│   │   └── ReportExport.vue
│   └── notifications/             # ~3 notification components
│       ├── NotificationList.vue
│       ├── NotificationItem.vue
│       └── NotificationBell.vue
├── views/                          # ~11 page views
│   ├── DashboardView.vue
│   ├── ProjectsView.vue
│   ├── ProjectDetailView.vue
│   ├── TasksView.vue
│   ├── TaskDetailView.vue
│   ├── UsersView.vue
│   ├── ReportsView.vue
│   ├── CalendarView.vue
│   ├── SettingsView.vue
│   ├── LoginView.vue
│   └── NotFoundView.vue
└── utils/
    └── helpers.js                  # Date formatting, etc.
```

**Total: ~60 Vue components + 20 mixins + 10 composables + 6 stores**

---

### Mixin Specifications

Each mixin must be a **standard default export object** (no factory functions — except one, see edge cases). Every mixin must use `this.` to access its own members and use various `this.$` patterns.

#### 1. `authMixin.js`
- **data:** `user`, `isAuthenticated`, `authError`, `loginAttempts`
- **computed:** `isAdmin`, `userDisplayName`, `hasPermission`
- **methods:** `login(credentials)`, `logout()`, `checkAuth()`, `refreshToken()`
- **lifecycle:** `created` → calls `checkAuth()`
- **this.$ patterns:** `this.$router.push('/login')`, `this.$emit('auth-changed')`
- **NO composable** (tests BLOCKED_NO_COMPOSABLE)

#### 2. `formMixin.js`
- **data:** `formData`, `originalData`, `isDirty`, `isSubmitting`, `formErrors`
- **computed:** `hasChanges`, `isFormValid`, `dirtyFields`
- **methods:** `initForm(data)`, `resetForm()`, `submitForm()`, `setFieldError(field, msg)`
- **lifecycle:** `beforeMount` → calls `initForm()`
- **this.$ patterns:** `this.$refs.form`, `this.$nextTick()`, `this.$emit('form-submitted')`
- **Composable: `useForm.js`** — INCOMPLETE: missing `setFieldError` and `dirtyFields` (tests BLOCKED_MISSING_MEMBERS)

#### 3. `validationMixin.js`
- **data:** `rules`, `errors`, `isValidating`
- **computed:** `isValid`, `firstError`, `errorCount`
- **methods:** `validate()`, `validateField(field)`, `clearErrors()`, `addRule(field, rule)`
- **this.$ patterns:** `this.$emit('validation-complete', this.isValid)`
- **Composable: `useValidation.js`** — COMPLETE (tests READY path)

#### 4. `tableMixin.js`
- **data:** `rows`, `columns`, `sortField`, `sortDirection`, `expandedRows`
- **computed:** `sortedRows`, `visibleColumns`, `hasExpandedRows`
- **methods:** `sortBy(field)`, `toggleRow(id)`, `collapseAll()`, `getColumnClass(col)`
- **this.$ patterns:** `this.$refs.tableContainer`, `this.$el.querySelector()`
- **Composable: `useTable.js`** — NOT_RETURNED: `sortDirection` and `collapseAll` defined but not in `return {}` (tests BLOCKED_NOT_RETURNED)

#### 5. `paginationMixin.js`
- **data:** `currentPage`, `pageSize`, `totalItems`
- **computed:** `totalPages`, `hasPrevPage`, `hasNextPage`, `paginatedOffset`
- **methods:** `nextPage()`, `prevPage()`, `goToPage(n)`, `changePageSize(size)`
- **Composable: `usePagination.js`** — INCOMPLETE: missing `hasPrevPage` and `prevPage` (tests component-override-unblocks when component defines its own `hasPrevPage`)

#### 6. `searchMixin.js`
- **data:** `searchQuery`, `searchResults`, `isSearching`, `searchHistory`
- **computed:** `hasResults`, `resultCount`, `recentSearches`
- **methods:** `search()`, `clearSearch()`, `addToHistory(query)` (search is debounced via `setTimeout`)
- **watch:** `searchQuery` with debounce (300ms timeout in handler)
- **this.$ patterns:** `this.$refs.searchInput.focus()`
- **Composable: `useSearch.js`** — COMPLETE

#### 7. `filterMixin.js`
- **data:** `filters`, `activeFilters`, `filterOptions`
- **computed:** `activeFilterCount`, `isFiltered`, `appliedFilterSummary`
- **methods:** `applyFilter(key, value)`, `removeFilter(key)`, `clearAllFilters()`, `getFilterOptions(key)`
- **watch:** `activeFilters` deep watcher
- **NO composable** (tests BLOCKED_NO_COMPOSABLE)

#### 8. `sortMixin.js`
- **data:** `sortKey`, `sortOrder`, `multiSort`, `sortHistory`
- **computed:** `sortIndicator`, `isSorted`
- **methods:** `toggleSort(key)`, `clearSort()`, `addSortLevel(key)`
- **NO composable**

#### 9. `selectionMixin.js`
- **data:** `selectedItems`, `selectionMode`, `lastSelected`
- **computed:** `hasSelection`, `selectionCount`, `allSelected`
- **methods:** `select(item)`, `deselect(item)`, `toggleSelection(item)`, `selectAll(items)`, `deselectAll()`, `isSelected(item)`
- **this.$ patterns:** `this.$emit('selection-changed', this.selectedItems)`
- **Composable: `useSelection.js`** — NOT_RETURNED: `deselectAll` defined but not in return (tests BLOCKED_NOT_RETURNED)

#### 10. `modalMixin.js`
- **data:** `isOpen`, `modalData`, `modalOptions`
- **computed:** `modalTitle`, `hasData`
- **methods:** `openModal(data, options)`, `closeModal()`, `confirmModal()`
- **lifecycle:** `mounted` → adds keydown listener for Escape; `beforeUnmount` → removes it
- **this.$ patterns:** `this.$refs.modalOverlay`, `this.$emit('modal-closed')`, `this.$nextTick()`
- **Composable: `useModal.js`** — COMPLETE

#### 11. `loadingMixin.js`
- **data:** `isLoading`, `loadingMessage`, `error`, `retryCount`
- **computed:** `hasError`, `canRetry`
- **methods:** `startLoading(msg)`, `stopLoading()`, `setError(err)`, `retry(fn)`
- **this.$ patterns:** `this.$forceUpdate()`
- **Composable: `useLoading.js`** — COMPLETE

#### 12. `notificationMixin.js`
- **data:** `notifications`, `unreadCount`, `notificationSettings`
- **computed:** `hasUnread`, `sortedNotifications`, `groupedByType`
- **methods:** `addNotification(n)`, `markAsRead(id)`, `markAllRead()`, `removeNotification(id)`, `clearAll()`
- **lifecycle:** `created` → loads notification settings
- **this.$ patterns:** `this.$emit('notification-added')`, `this.$nextTick()`
- **NO composable**

#### 13. `dragDropMixin.js`
- **data:** `isDragging`, `dragItem`, `dropTarget`, `dragOverIndex`
- **computed:** `hasDragItem`, `dropPosition`
- **methods:** `onDragStart(event, item)`, `onDragOver(event, index)`, `onDrop(event)`, `onDragEnd()`
- **this.$ patterns:** `this.$refs.dragContainer`, `this.$el.classList`, `this.$emit('item-reordered')`
- **NO composable**

#### 14. `chartMixin.js`
- **data:** `chartData`, `chartOptions`, `chartType`, `isChartReady`
- **computed:** `formattedChartData`, `chartColors`, `hasData`
- **methods:** `prepareChartData(raw)`, `updateChart()`, `resizeChart()`, `exportChart(format)`
- **lifecycle:** `mounted` → calls `resizeChart()`; `beforeUnmount` → cleanup
- **watch:** `chartData` deep watcher → calls `updateChart()`
- **this.$ patterns:** `this.$refs.chartCanvas`, `this.$el.offsetWidth`, `this.$nextTick()`
- **Composable: `useChart.js`** — COMPLETE

#### 15. `exportMixin.js`
- **data:** `exportFormat`, `exportColumns`, `isExporting`, `exportProgress`
- **computed:** `availableFormats`, `exportFileName`
- **methods:** `exportToCSV(data)`, `exportToPDF(data)`, `downloadFile(blob, name)`, `prepareExportData()`
- **NO composable**

#### 16. `permissionMixin.js`
- **data:** `userPermissions`, `roleMap`
- **computed:** `canEdit`, `canDelete`, `canCreate`, `isManager`, `permissionLevel`
- **methods:** `checkPermission(action)`, `requestPermission(action)`, `hasRole(role)`
- **this.$ patterns:** `this.$router.push('/unauthorized')`
- **Composable: `usePermission.js`** — INCOMPLETE: missing `canDelete` and `hasRole` (tests BLOCKED_MISSING + component override can unblock `canDelete`)

#### 17. `commentMixin.js`
- **data:** `comments`, `newComment`, `editingComment`, `isLoadingComments`
- **computed:** `commentCount`, `sortedComments`, `hasComments`
- **methods:** `addComment()`, `editComment(id, text)`, `deleteComment(id)`, `loadComments(entityId)`, `replyToComment(parentId, text)`
- **lifecycle:** `mounted` → loads comments
- **this.$ patterns:** `this.$refs.commentInput`, `this.$emit('comment-added')`, `this.$nextTick()`
- **NO composable**

#### 18. `keyboardShortcutMixin.js`
- **data:** `shortcuts`, `isShortcutsEnabled`
- **methods:** `registerShortcut(key, handler)`, `unregisterShortcut(key)`, `handleKeyDown(event)`
- **lifecycle:** `mounted` → `document.addEventListener('keydown', this.handleKeyDown)`; `beforeUnmount` → removes listener
- **this.$ patterns:** `this.$el`, `this.$emit('shortcut-triggered')`
- **NO composable**

#### 19. `themeMixin.js`
- **data:** `currentTheme`, `themes`, `customColors`
- **computed:** `themeClass`, `isDarkMode`, `themeVariables`
- **methods:** `setTheme(name)`, `toggleDarkMode()`, `applyTheme()`
- **lifecycle:** `created` → loads saved theme from localStorage
- **watch:** `currentTheme` → calls `applyTheme()`
- **this.$ patterns:** `this.$el.style`, `this.$forceUpdate()`
- **NO composable**

#### 20. `undoRedoMixin.js`
- **data:** `undoStack`, `redoStack`, `maxHistory`
- **computed:** `canUndo`, `canRedo`, `historyLength`
- **methods:** `pushState(state)`, `undo()`, `redo()`, `clearHistory()`
- **this.$ patterns:** `this.$emit('state-changed')`
- **NO composable**

---

### Composable Quality Tiers (CRITICAL — read carefully)

The composables must have **intentionally varying quality** to test the migration tool's patching logic. Each composable MUST follow the standard format:

```javascript
import { ref, computed } from 'vue'

export function useXxx() {
  // declarations...
  return { /* only some members */ }
}
```

| Composable | Quality Tier | What's wrong |
|---|---|---|
| `useValidation.js` | COMPLETE | All members present and returned |
| `useSearch.js` | COMPLETE | All members present and returned |
| `useModal.js` | COMPLETE | All members present and returned |
| `useLoading.js` | COMPLETE | All members present and returned |
| `useChart.js` | COMPLETE | All members present and returned |
| `useForm.js` | MISSING_MEMBERS | `setFieldError` and `dirtyFields` not defined at all |
| `usePagination.js` | MISSING_MEMBERS | `hasPrevPage` and `prevPage` not defined at all |
| `usePermission.js` | MISSING_MEMBERS | `canDelete` and `hasRole` not defined at all |
| `useTable.js` | NOT_RETURNED | `sortDirection` and `collapseAll` ARE defined but NOT in the `return {}` |
| `useSelection.js` | NOT_RETURNED | `deselectAll` IS defined but NOT in the `return {}` |

**The app must still work with these incomplete composables** because **no component uses the composables yet** — all components still use the mixins. The composables are "prepared but not wired in." The migration tool discovers them, patches them, and wires them into components.

---

### `this.$` Pattern Coverage

Distribute these patterns across components. Every pattern must appear in at least 2 different components:

| Pattern | Where to use | Count |
|---|---|---|
| `this.$refs.xxx` | Forms, modals, tables, search, charts | 8+ |
| `this.$emit('event', data)` | Child components (cards, forms, items) | 12+ |
| `this.$router.push(path)` | Auth, navigation, links | 5+ |
| `this.$router.replace(path)` | Auth redirect | 2+ |
| `this.$route.params.id` | Detail views | 4+ |
| `this.$route.query` | List views with URL filters | 3+ |
| `this.$nextTick(callback)` | After DOM updates (forms, charts, scroll) | 6+ |
| `this.$el.querySelector()` | Direct DOM access (charts, drag-drop) | 3+ |
| `this.$el.offsetWidth` | Layout calculations | 2+ |
| `this.$parent.$emit()` | Anti-pattern but real | 2 |
| `this.$forceUpdate()` | Theme changes, chart resize | 2 |
| `this.$watch('prop', handler)` | Programmatic watchers in mounted() | 3+ |
| `this.$slots.default` | Slot inspection in layout | 2 |
| `this.$attrs` | Attribute forwarding in wrappers | 2 |

---

### Structural Edge Cases (include these)

1. **Factory function mixin** — Create ONE mixin as a factory function to trigger structural warning:
   ```javascript
   // In one of the simpler mixins, e.g., sortMixin.js:
   export default function createSortMixin(defaultKey = 'name') {
     return {
       data() { return { sortKey: defaultKey, ... } },
       ...
     }
   }
   ```
   And use it as `mixins: [sortMixin('created_at')]`

2. **Nested mixin** — One mixin should use another mixin internally:
   ```javascript
   // tableMixin.js uses sortMixin and paginationMixin:
   import sortMixin from './sortMixin'
   import paginationMixin from './paginationMixin'
   export default {
     mixins: [sortMixin, paginationMixin],
     ...
   }
   ```

3. **this-aliasing** — In 2-3 components, use `const self = this` or `const vm = this` pattern inside callbacks:
   ```javascript
   mounted() {
     const self = this
     setTimeout(function() {
       self.isReady = true
     }, 100)
   }
   ```

4. **Multiple mixins per component** — At least 10 components should use 2+ mixins. Some should mix READY and BLOCKED mixins to test partial migration.

5. **Component overrides** — At least 3 components should define their own version of a mixin member (e.g., component defines its own `canDelete` computed, which would unblock the `usePermission` composable's missing `canDelete`).

---

### Pinia Store Integration

All stores use the standard Pinia `defineStore` pattern. Components access stores in two ways:

**Way 1 — Direct import in methods (most components):**
```javascript
import { useProjectStore } from '@/stores/projects'

export default {
  methods: {
    loadProjects() {
      const store = useProjectStore()
      this.projects = store.projects
    }
  }
}
```

**Way 2 — mapStores/mapState/mapActions (a few components, for migration variety):**
```javascript
import { mapState, mapActions } from 'pinia'
import { useTaskStore } from '@/stores/tasks'

export default {
  computed: {
    ...mapState(useTaskStore, ['tasks', 'taskCount'])
  },
  methods: {
    ...mapActions(useTaskStore, ['addTask', 'deleteTask'])
  }
}
```

Use Way 1 for ~70% of store access, Way 2 for ~30%.

**Store specs:**

1. **`auth.js`** — `user`, `token`, `isAuthenticated`, `login()`, `logout()`, `checkSession()`
2. **`projects.js`** — `projects[]`, `currentProject`, `fetchProjects()`, `createProject()`, `updateProject()`, `deleteProject()`
3. **`tasks.js`** — `tasks[]`, `fetchTasks(projectId)`, `createTask()`, `updateTask()`, `moveTask(id, status)`, `deleteTask()`
4. **`users.js`** — `users[]`, `fetchUsers()`, `updateUser()`, `getUserById()`
5. **`notifications.js`** — `notifications[]`, `unreadCount`, `addNotification()`, `markRead()`, `markAllRead()`
6. **`settings.js`** — `settings{}`, `theme`, `language`, `updateSettings()`, `resetSettings()`

---

### Mock Data Service

Create `src/services/mockData.js` with realistic seed data:

- **5 projects** with names, descriptions, statuses, dates, member lists
- **40 tasks** distributed across projects with title, description, status (todo/in-progress/review/done), priority (low/medium/high/critical), assignee, dates, tags
- **8 users** with names, emails, roles (admin/manager/developer/viewer), avatars (use ui-avatars.com URLs)
- **20 comments** distributed across tasks
- **15 notifications** of various types (task-assigned, comment-added, project-updated, deadline-approaching)
- **Activity log entries** (20 entries)

Create `src/services/api.js` that simulates async API calls:
```javascript
// All methods return Promises with setTimeout (200-500ms delay)
export const api = {
  getProjects() { return delay(() => [...mockProjects]) },
  getProject(id) { ... },
  getTasks(projectId) { ... },
  // etc.
}
```

---

### Router Configuration

```javascript
const routes = [
  { path: '/login', component: LoginView, meta: { guest: true } },
  {
    path: '/',
    component: AppLayout, // layout wrapper with header + sidebar
    meta: { requiresAuth: true },
    children: [
      { path: '', redirect: '/dashboard' },
      { path: 'dashboard', component: DashboardView },
      { path: 'projects', component: ProjectsView },
      { path: 'projects/:id', component: ProjectDetailView },
      { path: 'tasks', component: TasksView },
      { path: 'tasks/:id', component: TaskDetailView },
      { path: 'users', component: UsersView },
      { path: 'reports', component: ReportsView },
      { path: 'calendar', component: CalendarView },
      { path: 'settings', component: SettingsView },
    ]
  },
  { path: '/:pathMatch(.*)*', component: NotFoundView }
]
```

Route guard: check auth store, redirect to `/login` if not authenticated.

---

### Component Mixin Distribution

Every component MUST use at least one mixin. Distribute as follows:

| Component | Mixins Used | Expected Status |
|---|---|---|
| DataTable | tableMixin, selectionMixin, paginationMixin | BLOCKED (table NOT_RETURNED) |
| SearchBar | searchMixin | READY |
| FilterPanel | filterMixin | BLOCKED (no composable) |
| BaseModal | modalMixin, keyboardShortcutMixin | READY (modal) + BLOCKED (keyboard) |
| ProjectForm | formMixin, validationMixin | BLOCKED (form MISSING) |
| ProjectList | sortMixin, filterMixin, paginationMixin | BLOCKED (sort + filter no composable) |
| TaskForm | formMixin, validationMixin | BLOCKED (form MISSING) |
| TaskBoard | dragDropMixin, selectionMixin | BLOCKED (dragDrop no composable) |
| TaskCard | permissionMixin | BLOCKED (permission MISSING) but define own `canDelete` to test override-unblocks |
| UserList | tableMixin, searchMixin, selectionMixin | BLOCKED (table NOT_RETURNED) |
| UserForm | formMixin, validationMixin | BLOCKED (form MISSING) |
| ReportBuilder | chartMixin, exportMixin, filterMixin | READY (chart) + BLOCKED (export, filter) |
| ReportChart | chartMixin | READY |
| StatsOverview | loadingMixin, chartMixin | READY |
| RecentActivity | loadingMixin, paginationMixin | BLOCKED (pagination MISSING) but define own `hasPrevPage` to test override |
| NotificationList | notificationMixin, paginationMixin | BLOCKED (notification no composable) |
| ProjectBoard | dragDropMixin, selectionMixin | BLOCKED (dragDrop no composable) |
| ThemeSwitcher | themeMixin | BLOCKED (no composable) |
| ProjectSettings | formMixin, permissionMixin | BLOCKED (both incomplete) |
| TaskDetail | commentMixin, loadingMixin, permissionMixin | BLOCKED (comment no composable) |
| SettingsView | formMixin, validationMixin, themeMixin | BLOCKED (form MISSING + theme no composable) |
| LoginView | authMixin, formMixin, validationMixin | BLOCKED (auth no composable) |
| DashboardView | loadingMixin, chartMixin | READY |
| CalendarView | filterMixin, loadingMixin | BLOCKED (filter no composable) |
| ExportButton | exportMixin | BLOCKED (no composable) |
| ConfirmDialog | modalMixin | READY |

*Remaining components: distribute mixins to ensure every mixin is used by at least 3 components.*

---

### Lifecycle Hook Coverage

Ensure ALL these lifecycle hooks appear across the codebase:

- `beforeCreate` — 1 component (auth check)
- `created` — 10+ components (data fetching, initialization)
- `beforeMount` — 3+ components
- `mounted` — 15+ components (DOM setup, event listeners, focus)
- `beforeUpdate` — 2 components
- `updated` — 2 components
- `activated` — 1 component (keep-alive cache)
- `deactivated` — 1 component
- `beforeUnmount` — 8+ components (cleanup listeners, timers)
- `unmounted` — 2 components
- `errorCaptured` — 1 component (error boundary)

---

### Watch Patterns

Include all these watcher styles:

```javascript
// 1. Simple watcher
watch: {
  searchQuery(newVal, oldVal) { this.search() }
}

// 2. Deep watcher with options
watch: {
  filters: {
    handler(newVal) { this.applyFilters() },
    deep: true
  }
}

// 3. Immediate watcher
watch: {
  projectId: {
    handler(id) { this.loadProject(id) },
    immediate: true
  }
}

// 4. String method name handler
watch: {
  currentTheme: 'applyTheme'
}

// 5. Dot-notation nested path
watch: {
  'formData.email'(val) { this.validateField('email') }
}
```

---

### Computed Patterns

Include both simple and getter/setter computed:

```javascript
computed: {
  // Simple getter (majority)
  fullName() {
    return this.firstName + ' ' + this.lastName
  },

  // Getter + setter (at least 3 components)
  selectedStatus: {
    get() { return this.filters.status },
    set(val) { this.applyFilter('status', val) }
  }
}
```

---

### Quality Checklist

Before finishing, verify:

- [ ] `npm run dev` starts without errors
- [ ] All routes render real content (not placeholder text)
- [ ] Dashboard shows charts/stats with mock data
- [ ] Project list shows 5 projects, clickable to detail
- [ ] Task board shows kanban columns with draggable-looking cards
- [ ] Forms have real fields and validation feedback
- [ ] Search bar filters results
- [ ] Pagination works on lists
- [ ] Modal opens/closes
- [ ] Theme toggle switches classes
- [ ] Login page has form (auto-login with any credentials for demo)
- [ ] Every `.vue` file uses Options API with `export default {}`
- [ ] Every mixin is imported and used by at least 3 components
- [ ] Every `this.$` pattern from the table appears in the codebase
- [ ] Composables follow the exact quality tiers specified
- [ ] No `<script setup>` anywhere
- [ ] Factory function mixin exists (sortMixin)
- [ ] Nested mixin exists (tableMixin uses others)
- [ ] `const self = this` pattern exists in 2-3 places
- [ ] Component overrides exist for `canDelete` and `hasPrevPage`
- [ ] 10+ components use multiple mixins

---

### Execution Order

Build in this order to avoid import errors:

1. **Scaffold** — Vite + Vue 3 + install deps (router, pinia, tailwind)
2. **Mock data + API service** — Foundation everything else depends on
3. **Pinia stores** — Depend on mock data
4. **Utils/helpers** — Small utility functions
5. **Mixins** — All 20 mixins (no component dependencies)
6. **Composables** — All 10 composables (intentionally incomplete ones)
7. **Router** — Route definitions
8. **Layout components** — AppHeader, AppSidebar, etc.
9. **Common components** — Shared building blocks
10. **Feature components** — Dashboard, projects, tasks, users, reports, notifications
11. **View pages** — Wire everything together
12. **App.vue + main.js** — Final wiring
13. **Verify** — Run `npm run dev` and fix any errors

**IMPORTANT: Build ALL files. Do not skip any. Do not use placeholder content. Every component must have real, working template + script.**
