# Vue3-Migration Tool — Bug Report

Four bugs found by evaluating the tool's output on the test repo. Each section shows the **before** (pre-patch composable or component) and **after** (what the tool produced), along with the **expected correct output**.

Source of truth: `git diff` of working tree vs `HEAD`.

---

## Bug 1: Patcher Destroys Closing Braces (SyntaxError)

**Affected files:** `usePermission.js`, `useTable.js`, `usePagination.js`, `useForm.js`, `useSelection.js` (all 5 patched composables)

**Result:** `SyntaxError: Unexpected end of input` — none of these files can be parsed.

**Pattern:** In every case the pre-patch file ends with two closing braces — one for the return object (2-space indent) and one for the function (0-space indent):

```
    member1,
    member2
  }
}
```

After patching, both are replaced with a single `}` at 0-space indent, and newly added members have inconsistent indentation:

```
    member2,
      newMember,

}
```

---

### 1a. usePermission.js

**Before (valid):**

```js
import { ref, computed } from "vue";

export function usePermission() {
  const userPermissions = ref([]);
  const roleMap = ref({
    admin: ["read", "write", "create", "delete", "manage"],
    editor: ["read", "write", "create"],
    viewer: ["read"],
  });

  const canEdit = computed(() => userPermissions.value.includes("write"));
  const canCreate = computed(() => userPermissions.value.includes("create"));
  const isManager = computed(() => userPermissions.value.includes("manage"));

  const permissionLevel = computed(() => {
    if (userPermissions.value.includes("manage")) return "admin";
    if (userPermissions.value.includes("create")) return "editor";
    if (userPermissions.value.includes("read")) return "viewer";
    return "none";
  });

  function checkPermission(action) {
    return userPermissions.value.includes(action);
  }

  function requestPermission(action) {
    if (!userPermissions.value.includes(action)) {
      userPermissions.value.push(action);
    }
  }

  // NOTE: canDelete and hasRole are NOT defined in this composable

  return {
    userPermissions,
    roleMap,
    canEdit,
    canCreate,
    isManager,
    permissionLevel,
    checkPermission,
    requestPermission,
  };
}
```

**After (tool output — broken):**

```js
// Transformation confidence: LOW (1 warnings — see migration report)
// ⚠ MIGRATION: this.$router is not available in composables
import { ref, computed } from 'vue'

export function usePermission() {
  const userPermissions = ref([])
  const roleMap = ref({
    admin: ['read', 'write', 'create', 'delete', 'manage'],
    editor: ['read', 'write', 'create'],
    viewer: ['read']
  })

  const canEdit = computed(() => userPermissions.value.includes('write'))
  const canCreate = computed(() => userPermissions.value.includes('create'))
  const isManager = computed(() => userPermissions.value.includes('manage'))

  const permissionLevel = computed(() => {
    if (userPermissions.value.includes('manage')) return 'admin'
    if (userPermissions.value.includes('create')) return 'editor'
    if (userPermissions.value.includes('read')) return 'viewer'
    return 'none'
  })

  function checkPermission(action) {
    return userPermissions.value.includes(action)
  }

  function requestPermission(action) {
    if (!userPermissions.value.includes(action)) {
      userPermissions.value.push(action)
    }
  }

  // NOTE: canDelete and hasRole are NOT defined in this composable

  const canDelete = computed(() => checkPermission('delete'))
  return {
    userPermissions,
    roleMap,
    canEdit,
    canCreate,
    isManager,
    permissionLevel,
    checkPermission,
    requestPermission,
      canDelete,

}
```

**Git diff:**

```diff
@@ -41,6 +44,7 @@ export function usePermission() {
     isManager,
     permissionLevel,
     checkPermission,
-    requestPermission
-  }
+    requestPermission,
+      canDelete,
+
 }
```

**Expected correct output:**

```js
  const canDelete = computed(() => checkPermission('delete'))
  return {
    userPermissions,
    roleMap,
    canEdit,
    canCreate,
    isManager,
    permissionLevel,
    checkPermission,
    requestPermission,
    canDelete,
  }
}
```

