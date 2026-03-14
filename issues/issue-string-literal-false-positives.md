# Bug: Tool flags `this.$emit`/`this.$refs`/etc. inside string literals as real Vue API calls

## Problem

The tool's detection of Vue 2 instance APIs (`this.$emit`, `this.$refs`, `this.$router`, `this.$route`, `this.$store`) does not distinguish between actual executable code and string literals. When a mixin contains these patterns inside strings (documentation text, log messages, help text), the tool:
1. Adds incorrect `// ❌ not available in composable` inline comments to the generated composable
2. Generates false manual steps in the migration report

This results in **5 completely false steps** for a single composable that actually needs **0 manual steps**.

## Input mixin: `stringContainsCodeMixin.js`

```js
// Edge case: String values containing this.$emit, this.$router.push, this.$store.
// These are documentation/log strings and should NOT trigger Vue API migration warnings.
export default {
  data() {
    return {
      logEntries: [],
      debugMode: false,
      apiDocumentation: 'Call this.$emit("update") to notify parent components'
    }
  },

  computed: {
    debugSummary() {
      return this.logEntries.map(e => e.message).join('\n')
    },

    recentLogs() {
      return this.logEntries.slice(-10)
    }
  },

  methods: {
    logEvent(eventName, payload) {
      // String contains this.$emit — but it's just a log message, not real code
      const message = `Event fired: this.$emit("${eventName}") with payload: ${JSON.stringify(payload)}`
      this.logEntries.push({ message, timestamp: Date.now() })
    },

    buildDebugInfo() {
      // More strings that look like Vue API calls but are just documentation
      return {
        navigation: 'Router: this.$router.push("/dashboard") navigates to dashboard',
        state: 'Store: this.$store.dispatch("fetchData") loads data',
        events: 'Events: this.$emit("change", value) notifies parent',
        refs: 'DOM: this.$refs.input.focus() sets focus',
        lifecycle: 'Hooks: this.$nextTick(() => { ... }) waits for DOM update'
      }
    },

    logRouteChange(from, to) {
      // Contains this.$route but as a string description
      this.logEntries.push({
        message: `Route changed via this.$router.push from ${from} to ${to}`,
        timestamp: Date.now()
      })
    },

    getHelpText(topic) {
      const help = {
        events: 'Use this.$emit to send events to parent components. Example: this.$emit("save", data)',
        store: 'Access Vuex via this.$store.state.xxx or this.$store.getters.xxx',
        router: 'Navigate with this.$router.push({ name: "route-name" })'
      }
      return help[topic] || 'No help available'
    }
  }
}
```

## Generated composable: `useStringContainsCode.js` (WRONG)

```js
// ⚠️ 5 manual steps needed — see migration report for details
import { ref, computed } from 'vue'

export function useStringContainsCode() {
  const logEntries = ref([])
  const debugMode = ref(false)
  const apiDocumentation = ref('Call this.$emit("update") to notify parent components')  // ❌ not available in composable — use defineEmits or emit param

  const debugSummary = computed(() => logEntries.value.map(e => e.message).join('\n'))
  const recentLogs = computed(() => logEntries.value.slice(-10))

  function logEvent(eventName, payload) {
    // String contains this.$emit — but it's just a log message, not real code
    const message = `Event fired: this.$emit("${eventName}") with payload: ${JSON.stringify(payload)}`  // ❌ not available in composable — use defineEmits or emit param
    logEntries.value.push({ message, timestamp: Date.now() })
  }
  function buildDebugInfo() {
    // More strings that look like Vue API calls but are just documentation
    return {
      navigation: 'Router: this.$router.push("/dashboard") navigates to dashboard',  // ❌ not available in composable — use useRouter()
      state: 'Store: this.$store.dispatch("fetchData") loads data',  // ❌ not available in composable — use Pinia store
      events: 'Events: this.$emit("change", value) notifies parent',  // ❌ not available in composable — use defineEmits or emit param
      refs: 'DOM: this.$refs.input.focus() sets focus',  // ❌ not available in composable — use template refs
      lifecycle: 'Hooks: this.$nextTick(() => { ... }) waits for DOM update'
    }
  }
  function logRouteChange(from, to) {
    // Contains this.$route but as a string description
    logEntries.value.push({
      message: `Route changed via this.$router.push from ${from} to ${to}`,  // ❌ not available in composable — use useRouter()
      timestamp: Date.now()
    })
  }
  function getHelpText(topic) {
    const help = {
      events: 'Use this.$emit to send events to parent components. Example: this.$emit("save", data)',  // ❌ not available in composable — use defineEmits or emit param
      store: 'Access Vuex via this.$store.state.xxx or this.$store.getters.xxx',  // ❌ not available in composable — use Pinia store
      router: 'Navigate with this.$router.push({ name: "route-name" })'  // ❌ not available in composable — use useRouter()
    }
    return help[topic] || 'No help available'
  }

  return { logEntries, debugMode, apiDocumentation, debugSummary, recentLogs, logEvent, buildDebugInfo, logRouteChange, getHelpText }
}
```

## Report output (what the user sees)

```
### 🔴 `useStringContainsCode` — 5 steps

- **Step 1:** Replace `this.$emit` → [see how](#recipe-thisemit) (L7, L14, L22, L36)
- **Step 2:** Replace `this.$refs` → [see how](#recipe-thisrefs) (L23)
- **Step 3:** Replace `this.$router` → [see how](#recipe-thisrouter) (L20, L30, L38)
- **Step 4:** Replace `this.$route` → [see how](#recipe-thisroute) (L20, L30, L38)
- **Step 5:** Replace `this.$store` → [see how](#recipe-thisstore) (L21, L37)
```

## What's wrong

**Every single detection is a false positive.** All `this.$emit`, `this.$refs`, `this.$router`, `this.$route`, `this.$store` occurrences are inside:
- String literals: `'Call this.$emit("update") to notify...'`
- Template literals: `` `Event fired: this.$emit("${eventName}")...` ``
- Object value strings: `'Router: this.$router.push("/dashboard")...'`

None of these are actual Vue API calls that need migration. The composable should have **0 manual steps** and **0 inline warning comments**.

## Expected behavior

The tool should:
1. Not flag `this.$emit` (or any `this.$xxx`) when it appears inside a string literal (single quotes, double quotes, or backticks)
2. Not add `// ❌` inline comments for string-literal matches
3. Not generate report steps for string-literal matches
4. The composable header should say `// ✅ 0 issues` instead of `// ⚠️ 5 manual steps needed`

## Investigation

Find the detection logic that scans for `this.$emit`, `this.$refs`, `this.$router`, `this.$route`, `this.$store` patterns. It's likely using a regex that matches these patterns without checking whether the match is inside a string context. The fix should either:
- Use AST-aware detection (parse the JS and only flag `this.$xxx` in actual MemberExpression nodes), OR
- At minimum, check whether the match position falls inside a string literal (between quotes or backticks)

Also check: the inline comment injection logic (`// ❌ not available in composable`) likely has the same issue — it appends comments based on the same raw regex matches.
