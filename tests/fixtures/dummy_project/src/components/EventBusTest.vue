<template>
  <div>
    <p>Listening: {{ isListening }}</p>
    <p>Events: {{ receivedEvents.length }}</p>
    <button @click="emitEvent('test', {})">Emit</button>
  </div>
</template>

<script>
import eventBusMixin from '@/mixins/eventBusMixin'

export default {
  name: 'EventBusTest',
  mixins: [eventBusMixin],
}
</script>
