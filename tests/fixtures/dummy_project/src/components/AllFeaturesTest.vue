<template>
  <div>
    <!-- A1: Comments mentioning members that should NOT be detected as used -->
    <!-- internalFlag controls internal state -->
    <!-- unusedHelper provides debug utilities -->
    <!-- unusedStatus shows editing state -->

    <input ref="titleInput" v-model="title" />
    <textarea v-model="description"></textarea>
    <p>{{ displayTitle }}</p>
    <p v-if="!isValid">{{ errorCount }} errors</p>
    <span>{{ formatAmount(42.5) }}</span>
    <button @click="save">Save</button>
    <button @click="cancel">Cancel</button>
    <button @click="validate">Validate</button>
    <button @click="focusTitle">Focus</button>
  </div>
</template>

<script>
import allFeaturesMixin from '@/mixins/allFeaturesMixin'

export default {
  name: 'AllFeaturesTest',
  mixins: [allFeaturesMixin],
  data() {
    return {
      entityId: 'entity-123'
    }
  }
}
</script>
