<template>
  <div>
    <p>{{ displayPrefix }}</p>
    <p>{{ currencySymbol }}</p>
    <p>{{ format('hello') }}</p>
    <p>{{ formatCurrency(99.99) }}</p>
    <p>{{ formatList(['a', 'b', 'c']) }}</p>
    <p>{{ buildLabel('items', 5) }}</p>
    <p v-html="wrapTag('strong', 'bold text')"></p>
    <input v-model="prefix" placeholder="Prefix">
    <input v-model="suffix" placeholder="Suffix">
    <select v-model="locale">
      <option value="en">English</option>
      <option value="fr">French</option>
    </select>
    <select v-model="currency">
      <option value="USD">USD</option>
      <option value="EUR">EUR</option>
    </select>
  </div>
</template>

<script>
import formattingMixin from '@/mixins/formattingMixin'

export default {
  name: 'TemplateLiterals',
  mixins: [formattingMixin],
}
</script>
