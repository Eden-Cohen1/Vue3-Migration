<template>
  <div>
    <div class="progress" :style="{ width: progress + '%' }"></div>
    <p>Step {{ currentStep + 1 }}: {{ currentStepData ? currentStepData.name : 'N/A' }}</p>
    <p v-if="isComplete">Workflow Complete!</p>
    <ul v-if="errors.length">
      <li v-for="err in errors" :key="err">{{ err }}</li>
    </ul>
    <button @click="start">Start</button>
    <button @click="previous" :disabled="currentStep === 0">Previous</button>
    <button @click="next" :disabled="!canProceed">Next</button>
    <button @click="reset">Reset</button>
  </div>
</template>

<script>
import workflowMixin from '@/mixins/workflowMixin'

export default {
  name: 'InternalMethodCalls',
  mixins: [workflowMixin],
  created() {
    this.steps = [
      { name: 'Step 1', required: true, value: 'done' },
      { name: 'Step 2', required: false },
      { name: 'Step 3', required: true, value: 'done' },
    ]
  },
}
</script>
