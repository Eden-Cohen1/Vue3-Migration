# Bug: Report generates manual steps for composables that were never created

## Problem

When the tool decides to skip generating a composable (e.g., because it only contains lifecycle hooks — `skipped-lifecycle-only`), the migration report still lists manual steps for that composable as if the file exists. Users following these steps will look for files that don't exist.

## Affected composables

- `useLocale` — report says "1 step: Replace skipped-lifecycle-only" but `src/composables/useLocale.js` was never generated
- `usePolling` — report says "1 step: Replace skipped-lifecycle-only" but `src/composables/usePolling.js` was never generated

## Report output (what the user sees)

```
### 🟡 `useLocale` — 1 step

- **Step 1:** Replace `skipped-lifecycle-only` → Manually convert lifecycle hooks to the composable, or remove the mixin if unused.

> **Unused members:** `currentLocale`, `availableLocales`, `translations`, `isLoadingLocale`, `isRTL`, `localeLabel`, `setLocale`, `translate`, `loadTranslations` — consider removing from composable return
```

```
### 🟡 `usePolling` — 1 step

- **Step 1:** Replace `skipped-lifecycle-only` → Manually convert lifecycle hooks to the composable, or remove the mixin if unused.

> **Unused members:** `pollInterval`, `pollTimer`, `isPollActive`, `lastPollAt`, `isPolling`, `timeSinceLastPoll`, `startPolling`, `stopPolling`, `poll` — consider removing from composable return
```

## Input mixin: `localeMixin.js`

```js
// Edge case: Realistic filler mixin for project depth — i18n locale switching with dynamic translations
export default {
  data() {
    return {
      currentLocale: 'en',
      availableLocales: [
        { code: 'en', name: 'English' },
        { code: 'es', name: 'Spanish' },
        { code: 'fr', name: 'French' }
      ],
      translations: {},
      isLoadingLocale: false
    }
  },

  computed: {
    isRTL() {
      const rtlLocales = ['ar', 'he', 'fa', 'ur']
      return rtlLocales.includes(this.currentLocale)
    },

    localeLabel() {
      const locale = this.availableLocales.find((l) => l.code === this.currentLocale)
      return locale ? locale.name : this.currentLocale
    }
  },

  methods: {
    setLocale(code) {
      if (code === this.currentLocale) return

      const locale = this.availableLocales.find((l) => l.code === code)
      if (!locale) {
        console.warn(`Locale "${code}" is not available`)
        return
      }

      this.currentLocale = code
      document.documentElement.setAttribute('lang', code)
      document.documentElement.setAttribute('dir', this.isRTL ? 'rtl' : 'ltr')

      this.loadTranslations(code)
      this.$emit('locale-changed', code)
    },

    translate(key, params) {
      let text = this.translations[key] || key

      if (params && typeof params === 'object') {
        Object.keys(params).forEach((param) => {
          text = text.replace(new RegExp(`{${param}}`, 'g'), params[param])
        })
      }

      return text
    },

    loadTranslations(locale) {
      this.isLoadingLocale = true

      return new Promise((resolve) => {
        this.$nextTick(() => {
          this.translations = {
            'app.title': locale === 'es' ? 'Gestión de Proyectos' : locale === 'fr' ? 'Gestion de Projets' : 'Project Management',
            'app.save': locale === 'es' ? 'Guardar' : locale === 'fr' ? 'Sauvegarder' : 'Save',
            'app.cancel': locale === 'es' ? 'Cancelar' : locale === 'fr' ? 'Annuler' : 'Cancel',
            'app.delete': locale === 'es' ? 'Eliminar' : locale === 'fr' ? 'Supprimer' : 'Delete',
            'app.loading': locale === 'es' ? 'Cargando...' : locale === 'fr' ? 'Chargement...' : 'Loading...'
          }
          this.isLoadingLocale = false
          resolve(this.translations)
        })
      })
    }
  },

  mounted() {
    this.loadTranslations(this.currentLocale)
  }
}
```

## Input mixin: `pollingMixin.js`

```js
// Edge case: Periodic data refresh with timer lifecycle management.
// Tests migration of lifecycle hooks (mounted/beforeDestroy -> onMounted/onBeforeUnmount)
// and cleanup of setInterval references during component teardown.
export default {
  data() {
    return {
      pollInterval: 30000,
      pollTimer: null,
      isPollActive: false,
      lastPollAt: null
    }
  },

  computed: {
    isPolling() {
      return this.isPollActive && this.pollTimer !== null
    },

    timeSinceLastPoll() {
      if (!this.lastPollAt) return null
      const elapsed = Date.now() - this.lastPollAt
      if (elapsed < 1000) return 'just now'
      if (elapsed < 60000) return `${Math.floor(elapsed / 1000)}s ago`
      if (elapsed < 3600000) return `${Math.floor(elapsed / 60000)}m ago`
      return `${Math.floor(elapsed / 3600000)}h ago`
    }
  },

  methods: {
    startPolling(fn) {
      if (this.pollTimer) {
        this.stopPolling()
      }

      this._pollCallback = fn || this._pollCallback
      this.isPollActive = true
      this.poll()

      this.pollTimer = setInterval(() => {
        this.poll()
      }, this.pollInterval)
    },

    stopPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
      this.isPollActive = false
    },

    poll() {
      if (typeof this._pollCallback === 'function') {
        this.lastPollAt = Date.now()
        try {
          const result = this._pollCallback()
          if (result && typeof result.then === 'function') {
            result.catch(err => {
              console.warn('[pollingMixin] Poll callback error:', err)
            })
          }
        } catch (err) {
          console.warn('[pollingMixin] Poll callback error:', err)
        }
      }
    }
  },

  mounted() {
    // Subclass can override to auto-start polling
  },

  beforeDestroy() {
    this.stopPolling()
  }
}
```

## Generated composable: NONE

No composable file was generated for either mixin. `src/composables/useLocale.js` and `src/composables/usePolling.js` do not exist on disk.

## What's wrong

The report generation step creates action items for composables regardless of whether the composable file was actually written to disk. When the tool decides to skip generating a composable (e.g., because of `skipped-lifecycle-only`), the report should either:
1. Not list the composable in the action plan at all, OR
2. Clearly state "composable was not generated — manual conversion required" instead of listing steps that imply the file exists

The report also lists "Unused members" for these non-existent composables, which is nonsensical since there's no composable to remove members from.

## Investigation

Find the code path that generates the "Action Plan" section of the migration report. Determine why composables that were skipped (not written to disk) still get entries with manual steps. The fix should check whether the composable file was actually generated before adding it to the report's action plan. Look for where the `skipped-lifecycle-only` category is handled — it seems like the report builder treats skipped composables the same as generated ones.
