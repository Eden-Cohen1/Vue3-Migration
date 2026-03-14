// Mixin that ONLY provides lifecycle hooks — no data, computed, or methods
export default {
  mounted() {
    console.log('Component mounted — lifecycle side effect')
    document.title = 'Mounted'
  },
  beforeDestroy() {
    console.log('Component about to be destroyed')
    document.title = ''
  },
}
