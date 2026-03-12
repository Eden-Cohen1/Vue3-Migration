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
import watchMixin from '../mixins/watchMixin'

export default {
  name: 'VerifyWatch',
  mixins: [watchMixin]
}
</script>
