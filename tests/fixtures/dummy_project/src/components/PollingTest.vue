<template>
  <div>
    <p>Polling test component</p>
  </div>
</template>

<script>
import pollingMixin from '@/mixins/pollingMixin'

export default {
  name: 'PollingTest',
  mixins: [pollingMixin],
}
</script>
