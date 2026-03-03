export default {
  data() {
    return {
      steps: [],
      currentStep: 0,
      isComplete: false,
      errors: []
    }
  },
  computed: {
    progress() {
      return this.steps.length > 0 ? (this.currentStep / this.steps.length) * 100 : 0
    },
    currentStepData() {
      return this.steps[this.currentStep] || null
    },
    canProceed() {
      return this.currentStep < this.steps.length - 1 && this.errors.length === 0
    }
  },
  methods: {
    start() {
      this.currentStep = 0
      this.isComplete = false
      this.errors = []
      this.validate()
    },
    next() {
      if (this.validate()) {
        this.currentStep++
        if (this.currentStep >= this.steps.length) {
          this.complete()
        }
      }
    },
    previous() {
      if (this.currentStep > 0) {
        this.currentStep--
      }
    },
    complete() {
      this.isComplete = true
      this.onComplete()
    },
    validate() {
      this.errors = []
      const step = this.currentStepData
      if (step && step.required && !step.value) {
        this.errors.push(`Step ${this.currentStep + 1} is required`)
      }
      return this.errors.length === 0
    },
    onComplete() {
      this.log('Workflow complete')
    },
    reset() {
      this.errors = []
      this.isComplete = false
      this.start()
    },
    log(msg) {
      console.log(msg)
    }
  }
}
