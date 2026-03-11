<template>
  <div>
    <!-- Task 1: This component imports verifyMixin but uses NONE of its members.
         The tool should auto-remove the import and mixins array entry. -->
    <p>I don't use any mixin members</p>
  </div>
</template>

<script>

export default {
  name: 'VerifyEmpty',
  data() {
    return {
      ownData: 'only my own stuff'
    }
  }
}
</script>
