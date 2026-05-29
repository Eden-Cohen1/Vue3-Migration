<template>
  <div>
    <input :value="text" @input="setValue($event.target.value)" />
  </div>
</template>

<script>
import debounceMixin from '@/mixins/debounceMixin'

export default {
  name: 'Debounce',
  mixins: [debounceMixin],
}
</script>
