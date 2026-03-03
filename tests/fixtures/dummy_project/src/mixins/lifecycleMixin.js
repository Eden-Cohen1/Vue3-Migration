export default {
  data() {
    return {
      hookLog: [],
      mountCount: 0,
      isActive: false
    }
  },
  methods: {
    logHook(name) {
      this.hookLog.push(name)
    }
  },
  beforeCreate() {
    console.log('beforeCreate - no this access to data yet')
  },
  created() {
    this.logHook('created')
  },
  beforeMount() {
    this.logHook('beforeMount')
  },
  mounted() {
    this.mountCount++
    this.logHook('mounted')
  },
  beforeUpdate() {
    this.logHook('beforeUpdate')
  },
  updated() {
    this.logHook('updated')
  },
  activated() {
    this.isActive = true
    this.logHook('activated')
  },
  deactivated() {
    this.isActive = false
    this.logHook('deactivated')
  },
  beforeDestroy() {
    this.logHook('beforeDestroy')
  },
  destroyed() {
    this.logHook('destroyed')
  },
  errorCaptured(err) {
    this.logHook('errorCaptured: ' + err.message)
    return false
  }
}
