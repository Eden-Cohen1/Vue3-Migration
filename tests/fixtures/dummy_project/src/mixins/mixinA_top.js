// Top-level mixin — has nested mixin (mid), which itself nests (leaf)
// Tests: chain resolution (A → B → C), multiple transitive levels
import mixinB_mid from './mixinB_mid'
import ghostMixin from './ghostMixin'    // Scenario: missing file — unresolvable

export default {
  mixins: [mixinB_mid, ghostMixin],       // Scenario: mixed resolved + unresolved
  data() {
    return {
      topValue: 'hello',
    }
  },
  methods: {
    topMethod() {
      this.midFlag = false
    },
  },
}
