// Transformation confidence: HIGH (0 warnings — see migration report)
import { formatCurrency, formatDate } from '../utils/formatters'

import { fetchOrders, deleteOrder } from '../utils/api'

import { capitalize } from '../utils/formatters'


import { ref, computed } from 'vue'

export function useOrders() {
  const orders = ref([])
  const selectedOrder = ref(null)
  const isLoading = ref(false)

  const orderCount = computed(() => orders.value.length)
  const formattedOrders = computed(() => {
    return orders.value.map(o => ({
            ...o,
            total: formatCurrency(o.total),
            date: formatDate(o.createdAt),
            status: capitalize(o.status),
          }))
  })

  async function loadOrders() {
    isLoading.value = true
    try {
      orders.value = await fetchOrders({ limit: 50 })
    } finally {
      isLoading.value = false
    }
  }
  async function removeOrder(id) {
    await deleteOrder(id)
    orders.value = orders.value.filter(o => o.id !== id)
  }
  function selectOrder(order) {
    selectedOrder.value = order
  }

  loadOrders()

  return { orders, selectedOrder, isLoading, orderCount, formattedOrders, loadOrders, removeOrder, selectOrder }
}
