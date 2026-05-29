<template>
  <div>{{ label }}</div>
</template>

<script>
import templateOnlyMixin from '@/mixins/templateOnlyMixin'

export default {
  name: 'TemplateOnly',
  mixins: [templateOnlyMixin],
}
</script>
