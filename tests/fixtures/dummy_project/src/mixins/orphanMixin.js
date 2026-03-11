/**
 * Task 3: This mixin is NOT imported by any component.
 * The report should flag it as "safe to delete".
 */
export default {
  data() {
    return {
      orphanData: 'nobody uses me',
      counter: 0,
    }
  },

  methods: {
    increment() {
      this.counter++
    },
    decrement() {
      this.counter--
    }
  }
}