---

### 1b. useTable.js

**Before (valid — return block):**

```js
  // NOTE: sortDirection and collapseAll are intentionally NOT returned
  return {
    rows,
    columns,
    sortField,
    expandedRows,
    sortedRows,
    visibleColumns,
    hasExpandedRows,
    sortBy,
    toggleRow,
    getColumnClass
  }
}
```

**After (tool output — broken):**

```js
    sortBy,
    toggleRow,
    getColumnClass,
      sortDirection,

}
```

**Git diff:**

```diff
@@ -66,6 +70,7 @@ export function useTable() {
     hasExpandedRows,
     sortBy,
     toggleRow,
-    getColumnClass
-  }
+    getColumnClass,
+      sortDirection,
+
 }
```

**Expected correct output:**

```js
  return {
    rows,
    columns,
    sortField,
    expandedRows,
    sortedRows,
    visibleColumns,
    hasExpandedRows,
    sortBy,
    toggleRow,
    getColumnClass,
    sortDirection,
  }
}
```

---

### 1c. usePagination.js

**Before (valid — return block):**

```js
  // NOTE: hasPrevPage and prevPage are NOT defined in this composable

  return {
    currentPage,
    pageSize,
    totalItems,
    totalPages,
    hasNextPage,
    paginatedOffset,
    nextPage,
    goToPage,
    changePageSize
  }
}
```

**After (tool output — broken):**

The tool correctly generated the missing members:

```js
const hasPrevPage = computed(() => currentPage.value > 1);
function prevPage() {
  if (hasPrevPage.value) {
    currentPage.value--;
  }
}
```

But the return block is broken:

```js
return {
  currentPage,
  pageSize,
  totalItems,
  totalPages,
  hasNextPage,
  paginatedOffset,
  nextPage,
  goToPage,
  changePageSize,
  hasPrevPage,
  prevPage,
};
```

**Git diff:**

```diff
@@ -39,6 +45,8 @@ export function usePagination() {
     paginatedOffset,
     nextPage,
     goToPage,
-    changePageSize
-  }
+    changePageSize,
+      hasPrevPage,
+    prevPage,
+
 }
```

**Expected correct output:**

```js
  return {
    currentPage,
    pageSize,
    totalItems,
    totalPages,
    hasNextPage,
    paginatedOffset,
    nextPage,
    goToPage,
    changePageSize,
    hasPrevPage,
    prevPage,
  }
}
```

---

### 1d. useForm.js

**Before (valid — return block):**

```js
  // NOTE: setFieldError and dirtyFields are NOT defined in this composable

  return {
    formData,
    originalData,
    isDirty,
    isSubmitting,
    formErrors,
    hasChanges,
    isFormValid,
    initForm,
    resetForm,
    submitForm
  }
}
```

**After (tool output — broken):**

The tool correctly generated a `dirtyFields` computed and `onBeforeMount` lifecycle hook:

```js
const dirtyFields = computed(() => {
  return Object.keys(formData.value).filter((key) => {
    return (
      JSON.stringify(formData.value[key]) !==
      JSON.stringify(originalData.value[key])
    );
  });
});
onBeforeMount(() => {
  initForm(formData.value);
});
```

But the return block is broken:

```js
return {
  formData,
  originalData,
  isDirty,
  isSubmitting,
  formErrors,
  hasChanges,
  isFormValid,
  initForm,
  resetForm,
  submitForm,
  dirtyFields,
};
```

**Git diff:**

```diff
@@ -50,6 +61,7 @@ export function useForm() {
     isFormValid,
     initForm,
     resetForm,
-    submitForm
-  }
+    submitForm,
+      dirtyFields,
+
 }
```

**Expected correct output:**

```js
  return {
    formData,
    originalData,
    isDirty,
    isSubmitting,
    formErrors,
    hasChanges,
    isFormValid,
    initForm,
    resetForm,
    submitForm,
    dirtyFields,
  }
}
```

---

### 1e. useSelection.js

**Before (valid — return block):**

