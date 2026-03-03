import { ref } from 'vue'

export function useActions() {
  const actionLog = ref([])

  function execute(cmd) {
    actionLog.value.push(cmd)
  }

  function retry(cmd) {
    actionLog.value.push('retry:' + cmd)
    execute(cmd)
  }

  function cancel() {
    actionLog.value.pop()
  }

  function log(msg) {
    actionLog.value.push(msg)
  }

  function clearLog() {
    actionLog.value = []
  }

  return {
    actionLog,
    execute,
    retry,
    cancel,
    log,
    clearLog
  }
}
