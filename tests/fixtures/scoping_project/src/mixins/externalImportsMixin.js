// Scenario 10: external imports follow member scoping. Component uses ONLY
// `show` (uses formatDate). `process` (uses crunch) is dropped, so the `crunch`
// import should be filtered out while `formatDate` remains.
import { formatDate } from '@/utils/date'
import { crunch } from '@/utils/heavy'

export default {
  data() {
    return {
      stamp: null,
    }
  },
  methods: {
    show() {
      return formatDate(this.stamp)
    },
    process() {
      return crunch(this.stamp)
    },
  },
}
