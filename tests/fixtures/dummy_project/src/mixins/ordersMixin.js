import { formatCurrency, formatDate } from '../utils/formatters'
import { fetchOrders, deleteOrder } from '../utils/api'
import { capitalize } from '../utils/formatters'

export default {
  data() {
    return {
      orders: [],
      selectedOrder: null,
      isLoading: false,
    }
  },
  computed: {
    orderCount() {
      return this.orders.length
    },
    formattedOrders() {
      return this.orders.map(o => ({
        ...o,
        total: formatCurrency(o.total),
        date: formatDate(o.createdAt),
        status: capitalize(o.status),
      }))
    },
  },
  methods: {
    async loadOrders() {
      this.isLoading = true
      try {
        this.orders = await fetchOrders({ limit: 50 })
      } finally {
        this.isLoading = false
      }
    },
    async removeOrder(id) {
      await deleteOrder(id)
      this.orders = this.orders.filter(o => o.id !== id)
    },
    selectOrder(order) {
      this.selectedOrder = order
    },
  },
  created() {
    this.loadOrders()
  },
}
