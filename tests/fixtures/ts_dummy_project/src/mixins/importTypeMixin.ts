// Failure Mode 5: `import type` loses its type-only semantics.
// The parser strips the `type` keyword, generating `import { UserConfig }`
// instead of `import type { UserConfig }`. This causes runtime errors
// when UserConfig is a type-only export (not available at runtime).

import type { UserConfig } from '../types'
import { validateConfig } from '../utils'

export default {
  data() {
    return {
      config: null,
      isValid: false
    }
  },
  methods: {
    apply(config: UserConfig): void {
      this.config = config
      this.isValid = validateConfig(config)
    },
    reset(): void {
      this.config = null
      this.isValid = false
    }
  }
}
