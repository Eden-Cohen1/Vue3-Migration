<template>
  <div>
    <p>Count: {{ count }}</p>
    <p>Name: {{ name }}</p>
    <p>Active: {{ isActive }}</p>
    <p>Metadata: {{ metadata }}</p>
    <p>Timestamp: {{ timestamp }}</p>
    <p>Config theme: {{ config.theme }}</p>
    <p>Config nested: {{ config.nested.deep }}</p>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
    <ul>
      <li v-for="tag in tags" :key="tag">{{ tag }}</li>
    </ul>
  </div>
</template>

<script>
import stateMixin from '@/mixins/stateMixin'

export default {
  name: 'DataOnlyMixin',
  mixins: [stateMixin],
}
</script>
