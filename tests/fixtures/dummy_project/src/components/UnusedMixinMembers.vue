<template>
  <div>
    <ul>
      <li v-for="item in items" :key="item.id">{{ item.name }}</li>
    </ul>
  </div>
</template>

<script>
import itemsMixin from '@/mixins/itemsMixin'

export default {
  name: 'UnusedMixinMembers',
  mixins: [itemsMixin],
}
</script>
