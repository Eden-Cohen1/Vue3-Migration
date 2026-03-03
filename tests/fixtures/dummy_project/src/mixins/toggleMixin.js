export default {
  data() {
    return {
      isOpen: false,
      label: 'Toggle'
    }
  },
  methods: {
    toggle() {
      this.isOpen = !this.isOpen
    },
    open() {
      this.isOpen = true
    },
    close() {
      this.isOpen = false
    }
  }
}
