// Mid-chain mixin — has nested mixin (leaf) + own members
// Used by: chain test (A → B → C)
import mixinC_leaf from './mixinC_leaf'

export default {
  mixins: [mixinC_leaf],      // Scenario: chain — triggers transitive resolution
  data() {
    return {
      midFlag: true,           // Scenario: chain — direct member of B
    }
  },
  computed: {
    midComputed() {            // Scenario: chain — direct member of B
      return this.midFlag ? 'yes' : 'no'
    },
  },
}