```js
  // NOTE: deselectAll is intentionally NOT returned
  return {
    selectedItems,
    selectionMode,
    lastSelected,
    hasSelection,
    selectionCount,
    allSelected,
    select,
    deselect,
    toggleSelection,
    selectAll,
    isSelected
  }
}
```

**After (tool output — broken):**

```js
    selectAll,
    isSelected,
      deselectAll,

}
```

**Git diff:**

```diff
@@ -61,6 +63,7 @@ export function useSelection() {
     deselect,
     toggleSelection,
     selectAll,
-    isSelected
-  }
+    isSelected,
+      deselectAll,
+
 }
```

**Expected correct output:**

```js
  return {
    selectedItems,
    selectionMode,
    lastSelected,
    hasSelection,
    selectionCount,
    allSelected,
    select,
    deselect,
    toggleSelection,
    selectAll,
    isSelected,
    deselectAll,
  }
}
```

---

## Bug 2: Lifecycle Hooks Injected Inside `computed()` Body

**Affected file:** `src/composables/useChart.js`

**Result:** `onMounted` and `onBeforeUnmount` are called inside a `computed()` callback. Vue will throw _"onMounted is called when there is no active component instance"_ or silently fail. The hooks would also re-execute on every computed re-evaluation instead of running once.

### Source mixin (`chartMixin.js`):

```js
export default {
  data() {
    return {
      chartData: null,
      chartOptions: {},
      chartType: "bar",
      isChartReady: false,
    };
  },

  computed: {
    formattedChartData() {
      if (!this.chartData || this.chartData.length === 0) {
        return { labels: [], datasets: [] };
      }
      return {
        labels: this.chartData.map((d) => d.label),
        datasets: [
          {
            data: this.chartData.map((d) => d.value),
            backgroundColor: this.chartColors,
          },
        ],
      };
    },

    chartColors() {
      return [
        "#4CAF50",
        "#2196F3",
        "#FF9800",
        "#F44336",
        "#9C27B0",
        "#00BCD4",
        "#FFEB3B",
        "#795548",
      ];
    },

    hasData() {
      return !!this.chartData && this.chartData.length > 0;
    },
  },

  methods: {
    prepareChartData(raw) {
      this.chartData = raw.map((item) => ({
        label: item.name || item.label,
        value: item.value || item.count || 0,
      }));
    },

    updateChart() {
      this.isChartReady = true;
      this.$nextTick(() => {
        // Chart DOM updated
      });
    },

    resizeChart() {
      const width = this.$el.offsetWidth;
      if (this.$refs.chartCanvas) {
        this.$refs.chartCanvas.width = width;
        this.$refs.chartCanvas.height = width * 0.6;
      }
    },

    exportChart(format) {
      const canvas = this.$refs.chartCanvas;
      if (!canvas) return null;
      if (format === "png") {
        return canvas.toDataURL("image/png");
      } else if (format === "jpg") {
        return canvas.toDataURL("image/jpeg");
      }
      return null;
    },
  },

  mounted() {
    this.resizeChart();
  },

  beforeUnmount() {
    this.isChartReady = false;
  },

  watch: {
    chartData: {
      deep: true,
      handler() {
        this.updateChart();
      },
    },
  },
};
```

### Before (valid composable):

```js
import { ref, computed } from "vue";

export function useChart() {
  const chartData = ref(null);
  const chartOptions = ref({});
  const chartType = ref("bar");
  const isChartReady = ref(false);

  const formattedChartData = computed(() => {
    if (!chartData.value) return null;
    return {
      labels: chartData.value.labels || [],
      datasets: chartData.value.datasets || [],
    };
  });

  const chartColors = computed(() => {
    return (
      chartOptions.value.colors || [
        "#4CAF50",
        "#2196F3",
        "#FF9800",
        "#F44336",
        "#9C27B0",
      ]
    );
  });

  const hasData = computed(() => chartData.value !== null);

  function prepareChartData(raw) {
    if (!raw) return;
    chartData.value = {
      labels: raw.labels || [],
      datasets: (raw.datasets || []).map((ds, i) => ({
        ...ds,
        backgroundColor: chartColors.value[i % chartColors.value.length],
      })),
    };
    isChartReady.value = true;
  }

  function updateChart() {
    if (chartData.value) {
      isChartReady.value = false;
      isChartReady.value = true;
    }
  }

  function resizeChart() {
    updateChart();
  }

  function exportChart(format) {
    if (!isChartReady.value) return null;
    return {
      type: chartType.value,
      format: format || "png",
      data: formattedChartData.value,
    };
  }

  return {
    chartData,
    chartOptions,
    chartType,
    isChartReady,
    formattedChartData,
    chartColors,
    hasData,
    prepareChartData,
    updateChart,
    resizeChart,
    exportChart,
  };
}
```

