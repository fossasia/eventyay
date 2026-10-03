<template lang="pug">
dialog.pretalx-modal.assign-volunteer-modal(ref="modal", @click="onBackdrop", @cancel.prevent="cancel")
	.dialog-inner(@click.stop="")
		h3.assign-volunteer-title
			span {{ $t('Assign volunteers') }}
			button.modal-close-btn(type="button", aria-label="Close dialog", @click="cancel") ✕
		p.assign-volunteer-error(v-if="error") {{ error }}
		.assign-data
			.assign-role(v-for="role in session?.roles || []", :key="role.id")
				h4 {{ getLocalizedString(role.name) }} ({{ getAssignedList(role).length }}/{{ role.capacity }} {{ $t('assigned') }})
				div
					span.member-chip(v-for="assignee in getAssignedList(role)", :key="assignee.id")
						| {{ assignee.name }}
						button.member-chip-remove(type="button", :disabled="busy", :aria-label="$t('Unassign')", :title="$t('Unassign')", @click="$emit('unassign', { roleId: role.id, userId: assignee.id })") ✕
					p.text-muted(v-if="!getAssignedList(role).length") {{ $t('No members assigned yet.') }}
				.assign-new.form-group.row
					select.form-control(v-model="selectedMemberId[role.id]")
						option(value="") {{ $t('Select a member') }}
						option(v-for="member in members", :key="member.id", :value="member.id") {{ member.name }}{{ member.email ? ` (${member.email})` : '' }}
					button.assign-btn(type="button", :disabled="busy || !selectedMemberId[role.id]", @click="assign(role)") {{ $t('Assign') }}
		.button-row
			bunt-button#btn-close(type="button", :disabled="busy", @click="cancel") {{ $t('Close') }}
</template>

<script>
import { getLocalizedString } from '../utils'
import { getAssignedList } from './index'

export default {
	name: 'AssignVolunteerDialog',
	emits: ['assign', 'unassign', 'cancel'],
	props: {
		session: { type: Object, default: null },
		members: { type: Array, default: () => [] },
		error: { type: String, default: '' },
		busy: { type: Boolean, default: false },
	},
	data () {
		return {
			getLocalizedString,
			getAssignedList,
			selectedMemberId: {},
		}
	},
	methods: {
		show () {
			this.selectedMemberId = {}
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
		assign (role) {
			const userId = this.selectedMemberId[role.id]
			if (!userId) return
			this.$emit('assign', { roleId: role.id, userId })
		},
	},
}
</script>

<style lang="stylus">
.assign-volunteer-modal
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
	.assign-volunteer-title
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
	.assign-volunteer-error
		display: flex
		align-items: center
		padding: 10px 14px
		margin-bottom: 16px
		background-color: #fdecea
		border: 1px solid #f5c6cb
		border-radius: 4px
		color: #721c24
		font-size: 14px
	.assign-data
		.assign-role
			margin-bottom: 24px
			h4
				font-size: 15px
				font-weight: 600
				margin: 0 0 8px
				color: $clr-grey-700
			.text-muted
				font-size: 13px
				color: $clr-grey-600
				margin: 0
		.assign-new
			align-items: center
			margin-top: 8px
	.member-chip
		display: inline-flex
		align-items: center
		gap: 6px
		background-color: $clr-grey-200
		color: $clr-primary-text-light
		border-radius: 14px
		padding: 4px 6px 4px 12px
		margin: 0 6px 6px 0
		font-size: 13px
		line-height: 1.4
		.member-chip-remove
			display: inline-flex
			align-items: center
			justify-content: center
			width: 18px
			height: 18px
			border: none
			border-radius: 50%
			background: none
			color: $clr-danger
			cursor: pointer
			padding: 0
			font-size: 11px
			&:hover
				background-color: rgba(0, 0, 0, 0.08)
			&:disabled
				opacity: 0.5
				cursor: default
	.assign-new
		display: flex
		gap: 8px
		.form-control
			flex: auto
			font-size: 14px
			border: 1px solid $clr-grey-300
			border-radius: 4px
			padding: 8px 10px
			box-sizing: border-box
	.assign-btn
		flex: none
		min-height: 38px
		padding: 0 16px
		border: none
		border-radius: 4px
		background-color: $clr-primary
		color: $clr-white
		font-weight: bold
		cursor: pointer
		&:hover
			opacity: 0.9
		&:disabled
			opacity: 0.5
			cursor: default
	.button-row
		display: flex
		width: 100%
		margin-top: 8px
		.bunt-button-content
			font-size: 16px
		#btn-close
			margin-left: auto
			button-style(color: $clr-grey-200)
</style>
