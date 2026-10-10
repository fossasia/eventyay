<template lang="pug">
dialog.pretalx-modal.shift-edit-modal(ref="modal", :aria-labelledby="titleId", @click="onBackdrop", @cancel.prevent="cancel")
	.dialog-inner(@click.stop="")
		button.close-button(type="button", aria-label="Close dialog", @click="cancel") ✕
		h3(:id="titleId") {{ $t('Edit shift') }}
		p.shift-edit-error(v-if="error") {{ error }}
		form(@submit.prevent="submit")
			.data
				label.data-row
					span.data-label {{ $t('Title') }}
					input.form-control(type="text", v-model="form.title", required)
				label.data-row
					span.data-label {{ $t('Description') }}
					textarea.form-control(v-model="form.description", rows="3")
				.data-row.data-row-split
					label.data-col
						span.data-label {{ $t('Start') }}
						input.form-control(type="datetime-local", v-model="form.start", required)
					label.data-col
						span.data-label {{ $t('End') }}
						input.form-control(type="datetime-local", v-model="form.end", required)
				label.data-row
					span.data-label {{ $t('Location') }}
					select.form-control(v-model="form.room")
						option(value="") {{ $t('No location') }}
						option(v-for="room in rooms", :key="room.id", :value="room.id") {{ getLocalizedString(room.name) }}
				.data-row
					span.data-label {{ $t('Roles') }}
					.role-row(v-for="(row, index) in form.roles", :key="index")
						select.form-control.role-select(v-model="row.id")
							option(value="") {{ $t('Select a role') }}
							option(v-for="role in availableRoles(index)", :key="role.id", :value="role.id") {{ getLocalizedString(role.name) }}
						input.form-control.role-capacity(type="number", min="1", v-model.number="row.capacity")
						button.role-row-remove(type="button", :aria-label="$t('Remove')", @click="removeRole(index)")
							svg.role-row-remove-icon(viewBox="0 0 24 24", aria-hidden="true")
								path(fill="currentColor", d="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z")
					button.add-role-btn(type="button", @click="addRole")
						svg.add-role-icon(viewBox="0 0 24 24", aria-hidden="true")
							path(fill="currentColor", d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z")
						span {{ $t('Add role') }}
			.button-row
				bunt-button#btn-cancel(type="button", :disabled="busy", @click="cancel") {{ $t('Cancel') }}
				bunt-button#btn-save(type="submit", :loading="busy") {{ $t('Save') }}
</template>

<script setup>
import { ref, useId } from 'vue'
import moment from 'moment-timezone'
import { getLocalizedString } from '../utils'

const INPUT_FORMAT = 'YYYY-MM-DDTHH:mm'

const props = defineProps({
	rooms: { type: Array, default: () => [] },
	roles: { type: Array, default: () => [] },
	timezone: { type: String, default: 'UTC' },
	error: { type: String, default: '' },
	busy: { type: Boolean, default: false },
})

const emit = defineEmits(['save', 'cancel'])

const titleId = useId()
const modal = ref(null)
const form = ref({ title: '', description: '', start: '', end: '', room: '', roles: [] })
const original = ref({ start: null, end: null, startInput: '', endInput: '' })

function toInput (value) {
	return value ? value.clone().tz(props.timezone).format(INPUT_FORMAT) : ''
}

// Resend unchanged times as-is: reparsing the minute-precision local string drops seconds and picks the earlier repeated DST hour.
function toPayloadTime (input, originalValue, originalInput) {
	if (originalValue && input === originalInput) return originalValue.toISOString()
	return moment.tz(input, props.timezone).toISOString()
}

function show (session) {
	original.value = {
		start: session?.start ?? null,
		end: session?.end ?? null,
		startInput: toInput(session?.start),
		endInput: toInput(session?.end),
	}
	form.value = {
		title: getLocalizedString(session?.title) || '',
		description: session?.description || '',
		start: original.value.startInput,
		end: original.value.endInput,
		room: session?.room?.id ?? '',
		roles: (session?.roles || []).map(role => ({ id: role.id, capacity: role.capacity ?? 1 })),
	}
	modal.value?.showModal?.()
}

function close () {
	if (modal.value?.open) modal.value.close()
}

function cancel () {
	close()
	emit('cancel')
}

function onBackdrop (event) {
	if (event.target === modal.value) cancel()
}

function availableRoles (index) {
	const takenElsewhere = new Set(form.value.roles.filter((_, i) => i !== index).map(row => row.id).filter(Boolean))
	return props.roles.filter(role => !takenElsewhere.has(role.id))
}

function addRole () {
	form.value.roles.push({ id: '', capacity: 1 })
}

function removeRole (index) {
	form.value.roles.splice(index, 1)
}

function submit () {
	const { start, end, startInput, endInput } = original.value
	emit('save', {
		title: { en: form.value.title },
		description: form.value.description,
		start: toPayloadTime(form.value.start, start, startInput),
		end: toPayloadTime(form.value.end, end, endInput),
		room: form.value.room || null,
		roles: form.value.roles
			.filter(row => row.id)
			.map(row => ({ id: row.id, capacity: Number(row.capacity) || 1 })),
	})
}

defineExpose({ show, close })
</script>

<style lang="stylus">
dialog.pretalx-modal.shift-edit-modal
	max-width: 680px
	.shift-edit-error
		display: flex
		align-items: center
		padding: 10px 14px
		margin-bottom: 16px
		background-color: #fdecea
		border: 1px solid #f5c6cb
		border-radius: 4px
		color: #721c24
		font-size: 14px
	.data
		display: flex
		flex-direction: column
		gap: 16px
		font-size: 16px
	.data-row
		display: flex
		flex-direction: column
		gap: 6px
	.data-label
		font-size: 13px
		font-weight: 600
		color: $clr-grey-700
	.data-row-split
		flex-direction: row
		gap: 16px
		.data-col
			flex: 1
			display: flex
			flex-direction: column
			gap: 6px
	.form-control
		font-size: 14px
		font-family: inherit
		border: 1px solid $clr-grey-300
		border-radius: 4px
		padding: 8px 10px
		box-sizing: border-box
		width: 100%
	.role-row
		display: flex
		align-items: center
		gap: 10px
		margin-top: 10px
		.role-select
			flex: auto
		.role-capacity
			flex: none
			width: 90px
		.role-row-remove
			flex: none
			display: inline-flex
			align-items: center
			justify-content: center
			width: 28px
			height: 28px
			border: none
			border-radius: 4px
			background: transparent
			color: $clr-danger
			cursor: pointer
			padding: 0
			&:hover
				background-color: rgba(217, 83, 79, 0.1)
			.role-row-remove-icon
				width: 16px
				height: 16px
	.add-role-btn
		display: inline-flex
		align-items: center
		gap: 4px
		margin-top: 10px
		padding: 4px 0
		border: none
		background: none
		color: $clr-primary
		font-size: 14px
		font-weight: 600
		cursor: pointer
		&:hover
			text-decoration: underline
		.add-role-icon
			width: 16px
			height: 16px
	.button-row
		display: flex
		width: 100%
		margin-top: 24px
		gap: 8px
		.bunt-button-content
			font-size: 16px
		#btn-cancel
			button-style(color: $clr-grey-200)
		#btn-save
			margin-left: auto
			font-weight: bold
			button-style(color: $clr-primary)
</style>
