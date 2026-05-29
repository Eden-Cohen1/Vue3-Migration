// Scenario 3: computed-on-computed-on-data. Component uses ONLY `initials`,
// which reads `fullName`, which reads `firstName` + `lastName`. All declared,
// only `initials` returned.
export default {
  data() {
    return {
      firstName: 'Jane',
      lastName: 'Doe',
    }
  },
  computed: {
    fullName() {
      return this.firstName + ' ' + this.lastName
    },
    initials() {
      return this.fullName.split(' ').map(w => w[0]).join('')
    },
  },
}
