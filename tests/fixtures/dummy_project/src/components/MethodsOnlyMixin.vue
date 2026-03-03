<template>
  <div>
    <button @click="execute('build')">Execute Build</button>
    <button @click="retry('deploy')">Retry Deploy</button>
    <button @click="cancel">Cancel</button>
    <button @click="log('info message')">Log Info</button>
    <button @click="clearLog">Clear Log</button>
    <ul>
      <li v-for="(entry, idx) in actionLog" :key="idx">{{ entry }}</li>
    </ul>
  </div>
</template>

<script>
import actionsMixin from '@/mixins/actionsMixin'

export default {
  name: 'MethodsOnlyMixin',
  mixins: [actionsMixin],
}
</script>
