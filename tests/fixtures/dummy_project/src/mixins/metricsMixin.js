export default {
  data() {
    return {
      rawData: [10, 20, 30],
      multiplier: 1.5,
      offset: 100,
      precision: 2
    }
  },
  computed: {
    sum() {
      return this.rawData.reduce((a, b) => a + b, 0)
    },
    average() {
      return this.rawData.length ? this.sum / this.rawData.length : 0
    },
    scaled() {
      return this.average * this.multiplier
    },
    adjusted() {
      return this.scaled + this.offset
    },
    display() {
      return `Result: ${this.adjusted.toFixed(this.precision)}`
    },
    trend() {
      return this.adjusted > this.offset ? 'up' : this.adjusted < this.offset ? 'down' : 'flat'
    }
  },
  methods: {
    addDataPoint(val) {
      this.rawData.push(val)
    },
    reset() {
      this.rawData = []
      this.multiplier = 1
      this.offset = 0
    }
  }
}
