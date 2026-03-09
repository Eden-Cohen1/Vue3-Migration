// Kitchen sink mixin that exercises ALL 8 features at once:
// A1: Members in comments only
// A2: this.$t, this.$tc, this.$n
// B1: this.$refs, this.$emit (mixin-intrinsic warnings)
// B2: (use with pre-existing composable to test suppression)
// C1: External deps (this.entityId, this._debounceTimer)
// C2: Dotted watch key ('user.preferences')
// C3: All section types for ordering
// D1: Unused members
export default {
  data() {
    return {
      title: '',
      description: '',
      isEditing: false,
      validationErrors: [],
      // D1: never used by the component
      internalFlag: false
    }
  },
  computed: {
    displayTitle() {
      return this.$t('entity.title', { name: this.title })
    },
    errorCount() {
      return this.validationErrors.length
    },
    isValid() {
      return this.validationErrors.length === 0
    },
    // D1: never used
    unusedStatus() {
      return this.isEditing ? 'editing' : 'viewing'
    }
  },
  methods: {
    save() {
      if (!this.isValid) return
      // B1: mixin-intrinsic — this.$emit not available in composables
      this.$emit('save', { title: this.title, description: this.description })
      // C1: this.entityId is an external dep (comes from component)
      console.log('Saving entity:', this.entityId)
    },
    cancel() {
      this.isEditing = false
      this.$emit('cancel')
    },
    validate() {
      this.validationErrors = []
      if (!this.title.trim()) {
        this.validationErrors.push(this.$t('validation.title_required'))
      }
      if (this.description.length > 500) {
        const msg = this.$tc('validation.char_limit', 500)
        this.validationErrors.push(msg)
      }
    },
    formatAmount(val) {
      return this.$n(val, 'currency')
    },
    focusTitle() {
      // B1: this.$refs — mixin-intrinsic
      this.$refs.titleInput.focus()
    },
    // D1: never used
    unusedHelper() {
      return 'not called anywhere'
    }
  },
  watch: {
    title(newVal) {
      // C1: this._debounceTimer is underscore external dep
      if (this._debounceTimer) clearTimeout(this._debounceTimer)
      this._debounceTimer = setTimeout(() => {
        this.validate()
      }, 250)
    },
    // C2: dotted watch key
    'user.preferences'(newPrefs) {
      this.isEditing = false
    }
  }
}
