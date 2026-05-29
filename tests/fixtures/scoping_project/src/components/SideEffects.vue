<template>
  <div>
    <p>{{ ticks }}</p>
    <button @click="tick">Tick</button>
  </div>
</template>

<script>
import sideEffectsMixin from '@/mixins/sideEffectsMixin'

export default {
  name: 'SideEffects',
  mixins: [sideEffectsMixin],
}
</script>
