// Scenario 14: a member referenced ONLY in the component's <template> (never in
// <script>) must still be detected as used and returned. `hidden` is referenced
// nowhere and must be dropped.
export default {
  data() {
    return {
      label: 'hi',
      hidden: 'secret',
    }
  },
}
