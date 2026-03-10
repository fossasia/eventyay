<template lang="pug">
prompt.c-room-edit-prompt(@close="$emit('close')")
	.content
		.prompt-header
			h2 Edit Room
		bunt-progress-circular(v-if="loading", size="large")
		.error(v-else-if="error")
			p {{ error }}
			bunt-button(@click="fetchConfig") Retry
		template(v-else-if="config")
			.edit-body(v-scrollbar.y="")
				.type-section
					h3 Room Type
					.current-type(v-if="inferredType")
						.mdi(:class="[`mdi-${inferredType.icon}`]")
						span {{ inferredType.name }}
					.type-picker
						.type-option(
							v-for="type of availableRoomTypes",
							:key="type.id",
							:class="{active: inferredType && inferredType.id === type.id}",
							@click="changeType(type)"
						)
							.icon.mdi(:class="[`mdi-${type.icon}`]")
							.text
								.name {{ type.name }}
								.description {{ type.description }}
				.generic-settings
					bunt-input(name="name", v-model="localizedName", label="Name")
					bunt-input(name="description", v-model="localizedDescription", label="Description")
				component.type-settings(
					ref="settings",
					v-if="inferredType && typeComponents[inferredType.id]",
					:is="typeComponents[inferredType.id]",
					:config="config",
					:modules="modules"
				)
			.edit-actions
				bunt-button.btn-cancel(@click="$emit('close')") Cancel
				bunt-button.btn-save(@click="save", :loading="saving", :error-message="saveError") Save
</template>
<script>
import { markRaw } from 'vue'
import { mapGetters } from 'vuex'
import api from 'lib/api'
import Prompt from 'components/Prompt'
import ROOM_TYPES, { inferType } from 'lib/room-types'
import { filterRoomTypesByPermission } from 'lib/room-type-permissions'
import Stage from 'views/admin/rooms/types-edit/stage'
import PageStatic from 'views/admin/rooms/types-edit/page-static'
import PageIframe from 'views/admin/rooms/types-edit/page-iframe'
import ChannelBBB from 'views/admin/rooms/types-edit/channel-bbb'
import ChannelJanus from 'views/admin/rooms/types-edit/channel-janus'
import ChannelZoom from 'views/admin/rooms/types-edit/channel-zoom'
import ChannelRoulette from 'views/admin/rooms/types-edit/channel-roulette'
import Posters from 'views/admin/rooms/types-edit/posters'
import PageLanding from 'views/admin/rooms/types-edit/page-landing'

export default {
	components: { Prompt },
	props: {
		room: {
			type: Object,
			required: true
		}
	},
	emits: ['close'],
	data () {
		return {
			loading: true,
			error: null,
			config: null,
			saving: false,
			saveError: null,
			allRoomTypes: ROOM_TYPES,
			typeComponents: markRaw({
				stage: Stage,
				'page-static': PageStatic,
				'page-iframe': PageIframe,
				'page-landing': PageLanding,
				'channel-bbb': ChannelBBB,
				'channel-roulette': ChannelRoulette,
				'channel-janus': ChannelJanus,
				'channel-zoom': ChannelZoom,
				posters: Posters
			})
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		availableRoomTypes () {
			return filterRoomTypesByPermission(this.allRoomTypes, this.hasPermission)
		},
		modules () {
			if (!this.config) return {}
			return this.config.module_config.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		inferredType () {
			if (!this.config) return null
			return inferType(this.config)
		},
		localizedName: {
			get () {
				return this.$localize(this.config.name)
			},
			set (value) {
				this.config.name = value
			}
		},
		localizedDescription: {
			get () {
				return this.$localize(this.config.description)
			},
			set (value) {
				this.config.description = value
			}
		}
	},
	async created () {
		await this.fetchConfig()
	},
	methods: {
		async fetchConfig () {
			this.loading = true
			this.error = null
			try {
				this.config = await api.call('room.config.get', { room: this.room.id })
			} catch (err) {
				this.error = err.code === 'protocol.denied'
					? 'You do not have permission to edit this room.'
					: (err.message || String(err))
			} finally {
				this.loading = false
			}
		},
		changeType (type) {
			if (this.inferredType && this.inferredType.id === type.id) return
			this.config.module_config = [{ type: type.startingModule, config: {} }]
		},
		async save () {
			this.saveError = null
			this.$refs.settings?.beforeSave?.()
			this.saving = true
			try {
				await api.call('room.config.patch', {
					room: this.config.id,
					name: this.config.name,
					description: this.config.description,
					sorting_priority: this.config.sorting_priority,
					pretalx_id: this.config.pretalx_id || 0,
					picture: this.config.picture,
					force_join: this.config.force_join,
					module_config: this.config.module_config
				})
				this.saving = false
				this.$emit('close')
			} catch (err) {
				this.saving = false
				this.saveError = err.message || String(err)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room-edit-prompt
	.prompt-wrapper
		width: 640px
		max-width: 90vw
		max-height: 85vh
		display: flex
		flex-direction: column
	.content
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
	.prompt-header
		padding: 16px 16px 0
		h2
			margin: 0
			font-size: 20px
			font-weight: 600
	.edit-body
		flex: auto
		min-height: 0
		padding: 16px
		display: flex
		flex-direction: column
		gap: 16px
	.type-section
		h3
			margin: 0 0 8px
			font-size: 16px
			font-weight: 500
		.current-type
			display: flex
			align-items: center
			gap: 8px
			margin-bottom: 12px
			font-size: 14px
			color: $clr-secondary-text-light
			.mdi
				font-size: 20px
	.type-picker
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		.type-option
			display: flex
			align-items: center
			padding: 8px 12px
			cursor: pointer
			transition: background-color 0.15s
			&:not(:last-child)
				border-bottom: border-separator()
			&:hover
				background-color: $clr-grey-50
			&.active
				background-color: var(--clr-primary-light, $clr-blue-50)
				border-left: 3px solid var(--clr-primary)
				padding-left: 9px
			.icon
				font-size: 24px
				margin-right: 10px
				flex: none
			.text
				display: flex
				flex-direction: column
			.name
				font-size: 14px
				line-height: 20px
				font-weight: 500
			.description
				font-size: 12px
				color: $clr-secondary-text-light
				line-height: 16px
	.generic-settings
		display: flex
		flex-direction: column
		gap: 8px
	.type-settings
		margin-top: 8px
	.edit-actions
		display: flex
		justify-content: flex-end
		gap: 8px
		padding: 12px 16px
		border-top: border-separator()
		.btn-cancel
			themed-button-secondary()
		.btn-save
			themed-button-primary()
</style>