### After (tool output — broken):

```js
// Transformation confidence: MEDIUM (2 warnings — see migration report)
// ⚠ MIGRATION: this.$refs is not available in composables
// ⚠ MIGRATION: this.$el has no composable equivalent
import { ref, computed, onMounted, onBeforeUnmount } from "vue";

export function useChart() {
  const chartData = ref(null);
  const chartOptions = ref({});
  const chartType = ref("bar");
  const isChartReady = ref(false);

  const formattedChartData = computed(() => {
    if (!chartData.value) return null;
    onMounted(() => {
      // ← WRONG: inside computed() callback
      resizeChart();
    });
    onBeforeUnmount(() => {
      // ← WRONG: inside computed() callback
      isChartReady.value = false;
    });
    return {
      labels: chartData.value.labels || [],
      datasets: chartData.value.datasets || [],
    };
  });

  // ... rest unchanged ...
}
```

**Git diff:**

```diff
@@ -8,6 +11,12 @@ export function useChart() {

   const formattedChartData = computed(() => {
     if (!chartData.value) return null
+  onMounted(() => {
+    resizeChart()
+  })
+  onBeforeUnmount(() => {
+    isChartReady.value = false
+  })
     return {
       labels: chartData.value.labels || [],
       datasets: chartData.value.datasets || []
```

### Expected correct output (hooks at top-level function scope, before return):

```js
import { ref, computed, onMounted, onBeforeUnmount } from "vue";

export function useChart() {
  const chartData = ref(null);
  const chartOptions = ref({});
  const chartType = ref("bar");
  const isChartReady = ref(false);

  const formattedChartData = computed(() => {
    if (!chartData.value) return null;
    return {
      labels: chartData.value.labels || [],
      datasets: chartData.value.datasets || [],
    };
  });

  const chartColors = computed(() => {
    return (
      chartOptions.value.colors || [
        "#4CAF50",
        "#2196F3",
        "#FF9800",
        "#F44336",
        "#9C27B0",
      ]
    );
  });

  const hasData = computed(() => chartData.value !== null);

  function prepareChartData(raw) {
    if (!raw) return;
    chartData.value = {
      labels: raw.labels || [],
      datasets: (raw.datasets || []).map((ds, i) => ({
        ...ds,
        backgroundColor: chartColors.value[i % chartColors.value.length],
      })),
    };
    isChartReady.value = true;
  }

  function updateChart() {
    if (chartData.value) {
      isChartReady.value = false;
      isChartReady.value = true;
    }
  }

  function resizeChart() {
    updateChart();
  }

  function exportChart(format) {
    if (!isChartReady.value) return null;
    return {
      type: chartType.value,
      format: format || "png",
      data: formattedChartData.value,
    };
  }

  onMounted(() => {
    resizeChart();
  });

  onBeforeUnmount(() => {
    isChartReady.value = false;
  });

  return {
    chartData,
    chartOptions,
    chartType,
    isChartReady,
    formattedChartData,
    chartColors,
    hasData,
    prepareChartData,
    updateChart,
    resizeChart,
    exportChart,
  };
}
```

---

## Bug 3: `_handleEscapeKey` Referenced But Never Defined

**Affected file:** `src/composables/useModal.js`

**Result:** `ReferenceError: _handleEscapeKey is not defined` — the patcher added `onMounted`/`onBeforeUnmount` lifecycle hooks that reference `_handleEscapeKey`, but this function does not exist anywhere in the composable. The mixin defines it as a method, but the generator never converted it to a composable function.

