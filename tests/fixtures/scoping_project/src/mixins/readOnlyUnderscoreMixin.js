// Scenario 17: `this._injected` is READ but never assigned in the mixin — it
// comes from the component (an external dependency). Unlike `debounceMixin`'s
// assigned `_timer`, it must NOT be localized to a null local (that would be a
// silent bug); it stays as `this._injected` and is flagged for the developer.
export default {
  methods: {
    render() {
      return this._injected
    },
  },
}
