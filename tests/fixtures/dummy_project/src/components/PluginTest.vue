<template>
  <div>
    <p>{{ message }}</p>
    <button @click="showSuccess">Success</button>
    <button @click="showError">Error</button>
    <button @click="removeItem">Remove</button>
    <button @click="openDialog">Dialog</button>
    <button @click="navigate">Go</button>
    <button @click="notifyParent">Notify</button>
    <button @click="refresh">Refresh</button>
    <button @click="setField">Set</button>
  </div>
</template>

<script>

import { usePlugin } from '@/composables/usePlugin'
export default {
  setup() {
    const { message, showSuccess, showError, removeItem, openDialog, navigate, notifyParent, refresh, setField } = usePlugin()

    return { message, showSuccess, showError, removeItem, openDialog, navigate, notifyParent, refresh, setField }
  },
  name: 'PluginTest',
}
</script>
