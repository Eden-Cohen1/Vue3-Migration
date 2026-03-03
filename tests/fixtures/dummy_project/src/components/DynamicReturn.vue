<template>
  <div>
    <p>{{ label }}: {{ isOpen ? 'Open' : 'Closed' }}</p>
    <button @click="toggle">Toggle</button>
    <button @click="open">Open</button>
    <button @click="close">Close</button>
  </div>
</template>

<script>
import toggleMixin from '@/mixins/toggleMixin'

export default {
  name: 'DynamicReturn',
  mixins: [toggleMixin],
}
</script>
