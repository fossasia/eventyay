<template lang="pug">
.c-room-edit-form
	.scroll-wrapper(v-scrollbar.y="")
		.ui-form-body
			.generic-settings
				bunt-input(name="name", v-model="localizedName", label="Name", :validation="v$.config.name")
				bunt-input(name="description", v-model="localizedDescription", label="Description")
				div(:title="config.has_linked_sessions ? \"Room has linked sessions and can't be marked unscheduled\" : ''")
					bunt-checkbox(name="is_unscheduled", v-model="config.is_unscheduled", label="Unscheduled room (hide from schedule/sessions)", :disabled="config.has_linked_sessions")
				template(v-if="inferredType")
					bunt-checkbox(v-if="inferredType.id === 'channel-text'", name="force_join", v-model="config.force_join", label="Force join on login (use for non-volatile, text-based chats only!!)")
			component.stage-settings(ref="settings", v-if="inferredType && typeComponents[inferredType.id]", :is="typeComponents[inferredType.id]", :config="config", :modules="modules", :creating="creating", :room-id="config.id ? String(config.id) : null", :interpretation-admin="interpretationAdmin")
			sidebar-addons(v-if="inferredType && inferredType.id === 'stage'", :config="config", :modules="modules", :creating="creating")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error="!!error") {{ creating ? 'create' : 'save' }}
		.errors {{ error || validationErrors.join(', ') }}
</template>
<script>
import { markRaw } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import api from 'lib/api'
import { required } from 'lib/validators'
import ValidationErrorsMixin from 'components/mixins/validation-errors'
import ROOM_TYPES, { inferType } from 'lib/room-types'
import { filterRoomTypesByPermission } from 'lib/room-type-permissions'
import Stage from './types-edit/stage'
import ChannelBBB from './types-edit/channel-bbb'
import ChannelJanus from './types-edit/channel-janus'
import ChannelJitsi from './types-edit/channel-jitsi'
import ChannelZoom from './types-edit/channel-zoom'
import ChannelRoulette from './types-edit/channel-roulette'
import Posters from './types-edit/posters'
import PageLanding from './types-edit/page-landing'
import SidebarAddons from './types-edit/SidebarAddons'
import {
	cloneLanguageStreamEntries,
	fetchInterpretationLanguageStreams,
	saveInterpretationLanguageStreams,
} from 'lib/interpretation-language-streams'

export default {
	components: { SidebarAddons },
	mixins: [ValidationErrorsMixin],
	provide() {
		return {
			interpretationAdmin: this.interpretationAdmin,
		}
	},
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
			allRoomTypes: ROOM_TYPES,
			typeComponents: markRaw({
				stage: Stage,
				'page-landing': PageLanding,
				'channel-bbb': ChannelBBB,
				'channel-roulette': ChannelRoulette,
				'channel-janus': ChannelJanus,
				'channel-jitsi': ChannelJitsi,
				'channel-zoom': ChannelZoom,
				posters: Posters
			}),
			saving: false,
			error: null,
			interpretationAdmin: {
				usePluginStreams: false,
				languageStreams: [],
				loaded: false,
				streamsLoadFailed: false,
			},
		}
	},
	async created() {
		await this.loadInterpretationLanguageStreams()
	},
	computed: {
		...mapGetters(['hasPermission', 'isAdminMode']),
		roomTypes() {
			return filterRoomTypesByPermission(this.allRoomTypes, this.hasPermission, this.isAdminMode)
		},
		modules() {
			return this.config?.module_config.reduce((acc, module) => {
				acc[module.type] = module
				return acc
			}, {})
		},
		inferredType() {
			return inferType(this.config)
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
		return {
			config: {
				name: {
					required: required('name is required')
				},
			},
		}
	},
	methods: {
		async loadInterpretationLanguageStreams() {
			if (this.creating || !this.config?.id) return
			this.interpretationAdmin.streamsLoadFailed = false
			try {
				const data = await fetchInterpretationLanguageStreams(
					this.$store,
					this.config.id
				)
				this.interpretationAdmin.usePluginStreams = Boolean(
					data.use_plugin_language_streams
				)
				this.config.interpretation_use_plugin_streams = this.interpretationAdmin.usePluginStreams
				if (this.interpretationAdmin.usePluginStreams) {
					this.interpretationAdmin.languageStreams = cloneLanguageStreamEntries(
						data.language_streams
					)
				}
			} catch (error) {
				console.warn('interpretation language streams unavailable', error)
				this.interpretationAdmin.streamsLoadFailed = true
				this.interpretationAdmin.usePluginStreams = Boolean(
					this.config.interpretation_use_plugin_streams
				)
				this.interpretationAdmin.languageStreams = []
			} finally {
				this.interpretationAdmin.loaded = true
			}
		},
		async save() {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return
			const isStage = this.inferredType?.id === 'stage'
			if (isStage && !this.$refs.settings?.validate()) return
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
				const pendingModuleConfig = this.config.module_config
				const roomPatch = {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					picture: this.config.picture,
					force_join: this.config.force_join,
					is_unscheduled: this.config.is_unscheduled,
				}
				if (!isStage) roomPatch.module_config = this.config.module_config
				const updated = await api.call('room.config.patch', roomPatch)
				Object.assign(this.config, updated)
				if (isStage) {
					this.config.module_config = pendingModuleConfig
					await this.$refs.settings.saveStreamConfiguration(roomId)
				}
				if (
					this.interpretationAdmin.usePluginStreams &&
					roomId &&
					this.interpretationAdmin.loaded &&
					!this.interpretationAdmin.streamsLoadFailed
				) {
					await saveInterpretationLanguageStreams(
						this.$store,
						roomId,
						this.interpretationAdmin.languageStreams
					)
				}
				this.saving = false
				if (this.creating) {
					this.$router.push({name: 'admin:rooms:item', params: {roomId}})
				}
			} catch (error) {
				console.error(error)
				this.saving = false
				this.error = error.message || error
			}
		},
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
</style>
