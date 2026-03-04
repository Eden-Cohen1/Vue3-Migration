// Transformation confidence: LOW (7 warnings — see migration report)
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from "vue";

export function useShowcase() {
  const items = ref([1, 2, 3]);
  const config = ref({ theme: "dark", lang: "en" });
  const query = ref("");
  const count = ref(0);
  const isVisible = ref(true);

  const total = computed(() => {
    return items.value.length + count.value;
  });
  const fullLabel = computed({
    get: () => {
      return query.value + " (" + count.value + ")";
    },
    set: (val) => {
      query.value = val.split(" (")[0];
    },
  });

  function search(term) {
    nextTick(() => {
      console.log("searching", term);
    });
    // ⚠ MIGRATION: this.$emit is not available in composables
    this.$emit("search-changed", term);
  }
  function addItem(item) {
    items.value[items.value.length] = item;
  }
  function removeKey(key) {
    delete config.value[key];
  }
  async function fetchData() {
    // ⚠ MIGRATION: this.$route is not available in composables
    const page = this.$route.params.page;
    // ⚠ MIGRATION: this.$store is not available in composables
    const data = await this.$store.dispatch("load", { page });
    items.value = data;
  }
  function navigate(path) {
    // ⚠ MIGRATION: this.$router is not available in composables
    this.$router.push(path);
  }
  function legacyHandler() {
    const self = this;
    setTimeout(function () {
      self.count++;
    }, 100);
  }
  function readBracket() {
    return count.value + query.value;
  }

  watch(query, (val, oldVal) => {
    count.value = val.length;
    search(val);
  });
  watch(
    items,
    (newItems) => {
      count.value = newItems.length;
    },
    { deep: true, immediate: true },
  );

  fetchData();

  onMounted(() => {
    console.log("mounted with", items.value.length, "items");
  });
  onBeforeUnmount(() => {
    console.log("cleaning up");
  });

  return {
    items,
    config,
    query,
    count,
    isVisible,
    total,
    fullLabel,
    search,
    addItem,
    removeKey,
    fetchData,
    navigate,
    legacyHandler,
    readBracket,
    query,
    items,
  };
}