### Source mixin (`modalMixin.js`):

```js
export default {
  data() {
    return {
      isOpen: false,
      modalData: null,
      modalOptions: {},
    };
  },

  computed: {
    modalTitle() {
      return this.modalOptions.title || "Modal";
    },
    hasData() {
      return !!this.modalData;
    },
  },

  methods: {
    openModal(data, options) {
      this.modalData = data;
      this.modalOptions = options || {};
      this.isOpen = true;
      this.$nextTick(() => {
        this.$refs.modalOverlay?.focus();
      });
    },

    closeModal() {
      this.isOpen = false;
      this.modalData = null;
      this.modalOptions = {};
      this.$emit("modal-closed");
    },

    confirmModal() {
      this.$emit("modal-confirmed", this.modalData);
      this.closeModal();
    },

    _handleEscapeKey(event) {
      if (event.key === "Escape" && this.isOpen) {
        this.closeModal();
      }
    },
  },

  mounted() {
    document.addEventListener("keydown", this._handleEscapeKey);
  },

  beforeUnmount() {
    document.removeEventListener("keydown", this._handleEscapeKey);
  },
};
```

### Before (composable — `_handleEscapeKey` already missing from generator output):

```js
import { ref, computed } from "vue";

export function useModal() {
  const isOpen = ref(false);
  const modalData = ref(null);
  const modalOptions = ref({});

  const modalTitle = computed(() => modalOptions.value.title || "Modal");
  const hasData = computed(() => modalData.value !== null);

  function openModal(data, options) {
    modalData.value = data;
    modalOptions.value = options || {};
    isOpen.value = true;
  }

  function closeModal() {
    isOpen.value = false;
    modalData.value = null;
    modalOptions.value = {};
  }

  function confirmModal() {
    const callback = modalOptions.value.onConfirm;
    if (typeof callback === "function") {
      callback(modalData.value);
    }
    closeModal();
  }

  return {
    isOpen,
    modalData,
    modalOptions,
    modalTitle,
    hasData,
    openModal,
    closeModal,
    confirmModal,
  };
}
```

### After (tool output — broken):

```js
// Transformation confidence: MEDIUM (2 warnings — see migration report)
// ⚠ MIGRATION: this.$emit is not available in composables
// ⚠ MIGRATION: this.$refs is not available in composables
import { ref, computed, onMounted, onBeforeUnmount } from "vue";

export function useModal() {
  const isOpen = ref(false);
  const modalData = ref(null);
  const modalOptions = ref({});

  const modalTitle = computed(() => modalOptions.value.title || "Modal");
  const hasData = computed(() => modalData.value !== null);

  function openModal(data, options) {
    modalData.value = data;
    modalOptions.value = options || {};
    isOpen.value = true;
  }

  function closeModal() {
    isOpen.value = false;
    modalData.value = null;
    modalOptions.value = {};
  }

  function confirmModal() {
    const callback = modalOptions.value.onConfirm;
    if (typeof callback === "function") {
      callback(modalData.value);
    }
    closeModal();
  }

  onMounted(() => {
    document.addEventListener("keydown", _handleEscapeKey); // ← ReferenceError
  });
  onBeforeUnmount(() => {
    document.removeEventListener("keydown", _handleEscapeKey); // ← ReferenceError
  });

  return {
    isOpen,
    modalData,
    modalOptions,
    modalTitle,
    hasData,
    openModal,
    closeModal,
    confirmModal,
  };
}
```

**Git diff:**

```diff
@@ -28,6 +31,12 @@ export function useModal() {
     closeModal()
   }

+  onMounted(() => {
+    document.addEventListener('keydown', _handleEscapeKey)
+  })
+  onBeforeUnmount(() => {
+    document.removeEventListener('keydown', _handleEscapeKey)
+  })
   return {
     isOpen,
     modalData,
```

### Expected correct output (function defined, then used in hooks):

