<template>
  <div>
    <button @click="submit">Submit</button>
  </div>
</template>

<script>
import chainMixin from '@/mixins/chainMixin'

export default {
  name: 'Chain',
  mixins: [chainMixin],
}
</script>
