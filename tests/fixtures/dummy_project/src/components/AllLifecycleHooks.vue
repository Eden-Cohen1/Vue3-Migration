<template>
  <div>
    <p>Mount count: {{ mountCount }}</p>
    <p>Active: {{ isActive }}</p>
    <ul>
      <li v-for="(hook, idx) in hookLog" :key="idx">{{ hook }}</li>
    </ul>
    <button @click="logHook('manual')">Log Hook</button>
  </div>
</template>

<script>
import lifecycleMixin from '@/mixins/lifecycleMixin'

export default {
  name: 'AllLifecycleHooks',
  mixins: [lifecycleMixin],
}
</script>
