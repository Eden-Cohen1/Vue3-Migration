// Fixture for manual verification of catch-all plugin property warnings
export default {
  data() {
    return {
      message: '',             // normal data member
    }
  },
  methods: {
    // Task: unknown $toast — should produce catch-all warning
    showSuccess() {
      this.$toast.success('Done!')
    },
    // Task: unknown $toast (duplicate) — should NOT produce a second warning
    showError() {
      this.$toast.error('Failed')
    },
    // Task: unknown $confirm — should produce a separate catch-all warning
    removeItem() {
      this.$confirm('Are you sure?').then(() => {
        this.message = 'Removed'
      })
    },
    // Task: unknown $modalMessageBx — long name, should produce catch-all warning
    openDialog() {
      this.$modalMessageBx.show({ title: 'Hello' })
    },
    // Task: known $router — should produce known-pattern warning, NOT a catch-all duplicate
    navigate() {
      this.$router.push('/home')
    },
    // Task: known $emit — should produce known-pattern warning, NOT a catch-all duplicate
    notifyParent() {
      this.$emit('done', this.message)
    },
    // Task: auto-rewritten $nextTick — should produce NO warning at all
    refresh() {
      this.$nextTick(() => {
        console.log('refreshed')
      })
    },
    // Task: auto-rewritten $set — should produce NO warning at all
    setField() {
      this.$set(this, 'message', 'updated')
    },
  }
}
