export function formatCurrency(value) {
  return `$${Number(value).toFixed(2)}`
}

export function formatDate(dateStr) {
  return new Date(dateStr).toLocaleDateString()
}

export function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}
