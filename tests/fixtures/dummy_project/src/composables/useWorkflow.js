import { ref, computed } from 'vue'

export function useWorkflow() {
  const steps = ref([])
  const currentStep = ref(0)
  const isComplete = ref(false)
  const errors = ref([])

  const progress = computed(() => steps.value.length > 0 ? (currentStep.value / steps.value.length) * 100 : 0)
  const currentStepData = computed(() => steps.value[currentStep.value] || null)
  const canProceed = computed(() => currentStep.value < steps.value.length - 1 && errors.value.length === 0)

  function start() {
    currentStep.value = 0
    isComplete.value = false
    errors.value = []
    validate()
  }

  function next() {
    if (validate()) {
      currentStep.value++
      if (currentStep.value >= steps.value.length) {
        complete()
      }
    }
  }

  function previous() {
    if (currentStep.value > 0) {
      currentStep.value--
    }
  }

  function complete() {
    isComplete.value = true
    onComplete()
  }

  function validate() {
    errors.value = []
    const step = currentStepData.value
    if (step && step.required && !step.value) {
      errors.value.push(`Step ${currentStep.value + 1} is required`)
    }
    return errors.value.length === 0
  }

  function onComplete() {
    log('Workflow complete')
  }

  function reset() {
    errors.value = []
    isComplete.value = false
    start()
  }

  function log(msg) {
    console.log(msg)
  }

  return {
    steps,
    currentStep,
    isComplete,
    errors,
    progress,
    currentStepData,
    canProceed,
    start,
    next,
    previous,
    complete,
    validate,
    onComplete,
    reset,
    log
  }
}
