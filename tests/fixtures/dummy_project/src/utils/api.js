export function fetchOrders(params) {
  return fetch('/api/orders?' + new URLSearchParams(params)).then(r => r.json())
}

export function deleteOrder(id) {
  return fetch(`/api/orders/${id}`, { method: 'DELETE' })
}
