// Mixin with isLoading (overlaps with loadingMixin) for collision testing
export default {
  data() {
    return {
      isLoading: false,
      statusMessage: '',
    }
  },
  methods: {
    setStatus(msg) {
      this.statusMessage = msg
    },
    clearStatus() {
      this.statusMessage = ''
      this.isLoading = false
    },
  },
}
