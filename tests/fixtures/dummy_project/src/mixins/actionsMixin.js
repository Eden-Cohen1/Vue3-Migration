export default {
  data() {
    return {
      actionLog: []
    }
  },
  methods: {
    execute(cmd) {
      this.actionLog.push(cmd)
    },
    retry(cmd) {
      this.actionLog.push('retry:' + cmd)
      this.execute(cmd)
    },
    cancel() {
      this.actionLog.pop()
    },
    log(msg) {
      this.actionLog.push(msg)
    },
    clearLog() {
      this.actionLog = []
    }
  }
}
