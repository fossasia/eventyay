<template lang="pug">
.c-room-edit-form
	.scroll-wrapper(v-scrollbar.y="")
		.ui-form-body
			.type-selection(v-if="needsTypeSelection")
				h2 Complete Room Setup
				p Select a room type to unlock the full configuration options.
				.types
					button.type-option(
						v-for="type in roomTypes",
						:key="type.id",
						type="button",
						:class="{selected: selectedTypeId === type.id}",
						@click="selectType(type.id)"
					)
						.icon(:class="[`mdi`, `mdi-${type.icon}`]")
						.text
							.name {{ type.name }}
							.description {{ type.description }}
			.generic-settings
				bunt-input(name="name", v-model="localizedName", label="Name", :validation="v$.config.name")
				bunt-input(name="description", v-model="localizedDescription", label="Description")
				bunt-input(name="sorting_priority", v-model="config.sorting_priority", label="Sorting priority", :validation="v$.config.sorting_priority")
				template(v-if="inferredType")
					bunt-input(v-if="inferredType.id === 'stage' || inferredType.id === 'channel-bbb'", name="pretalx_id", v-model="config.pretalx_id", label="pretalx ID", :validation="v$.config.pretalx_id")
					bunt-checkbox(v-if="inferredType.id === 'channel-text'", name="force_join", v-model="config.force_join", label="Force join on login (use for non-volatile, text-based chats only!!)")
				.visibility-controls
					h3 Visibility
					bunt-checkbox(name="hidden", v-model="config.hidden", class="visibility-option") Hide this room from schedule-editor
					template(v-if="config.setup_complete")
						bunt-checkbox(
							name="sidebar_hidden",
							v-model="config.sidebar_hidden",
							class="visibility-option"
						) Hide from Sidebar
					template(v-else)
						small Hidden from the sidebar until setup is complete.
			template(v-if="inferredType && typeComponents[inferredType.id]")
				.video-settings(v-if="showVideoSettingsTitle")
					h3 Video Settings
					component.stage-settings(ref="settings", :is="typeComponents[inferredType.id]", :config="config", :modules="modules")
				component.stage-settings(v-else, ref="settings", :is="typeComponents[inferredType.id]", :config="config", :modules="modules")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ creating ? 'create' : 'save' }}
		.errors {{ validationErrors.join(', ') }}
</template>
<script>
import { markRaw } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import api from 'lib/api'
import Prompt from 'components/Prompt'
import { required, integer } from 'lib/validators'
import ValidationErrorsMixin from 'components/mixins/validation-errors'
import { inferType } from 'lib/room-types'
import ROOM_TYPES from 'lib/room-types'
import Stage from './types-edit/stage'
import PageStatic from './types-edit/page-static'
import PageIframe from './types-edit/page-iframe'
import ChannelBBB from './types-edit/channel-bbb'
import ChannelJanus from './types-edit/channel-janus'
import ChannelZoom from './types-edit/channel-zoom'
import ChannelRoulette from './types-edit/channel-roulette'
import Posters from './types-edit/posters'
import PageLanding from './types-edit/page-landing'

