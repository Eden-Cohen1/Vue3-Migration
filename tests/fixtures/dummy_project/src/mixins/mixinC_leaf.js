// Leaf mixin — no nested mixins, just members
// Used by: chain test (A → B → C)
export default {
  data() {
    return {
      leafValue: 0,        // Scenario: chain — should appear as transitive member
    }
  },
  methods: {
    leafMethod() {         // Scenario: chain — should appear as transitive member
      console.log('leaf')
    },
  },
}