```js
import { ref, computed, onMounted, onBeforeUnmount } from "vue";

export function useModal() {
  const isOpen = ref(false);
  const modalData = ref(null);
  const modalOptions = ref({});

  const modalTitle = computed(() => modalOptions.value.title || "Modal");
  const hasData = computed(() => modalData.value !== null);

  function openModal(data, options) {
    modalData.value = data;
    modalOptions.value = options || {};
    isOpen.value = true;
  }

  function closeModal() {
    isOpen.value = false;
    modalData.value = null;
    modalOptions.value = {};
  }

  function confirmModal() {
    const callback = modalOptions.value.onConfirm;
    if (typeof callback === "function") {
      callback(modalData.value);
    }
    closeModal();
  }

  function _handleEscapeKey(event) {
    if (event.key === "Escape" && isOpen.value) {
      closeModal();
    }
  }

  onMounted(() => {
    document.addEventListener("keydown", _handleEscapeKey);
  });

  onBeforeUnmount(() => {
    document.removeEventListener("keydown", _handleEscapeKey);
  });

  return {
    isOpen,
    modalData,
    modalOptions,
    modalTitle,
    hasData,
    openModal,
    closeModal,
    confirmModal,
  };
}
```

---

## Bug 4: Template Members Missing from `setup()` Destructuring

**Affected files:** `BaseModal.vue`, `PaginationBar.vue`, `StatsOverview.vue`

**Result:** Members used in the component's template and script are not included in the `setup()` destructuring or return. Since the mixin was removed, these members become `undefined` at runtime — breaking conditional rendering, computed properties, and watchers.

---

### 4a. BaseModal.vue — `isOpen` missing

**Template uses `isOpen`:**

```html
<div v-if="isOpen" ref="modalOverlay" ...></div>
```

**Component script also references `isOpen` in:**

- `watch: { isOpen(newVal) { ... } }`
- `mounted() { if (this.isOpen) { ... } }`

**Before (mixin provides `isOpen`):**

```js
import modalMixin from "@/mixins/modalMixin";
import keyboardShortcutMixin from "@/mixins/keyboardShortcutMixin";

export default {
  name: "BaseModal",
  mixins: [modalMixin, keyboardShortcutMixin],
  emits: ["modal-closed", "modal-confirmed", "shortcut-triggered"],

  watch: {
    isOpen(newVal) {
      if (newVal) {
        this.$nextTick(() => {
          if (this.$refs.modalOverlay) {
            this.$refs.modalOverlay.focus();
          }
        });
      }
    },
  },

  mounted() {
    this.registerShortcut("Escape", () => {
      if (this.isOpen) {
        this.closeModal();
      }
    });
  },
};
```

**After (tool output — `isOpen` missing from destructuring and return):**

```js
import { useKeyboardShortcut } from "@/composables/useKeyboardShortcut";
import { useModal } from "@/composables/useModal";

export default {
  setup() {
    const {
      modalData,
      modalTitle,
      closeModal,
      confirmModal,
      _handleEscapeKey,
    } = useModal();
    const { registerShortcut, shortcuts, handleKeyDown } =
      useKeyboardShortcut();

    return {
      modalData,
      modalTitle,
      closeModal,
      confirmModal,
      _handleEscapeKey,
      registerShortcut,
      shortcuts,
      handleKeyDown,
    };
  },
  name: "BaseModal",
  emits: ["modal-closed", "modal-confirmed", "shortcut-triggered"],
  // ...
};
```

`isOpen` is used in the template (`v-if="isOpen"`), in a watcher, and in `mounted()`, but is not destructured from `useModal()` and not returned from `setup()`.

Additionally, `_handleEscapeKey` IS included in the destructuring but does not exist in the composable (see Bug 3).

**Git diff:**

```diff
-import modalMixin from '@/mixins/modalMixin'
-import keyboardShortcutMixin from '@/mixins/keyboardShortcutMixin'
+import { useKeyboardShortcut } from '@/composables/useKeyboardShortcut'
+import { useModal } from '@/composables/useModal'

 export default {
-  name: 'BaseModal',
+  setup() {
+    const { modalData, modalTitle, closeModal, confirmModal, _handleEscapeKey } = useModal()
+    const { registerShortcut, shortcuts, handleKeyDown } = useKeyboardShortcut()

-  mixins: [modalMixin, keyboardShortcutMixin],
+    return { modalData, modalTitle, closeModal, confirmModal, _handleEscapeKey, registerShortcut, shortcuts, handleKeyDown }
+  },
+  name: 'BaseModal',
```

