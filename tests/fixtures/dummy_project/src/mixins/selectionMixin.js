// Edge case: full mixin with all member types (data, computed, methods)
// Scenario: fully covered by useSelection composable -> READY
export default {
  data() {
    return {
      selectedItems: [],
      selectionMode: 'single',
    }
  },
  computed: {
    hasSelection() {
      return this.selectedItems.length > 0
    },
    selectionCount() {
      return this.selectedItems.length
    },
  },
  methods: {
    selectItem(item) {
      this.selectedItems.push(item)
    },
    clearSelection() {
      this.selectedItems = []
    },
    toggleItem(item) {
      const idx = this.selectedItems.indexOf(item)
      if (idx === -1) this.selectedItems.push(item)
      else this.selectedItems.splice(idx, 1)
    },
  },
}
