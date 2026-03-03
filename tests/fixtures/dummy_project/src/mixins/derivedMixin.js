export default {
  data() {
    return {
      baseValue: 10,
      label: 'item'
    }
  },
  computed: {
    doubled() {
      return this.baseValue * 2
    },
    tripled() {
      return this.baseValue * 3
    },
    formatted() {
      return `${this.label}: ${this.baseValue}`
    },
    isPositive() {
      return this.baseValue > 0
    },
    summary() {
      return this.isPositive ? this.formatted : 'N/A'
    }
  }
}
