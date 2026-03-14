export function validateConfig(config) {
  return config && typeof config.name === 'string'
}
