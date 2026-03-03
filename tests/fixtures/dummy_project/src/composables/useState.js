import { ref } from 'vue'

export function useState() {
  const count = ref(0)
  const name = ref('')
  const items = ref([])
  const config = ref({
    theme: 'light',
    pageSize: 10,
    nested: {
      deep: true
    }
  })
  const isActive = ref(false)
  const metadata = ref(null)
  const tags = ref([1, 2, 3])
  const timestamp = ref(Date.now())

  return {
    count,
    name,
    items,
    config,
    isActive,
    metadata,
    tags,
    timestamp
  }
}
