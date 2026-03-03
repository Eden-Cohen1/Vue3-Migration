<template>
  <div>
    <p>TTL: {{ ttl }}</p>
    <pre>{{ cache }}</pre>
    <button @click="set('key1', 'value1')">Set</button>
    <button @click="get('key1')">Get</button>
    <button @click="clear">Clear</button>
  </div>
</template>

<script>
import storageMixin from '@/mixins/storageMixin'

export default {
  name: 'ReactiveGuard',
  mixins: [storageMixin],
}
</script>
