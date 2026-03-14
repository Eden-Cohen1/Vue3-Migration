<template>
  <div>
    <input v-model="query" />
    <span>{{ total }}</span>
    <span>{{ count }}</span>
    <button @click="startWatchingQuery">Watch Query</button>
    <button @click="startWatchingUserName">Watch User</button>
    <button @click="startDeepWatch">Deep Watch</button>
    <button @click="startWatchWithCleanup">Watch+Cleanup</button>
    <button @click="startDynamicWatch('query')">Dynamic</button>
    <button @click="fetchResults('test')">Fetch</button>
  </div>
</template>

<script>

import { useWatch } from '@/composables/useWatch'
export default {
  setup() {
    const { query, count, total, startWatchingQuery, startWatchingUserName, startDeepWatch, startWatchWithCleanup, startDynamicWatch, fetchResults } = useWatch()

    return { query, count, total, startWatchingQuery, startWatchingUserName, startDeepWatch, startWatchWithCleanup, startDynamicWatch, fetchResults }
  },
  name: 'VerifyWatch',
}
</script>
