<template lang="pug">
.ts-confirm-overlay(v-if="visible", @click="cancel")
  .ts-confirm-panel(@click.stop="")
    .ts-confirm-header
      h3 {{ title }}
      button.modal-close-btn(type="button", :aria-label="$t('Close')", @click="cancel")
        i.fa.fa-times(aria-hidden="true")
    p.ts-confirm-lead(v-if="lead") {{ lead }}
    p.ts-confirm-error(v-if="error") {{ error }}
    .ts-confirm-actions
      button.btn.btn-default(type="button", :disabled="busy", @click="cancel") {{ $t('Cancel') }}
      button.btn(:class="confirmClass || 'btn-primary'", type="button", :disabled="busy", @click="$emit('confirm')")
        | {{ confirmLabel || $t('Confirm') }}
</template>

<script lang="ts" setup>
import { ref } from 'vue'

defineProps<{
  title: string
  lead?: string
  confirmLabel?: string
  confirmClass?: string
  error?: string
  busy?: boolean
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const visible = ref(false)

function show() {
  visible.value = true
}

function close() {
  visible.value = false
}

function cancel() {
  close()
  emit('cancel')
}

defineExpose({ show, close })
</script>

<style lang="stylus">
.ts-confirm-overlay
  position: fixed
  z-index: 1000
  top: 0
  left: 0
  width: 100%
  height: 100%
  background-color: rgba(0, 0, 0, 0.5)
  display: flex
  align-items: center
  justify-content: center
  padding: 24px

.ts-confirm-panel
  background-color: $clr-white
  border-radius: 4px
  padding: 32px 40px
  width: 440px
  max-width: calc(100vw - 48px)
  position: relative

  .ts-confirm-header
    display: flex
    justify-content: space-between
    align-items: center
    margin-bottom: 16px
    h3
      font-size: 22px
      margin: 0
    .modal-close-btn
      background: none
      border: none
      font-size: 20px
      color: #666
      cursor: pointer
      padding: 4px 8px
      line-height: 1
      border-radius: 4px
      &:hover
        color: #333
        background-color: rgba(0, 0, 0, 0.05)

  .ts-confirm-lead
    margin: 0 0 20px
    color: $clr-secondary-text-light
    font-size: 15px
    line-height: 1.5

  .ts-confirm-error
    color: #d9534f
    margin: 0 0 16px
    font-size: 14px

  .ts-confirm-actions
    display: flex
    justify-content: flex-end
    gap: 8px
    .btn
      display: inline-block
      padding: 8px 16px
      font-size: 14px
      font-weight: 500
      line-height: 1.4
      border-radius: 4px
      border: 1px solid transparent
      cursor: pointer
      &:disabled
        opacity: 0.65
        cursor: default
    .btn-default
      background: $clr-white
      border-color: #ccc
      color: #333
      &:hover
        background-color: #f5f5f5
    .btn-primary
      background: #2185d0
      border-color: #2185d0
      color: #fff
    .btn-danger
      background: #d9534f
      border-color: #d9534f
      color: #fff
</style>
