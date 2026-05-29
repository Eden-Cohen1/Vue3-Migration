<template>
  <div>
    <button @click="announce">Announce</button>
  </div>
</template>

<script>
import usedEmitMixin from '@/mixins/usedEmitMixin'

export default {
  name: 'UsedEmit',
  mixins: [usedEmitMixin],
}
</script>