**Expected correct `setup()`:**

```js
setup() {
  const { isOpen, modalData, modalTitle, hasData, openModal, closeModal, confirmModal } = useModal()
  const { registerShortcut, shortcuts, handleKeyDown } = useKeyboardShortcut()

  return { isOpen, modalData, modalTitle, hasData, openModal, closeModal, confirmModal, registerShortcut, shortcuts, handleKeyDown }
},
```

---

### 4b. PaginationBar.vue — `currentPage` missing

**Template uses `currentPage`:**

```html
<!-- :class binding -->
page === currentPage ? 'bg-blue-600 text-white border-blue-600 z-10' : 'bg-white
text-gray-700 border-gray-300 hover:bg-gray-50'

<!-- v-if -->
v-if="totalPages > 7 && currentPage < totalPages - 2"
```

**Component script also references `currentPage` in:**

- `computed: { visiblePages() { ... this.currentPage ... } }`
- `watch: { currentPage(newPage) { this.$emit('page-changed', ...) } }`

**Before (mixin provides `currentPage`):**

```js
import paginationMixin from "@/mixins/paginationMixin";

export default {
  name: "PaginationBar",
  mixins: [paginationMixin],
  props: {
    total: { type: Number, default: 0 },
  },
  emits: ["page-changed"],
  // ...
};
```

**After (tool output — `currentPage` missing from destructuring and return):**

```js
import { usePagination } from "@/composables/usePagination";

export default {
  setup() {
    const {
      pageSize,
      totalItems,
      totalPages,
      hasPrevPage,
      hasNextPage,
      paginatedOffset,
      nextPage,
      prevPage,
      goToPage,
      changePageSize,
    } = usePagination();

    return {
      pageSize,
      totalItems,
      totalPages,
      hasPrevPage,
      hasNextPage,
      paginatedOffset,
      nextPage,
      prevPage,
      goToPage,
      changePageSize,
    };
  },
  name: "PaginationBar",
  // ...
};
```

`currentPage` is used in template bindings and in `computed`/`watch` blocks, but is not destructured or returned.

**Git diff:**

```diff
-import paginationMixin from '@/mixins/paginationMixin'
+import { usePagination } from '@/composables/usePagination'

 export default {
-  name: 'PaginationBar',
-
-  mixins: [paginationMixin],
+  setup() {
+    const { pageSize, totalItems, totalPages, hasPrevPage, hasNextPage, paginatedOffset, nextPage, prevPage, goToPage, changePageSize } = usePagination()
+
+    return { pageSize, totalItems, totalPages, hasPrevPage, hasNextPage, paginatedOffset, nextPage, prevPage, goToPage, changePageSize }
+  },
+  name: 'PaginationBar',
```

**Expected correct `setup()`:**

```js
setup() {
  const { currentPage, pageSize, totalItems, totalPages, hasPrevPage, hasNextPage, paginatedOffset, nextPage, prevPage, goToPage, changePageSize } = usePagination()

  return { currentPage, pageSize, totalItems, totalPages, hasPrevPage, hasNextPage, paginatedOffset, nextPage, prevPage, goToPage, changePageSize }
},
```

---

### 4c. StatsOverview.vue — `hasError`, `error`, `canRetry`, `retry` missing

**Template uses these members:**

```html
<div v-else-if="hasError" ...>
  <p class="text-red-600 text-sm">{{ error }}</p>
  <button v-if="canRetry" ...>@click="retry(loadStats)"</button>
</div>
```

**Source mixin (`loadingMixin.js`) provides all of them:**

