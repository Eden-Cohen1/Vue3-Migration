// Scenario 9: non-reactive `this._timer` private property. Component uses
// `setValue` + `text`. The generator should hoist `_timer` to a local `let`,
// and scoping must not interfere. Returned: {text, setValue}.
export default {
  data() {
    return {
      text: '',
    }
  },
  methods: {
    setValue(v) {
      clearTimeout(this._timer)
      this._timer = setTimeout(() => {
        this.text = v
      }, 200)
    },
  },
}
