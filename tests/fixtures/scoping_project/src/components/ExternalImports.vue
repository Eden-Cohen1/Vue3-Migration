<template>
  <div>{{ show() }}</div>
</template>

<script>
import externalImportsMixin from '@/mixins/externalImportsMixin'

export default {
  name: 'ExternalImports',
  mixins: [externalImportsMixin],
}
</script>
