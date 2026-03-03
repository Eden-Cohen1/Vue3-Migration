<template>
  <div>
    <p>Count: {{ count }}</p>
    <p>Theme: {{ config.theme }}</p>
    <ul>
      <li v-for="item in items" :key="item">{{ item }}</li>
    </ul>
    <ul>
      <li v-for="tag in tags" :key="tag">{{ tag }}</li>
    </ul>
    <p>{{ name }}</p>
    <p>{{ isActive }}</p>
    <p>{{ metadata }}</p>
    <p>{{ timestamp }}</p>
  </div>
</template>

<script>
import stateMixin from '@/mixins/stateMixin'

export default {
  name: 'ComplexDefaults',
  mixins: [stateMixin],
  data() {
    return {
      config: {
        theme: 'dark',
        pageSize: 50,
        nested: {
          deep: false,
          extra: 'custom'
        }
      },
      items: ['pre-loaded-1', 'pre-loaded-2'],
    }
  },
}
</script>