export default {
	components: { Prompt },
	mixins: [ValidationErrorsMixin],
	props: {
		config: {
			type: Object,
			required: true
		},
		creating: {
			type: Boolean,
			default: false
		}
	},
	setup:() => ({v$:useVuelidate()}),
	data() {
		return {
			roomTypes: ROOM_TYPES,
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
			}),
			saving: false,
			error: null,
			selectedTypeId: null
		}
	},
	watch: {
		config: {
			immediate: true,
			handler(config) {
				if (!config) return
				this.applyVisibilityDefaults(config)
				this.syncSidebarHidden()
			}
		},
		inferredType(newType) {
			this.selectedTypeId = newType?.id || null
		}
	},
	computed: {
		modules() {
			const module_config = Array.isArray(this.config?.module_config) ? this.config.module_config : []
			return module_config.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		inferredType() {
			return inferType(this.config)
		},
		needsTypeSelection() {
			return !this.inferredType
		},
		showVideoSettingsTitle() {
			const videoTypes = ['stage', 'channel-bbb', 'channel-janus', 'channel-zoom', 'channel-roulette']
			return videoTypes.includes(this.inferredType?.id)
		},
		localizedName: {
			get() {
				return this.$localize(this.config.name)
			},
			set(value) {
				this.config.name = value
			}
		},
		localizedDescription: {
			get() {
				return this.$localize(this.config.description)
			},
			set(value) {
				this.config.description = value
			}
		}
	},
	validations() {
		const config = {
			name: {
				required: required('name is required')
			},
			sorting_priority: {
				integer: integer('sorting priority must be a number')
			},
			pretalx_id: {
				integer: integer('pretalx id must be a number')
			},
		}

		if (!this.creating) config.sorting_priority.required = required('sorting priority is required')

		return { config }
	},
	methods: {
		applyVisibilityDefaults(config) {
			if (config.hidden == null) config.hidden = false
			if (config.sidebar_hidden == null) {
				config.sidebar_hidden = !config.setup_complete
			}
		},
		syncSidebarHidden() {
			if (!this.config) return
			if (!this.config.setup_complete && !this.config.sidebar_hidden) {
				this.config.sidebar_hidden = true
			}
		},
		selectType(typeId) {
			const type = this.roomTypes.find(t => t.id === typeId)
			if (!type) return
			this.selectedTypeId = typeId
			this.config.module_config = [{
				type: type.startingModule,
				config: {}
			}]
		},
		async save() {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return
			this.$refs.settings?.beforeSave?.()
			this.saving = true
			try {
				let roomId = this.config.id
				if (this.creating) {
					({ room: roomId } = await this.$store.dispatch('createRoom', {
						name: this.config.name,
						description: this.config.description,
						modules: []
					}))
				}
				const module_config = Array.isArray(this.config.module_config) ? this.config.module_config : []
				const setup_complete = module_config.length > 0
				let sidebar_hidden
				if (setup_complete && !this.config.setup_complete) {
					// Setup just completed, show in sidebar
					sidebar_hidden = false
				} else if (setup_complete) {
					// Setup was already complete, preserve user preference
					sidebar_hidden = this.config.sidebar_hidden
				} else {
					// Setup incomplete, hide from sidebar
					sidebar_hidden = true
				}
				const roomData = {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					sorting_priority: this.config.sorting_priority === '' ? undefined : this.config.sorting_priority,
					pretalx_id: this.config.pretalx_id || 0, // TODO weird default
					picture: this.config.picture,
					force_join: this.config.force_join,
					hidden: !!this.config.hidden,
					sidebar_hidden,
					setup_complete,
					module_config,
				}
				const updatedConfig = await api.call('room.config.patch', roomData)
				Object.assign(this.config, updatedConfig)
				this.saving = false
				if (this.creating) {
					this.$router.push({name: 'admin:rooms:item', params: {roomId}})
				}
			} catch (error) {
				console.error(error)
				this.saving = false
				this.error = error.message || error
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room-edit-form
	flex: auto
	min-height: 0
	height: 100vh
	display: flex
	flex-direction: column
	.scroll-wrapper
		flex: auto
		min-height: 0
		display: flex
		flex-direction: column
	.type-selection
		margin-bottom: 24px
		.types
			display: grid
			grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))
			gap: 12px
			margin-top: 12px
		.type-option
			display: flex
			flex-direction: column
			align-items: flex-start
			border: border-separator()
			border-radius: 6px
			padding: 12px
			text-align: left
			cursor: pointer
			transition: border-color .2s, box-shadow .2s
			background-color: $clr-white
			&:hover, &.selected
				border-color: $clr-primary
				box-shadow: 0 0 0 1px $clr-primary inset
			.icon
				font-size: 24px
				margin-bottom: 8px
			.name
				font-weight: 600
				margin-bottom: 4px
			.description
				color: $clr-secondary-text-light
				font-size: 13px
	.generic-settings
		display: flex
		flex-direction: column
		gap: 16px
	.visibility-controls
		h3
			margin: 24px 0 8px
		small
			color: $clr-secondary-text-light
	.visibility-option
		margin-bottom: 6px
.video-settings
	margin-top: 24px
	h3
		margin-bottom: 8px
	.bunt-checkbox
		margin-bottom: 6px
</style>
