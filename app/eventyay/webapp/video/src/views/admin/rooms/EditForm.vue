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
			component.stage-settings(ref="settings", v-if="inferredType && typeComponents[inferredType.id]", :is="typeComponents[inferredType.id]", :config="config", :modules="modules", :creating="creating")
			stream-schedule(ref="streamSchedule", v-if="showStreamSchedule", :room-id="config.id ? String(config.id) : null", :room-name="localizedName", :open-create-on-mount="openStreamScheduleCreateOnMount", @opened-create-on-mount="clearOpenStreamScheduleCreateQuery", @create-requires-room="createRoomForStreamSchedule")
			sidebar-addons(v-if="inferredType && inferredType.id === 'stage'", :config="config", :modules="modules", :creating="creating")
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ creating ? 'create' : 'save' }}
		.errors {{ validationErrors.join(', ') }}
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
import { PLAYBACK_MODE_SCHEDULE_DRIVEN, getStagePlaybackMode } from 'lib/stage-streams'
import Stage from './types-edit/stage'
import PageStatic from './types-edit/page-static'
import PageIframe from './types-edit/page-iframe'
import ChannelBBB from './types-edit/channel-bbb'
import ChannelJanus from './types-edit/channel-janus'
import ChannelZoom from './types-edit/channel-zoom'
import ChannelRoulette from './types-edit/channel-roulette'
import Posters from './types-edit/posters'
import PageLanding from './types-edit/page-landing'
import StreamSchedule from './StreamSchedule'
import SidebarAddons from './types-edit/SidebarAddons'

export default {
	components: { StreamSchedule, SidebarAddons },
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
			}),
			saving: false,
			error: null
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
		roomTypes() {
			return filterRoomTypesByPermission(this.allRoomTypes, this.hasPermission)
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
		stagePlaybackMode() {
			if (!this.modules) return null
			const module = this.modules['livestream.native'] || this.modules['livestream.youtube'] || this.modules['livestream.iframe']
			return getStagePlaybackMode(module)
		},
		showStreamSchedule() {
			return this.inferredType?.id === 'stage' &&
				this.stagePlaybackMode === PLAYBACK_MODE_SCHEDULE_DRIVEN
		},
		openStreamScheduleCreateOnMount() {
			return !this.creating && this.config.id && this.showStreamSchedule && this.$route.query.schedule === 'new'
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
		async save({ openScheduleAfterCreate = false, streamScheduleDraft = null } = {}) {
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
						modules: this.config.module_config
					}))
				}
				const updated = await api.call('room.config.patch', {
					room: roomId,
					name: this.config.name,
					description: this.config.description,
					picture: this.config.picture,
					force_join: this.config.force_join,
					is_unscheduled: this.config.is_unscheduled,
					module_config: this.config.module_config,
				})
				Object.assign(this.config, updated)
				this.saving = false
				if (this.creating) {
					if (streamScheduleDraft) {
						sessionStorage.setItem(`streamScheduleDraft:${roomId}`, JSON.stringify(streamScheduleDraft))
					}
					const query = this.inferredType?.id === 'stage' &&
						this.stagePlaybackMode === PLAYBACK_MODE_SCHEDULE_DRIVEN &&
						openScheduleAfterCreate
						? { schedule: 'new' }
						: undefined
					this.$router.push({name: 'admin:rooms:item', params: {roomId}, query})
				}
			} catch (error) {
				console.error(error)
				this.saving = false
				this.error = error.message || error
			}
		},
		clearOpenStreamScheduleCreateQuery() {
			if (this.$route.query.schedule !== 'new') return
			const query = { ...this.$route.query }
			delete query.schedule
			this.$router.replace({ query })
		},
		createRoomForStreamSchedule(streamScheduleDraft) {
			return this.save({ openScheduleAfterCreate: true, streamScheduleDraft })
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
</style>
