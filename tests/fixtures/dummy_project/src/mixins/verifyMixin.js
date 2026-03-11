/**
 * Manual verification mixin — tests ALL 9 implemented tasks.
 *
 * Task 1:  VerifyEmpty.vue imports this but uses zero members → auto-remove
 * Task 2:  External dep (this.externalItems) → 3 alternatives in report
 * Task 3:  orphanMixin.js is never imported → flagged for deletion
 * Task 5:  Unused members (neverUsedFlag, neverUsedHelper) → info section
 * Task 6:  Member usage accuracy check
 * Task 7:  const self = this → inline comments on ALL self.x lines
 * Task 8:  All warnings should have line references in the report
 * Task 9:  VerifyFull.vue has data/setup collision on 'status'
 */
export default {
  // Task 7: self = this alias — should produce inline warnings on EVERY self.x line
  // Task 8: this-alias warning should link to this line in the report
  props: ['config'],  // Task 8: mixin-option:props warning should link here

  data() {
    return {
      status: 'idle',        // Task 9: collides with component data
      query: '',
      results: [],
      neverUsedFlag: false,  // Task 5+6: should appear as unused member
    }
  },

  computed: {
    hasResults() {
      return this.results.length > 0
    },
    neverUsedComputed() {  // Task 5+6: should appear as unused member
      return this.neverUsedFlag
    }
  },

  methods: {
    // Task 2: this.externalItems is an external dep — report should show 3 alternatives
    search() {
      const self = this    // Task 7: declaration line — should get ⚠️ inline comment
      self.status = 'searching'  // Task 7: usage line — should ALSO get ⚠️ inline comment
      self.results = this.externalItems.filter(  // Task 2: external dep + Task 7: self usage
        item => item.name.includes(self.query)   // Task 7: and another
      )
      self.status = 'done'  // Task 7: and another
      this.$emit('searched', self.results)  // Task 8: this.$emit should have line link
    },

    clearSearch() {
      this.query = ''
      this.results = []
      this.$router.push('/home')  // Task 8: this.$router should have line link
    },

    neverUsedHelper() {  // Task 5+6: should appear as unused member
      return 'not used anywhere'
    }
  },

  mounted() {
    console.log('verifyMixin mounted')
  }
}
