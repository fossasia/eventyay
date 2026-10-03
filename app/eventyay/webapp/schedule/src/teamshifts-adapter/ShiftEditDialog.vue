<template lang="pug">
dialog.pretalx-modal.shift-edit-modal(ref="modal", @click="onBackdrop", @cancel.prevent="cancel")
	.dialog-inner(@click.stop="")
		h3.shift-edit-title
			span {{ $t('Edit shift') }}
			button.modal-close-btn(type="button", aria-label="Close dialog", @click="cancel") ✕
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
							option(v-for="role in roles", :key="role.id", :value="role.id") {{ getLocalizedString(role.name) }}
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

<script>
import moment from 'moment-timezone'
import { getLocalizedString } from '../utils'

export default {
	name: 'ShiftEditDialog',
	emits: ['save', 'cancel'],
	props: {
		rooms: { type: Array, default: () => [] },
		roles: { type: Array, default: () => [] },
		timezone: { type: String, default: 'UTC' },
		error: { type: String, default: '' },
		busy: { type: Boolean, default: false },
	},
	data () {
		return {
			getLocalizedString,
			form: {
				title: '',
				description: '',
				start: '',
				end: '',
				room: '',
				roles: [],
			},
		}
	},
	methods: {
		show (session) {
			this.form = {
				title: getLocalizedString(session?.title) || '',
				description: session?.description || '',
				start: session?.start ? session.start.clone().tz(this.timezone).format('YYYY-MM-DDTHH:mm') : '',
				end: session?.end ? session.end.clone().tz(this.timezone).format('YYYY-MM-DDTHH:mm') : '',
				room: session?.room?.id ?? '',
				roles: (session?.roles || []).map(role => ({ id: role.id, capacity: role.capacity ?? 1 })),
			}
			this.$refs.modal?.showModal?.()
		},
		close () {
			if (this.$refs.modal?.open) this.$refs.modal.close()
		},
		cancel () {
			this.close()
			this.$emit('cancel')
		},
		onBackdrop (event) {
			if (event.target === this.$refs.modal) this.cancel()
		},
		addRole () {
			this.form.roles.push({ id: '', capacity: 1 })
		},
		removeRole (index) {
			this.form.roles.splice(index, 1)
		},
		submit () {
			const start = moment.tz(this.form.start, this.timezone)
			const end = moment.tz(this.form.end, this.timezone)
			this.$emit('save', {
				title: { en: this.form.title },
				description: this.form.description,
				start: start.toISOString(),
				end: end.toISOString(),
				room: this.form.room || null,
				roles: this.form.roles
					.filter(row => row.id)
					.map(row => ({ id: row.id, capacity: Number(row.capacity) || 1 })),
			})
		},
	},
}
</script>

<style lang="stylus">
.shift-edit-modal
	border: none
	padding: 0
	&::backdrop
		background-color: rgba(0, 0, 0, 0.5)
	.dialog-inner
		background-color: $clr-white
		border-radius: 4px
		padding: 32px 40px
		width: unquote("min(680px, 95vw)")
		max-height: calc(100vh - 48px)
		overflow-y: auto
		box-sizing: border-box
	.shift-edit-title
		font-size: 22px
		margin: 0 0 16px
		display: flex
		justify-content: space-between
		align-items: center
		.modal-close-btn
			background: none
			border: none
			font-size: 20px
			color: $clr-grey-600
			cursor: pointer
			padding: 4px 8px
			line-height: 1
			border-radius: 4px
			&:hover
				color: $clr-grey-900
				background-color: rgba(0, 0, 0, 0.05)
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
