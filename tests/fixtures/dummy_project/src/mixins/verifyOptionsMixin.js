// Manual verification fixture: this.$options access patterns
export default {
  methods: {
    getMixinMethod() {
      return this.$options.mixins[0].methods.doSomething()
    },
    getComponentName() {
      return this.$options.name
    },
  },
}
