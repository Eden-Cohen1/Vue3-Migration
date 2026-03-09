<template>
  <div>
    <!-- A1: this.translationCache is ONLY in this comment — should NOT be detected as used -->
    <!-- TODO: use translationCache for performance -->
    <h1>{{ welcomeMessage }}</h1>
    <p>{{ itemCount }}</p>
    <span>{{ formatDate(new Date()) }}</span>
    <span>{{ formatPrice(9.99) }}</span>
    <button @click="getGreeting">{{ greeting }}</button>
  </div>
</template>

<script>
import i18nMixin from '@/mixins/i18nMixin'

export default {
  name: 'I18nTest',
  mixins: [i18nMixin],
  data() {
    return {
      // A1: "translationCache" appears in a comment above, but not in real code
      items: [{ id: 1 }, { id: 2 }, { id: 3 }]
    }
  }
}
</script>
