export default {
  data() {
    return {
      count: 0,
      name: '',
      items: [],
      config: {
        theme: 'light',
        pageSize: 10,
        nested: {
          deep: true
        }
      },
      isActive: false,
      metadata: null,
      tags: [1, 2, 3],
      timestamp: Date.now()
    }
  }
}