```js
export default {
  data() {
    return {
      isLoading: false,
      loadingMessage: "",
      error: null,
      retryCount: 0,
    };
  },
  computed: {
    hasError() {
      return !!this.error;
    },
    canRetry() {
      return this.retryCount < 3;
    },
  },
  methods: {
    startLoading(msg) {
      this.isLoading = true;
      this.loadingMessage = msg || "Loading...";
      this.error = null;
    },
    stopLoading() {
      this.isLoading = false;
      this.loadingMessage = "";
    },
    setError(err) {
      this.error = err;
      this.isLoading = false;
      this.$forceUpdate();
    },
    retry(fn) {
      this.retryCount++;
      fn();
    },
  },
};
```

**The composable (`useLoading.js`) correctly defines and returns ALL of these:**

```js
export function useLoading() {
  const isLoading = ref(false);
  const loadingMessage = ref("");
  const error = ref(null);
  const retryCount = ref(0);

  const hasError = computed(() => error.value !== null);
  const canRetry = computed(() => retryCount.value < 3);

  function startLoading(msg) {
    isLoading.value = true;
    loadingMessage.value = msg || "";
    error.value = null;
  }

  function stopLoading() {
    isLoading.value = false;
    loadingMessage.value = "";
  }

  function setError(err) {
    error.value = err;
    isLoading.value = false;
  }

  async function retry(fn) {
    if (!canRetry.value) return;
    retryCount.value++;
    try {
      startLoading("Retrying...");
      await fn();
      stopLoading();
    } catch (err) {
      setError(err);
    }
  }

  return {
    isLoading,
    loadingMessage,
    error,
    retryCount,
    hasError,
    canRetry,
    startLoading,
    stopLoading,
    setError,
    retry,
  };
}
```

**Before (mixin provides all members):**

```js
import loadingMixin from "@/mixins/loadingMixin";
import chartMixin from "@/mixins/chartMixin";
import { useProjectsStore } from "@/stores/projects";
import { useTasksStore } from "@/stores/tasks";
import { useUsersStore } from "@/stores/users";

export default {
  name: "StatsOverview",
  mixins: [loadingMixin, chartMixin],
  // ...
};
```

**After (tool output — 4 members missing from destructuring and return):**

```js
import { useChart } from "@/composables/useChart";
import { useLoading } from "@/composables/useLoading";
import { useProjectsStore } from "@/stores/projects";
import { useTasksStore } from "@/stores/tasks";
import { useUsersStore } from "@/stores/users";

export default {
  name: "StatsOverview",
  setup() {
    const { isLoading, startLoading, stopLoading, setError } = useLoading();
    const { prepareChartData, resizeChart, isChartReady } = useChart();

    return {
      isLoading,
      startLoading,
      stopLoading,
      setError,
      prepareChartData,
      resizeChart,
      isChartReady,
    };
  },
  // ...
};
```

`hasError`, `error`, `canRetry`, and `retry` are all used in the template but none are destructured from `useLoading()` or returned from `setup()`. The composable returns them — the injector just didn't include them.

**Git diff:**

```diff
-import loadingMixin from '@/mixins/loadingMixin'
-import chartMixin from '@/mixins/chartMixin'
+import { useChart } from '@/composables/useChart'
+import { useLoading } from '@/composables/useLoading'
 import { useProjectsStore } from '@/stores/projects'
 import { useTasksStore } from '@/stores/tasks'
 import { useUsersStore } from '@/stores/users'

 export default {
   name: 'StatsOverview',
-
-  mixins: [loadingMixin, chartMixin],
+  setup() {
+    const { isLoading, startLoading, stopLoading, setError } = useLoading()
+    const { prepareChartData, resizeChart, isChartReady } = useChart()
+
+    return { isLoading, startLoading, stopLoading, setError, prepareChartData, resizeChart, isChartReady }
+  },
```

**Expected correct `setup()`:**

```js
setup() {
  const { isLoading, startLoading, stopLoading, setError, hasError, error, canRetry, retry } = useLoading()
  const { prepareChartData, resizeChart, isChartReady } = useChart()

  return { isLoading, startLoading, stopLoading, setError, hasError, error, canRetry, retry, prepareChartData, resizeChart, isChartReady }
},
```
