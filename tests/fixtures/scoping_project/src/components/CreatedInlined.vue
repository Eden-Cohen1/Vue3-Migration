<template>
  <div>{{ bar() }}</div>
</template>

<script>
import createdInlinedMixin from '@/mixins/createdInlinedMixin'

export default {
  name: 'CreatedInlined',
  mixins: [createdInlinedMixin],
}
</script>
