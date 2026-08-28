<template lang="pug">
.c-stage-settings
	.stream-section-header
		.header-info
			h2 {{ $t('Stream schedule') }}
			p.subtitle {{ $t('Configure the streams and fallback player for this stage.') }}
		.header-actions
			.btn-add-scheduled-group
				bunt-button.btn-add-scheduled(@click="addScheduledStream")
					i.mdi.mdi-plus(aria-hidden="true")
					span {{ $t('Add scheduled streams') }}
				.info-tooltip-wrapper(
					tabindex="0"
					role="button"
					:aria-label="$t('Adding several streams requires a stream schedule.')"
					v-tooltip="{text: $t('Adding several streams requires a stream schedule.'), placement: 'bottom-end', fixed: true}"
				)
					i.mdi.mdi-information-outline(aria-hidden="true")

	.loading-container(v-if="loading")
		bunt-progress-circular(size="large")

	.streams-container(v-else)
		.streams-list
			.stream-card(
				v-for="(stream, index) in streams"
				:key="stream.uid"
				:data-stream-id="stream.id"
			)
				.stream-card-header
					.header-left
						span.drag-handle(v-if="streams.length > 1", title="Drag to reorder") :::
						span.stream-title {{ $t('Stream') }} {{ index + 1 }}
					button.btn-delete-stream(
						v-if="streams.length > 1 || isScheduledMode"
						type="button"
						@click="confirmDeleteStream(index)"
						:title="$t('Delete stream')"
						:aria-label="$t('Delete stream')"
					)
						i.mdi.mdi-trash-can-outline(aria-hidden="true")

				.fields-grid
					.field-group
						label.field-label
							| {{ $t('Stream type / provider') }}
							span.required-star *
						.custom-provider-select
							.provider-icon-badge
								i.mdi(:class="providerIcon(stream.stream_type)" aria-hidden="true")
							select.provider-select(v-model="stream.stream_type" @change="onStreamTypeChange(stream)")
								option(value="youtube") YouTube
								option(value="hls") HLS
							i.mdi.mdi-chevron-down.dropdown-arrow(aria-hidden="true")

					.field-group
						label.field-label
							| {{ streamUrlLabel(stream.stream_type) }}
							span.required-star *
						.input-wrapper
							input.text-input(
								type="text"
								v-model="stream.url"
								:placeholder="streamUrlPlaceholder(stream.stream_type)"
								:class="{'has-error': getStreamError(index, 'url')}"
								@blur="onStreamUrlBlur(stream)"
							)
						.field-error(v-if="getStreamError(index, 'url')")
							| {{ getStreamError(index, 'url') }}

				.fields-grid.datetime-grid(v-if="isScheduledMode")
					.field-group
						label.field-label
							| {{ $t('Start date & time') }} ({{ eventTimezone }})
							span.required-star *
						.input-wrapper.datetime-wrapper
							input.datetime-input(
								type="datetime-local"
								v-model="stream.plainStartTime"
								:class="{'has-error': getStreamError(index, 'start_time')}"
							)
						.field-error(v-if="getStreamError(index, 'start_time')")
							| {{ getStreamError(index, 'start_time') }}

					.field-group
						label.field-label
							| {{ $t('End date & time') }} ({{ eventTimezone }})
							span.required-star *
						.input-wrapper.datetime-wrapper
							input.datetime-input(
								type="datetime-local"
								v-model="stream.plainEndTime"
								:class="{'has-error': getStreamError(index, 'end_time')}"
							)
						.field-error(v-if="getStreamError(index, 'end_time')")
							| {{ getStreamError(index, 'end_time') }}

					.timezone-hint
						i.mdi.mdi-clock-outline(aria-hidden="true")
						| {{ $t('All times shown in the event timezone') }} ({{ eventTimezone }}).

				.single-stream-scheduled-hint(v-if="streams.length === 1 && isScheduledMode")
					span {{ $t('This stage has a scheduled time window.') }}
					button.btn-clear-times(type="button" @click="clearScheduleTimes(stream)")
						| {{ $t('Clear times to make this an always-on stream') }}

				.stream-playback-settings
					button.accordion-header.sub-accordion(
						type="button"
						@click="stream.showAdvanced = !stream.showAdvanced"
						:aria-expanded="String(stream.showAdvanced)"
					)
						span.accordion-title {{ $t('Playback settings') }}
						i.mdi(:class="stream.showAdvanced ? 'mdi-chevron-up' : 'mdi-chevron-down'" aria-hidden="true")
					.advanced-switches(v-if="stream.showAdvanced")
						bunt-switch(name="startMuted", v-model="stream.config.startMuted", :label="$t('Start muted')")
						template(v-if="stream.stream_type === 'youtube'")
							bunt-switch(name="enablePrivacyEnhancedMode", v-model="stream.config.enablePrivacyEnhancedMode", :label="$t('Enable No-Cookies')")
							bunt-switch(name="loop", v-model="stream.config.loop", :label="$t('Loop')")
							bunt-switch(name="modestBranding", v-model="stream.config.modestBranding", :label="$t('Enable Modest Branding')")
							bunt-switch(name="hideControls", v-model="stream.config.hideControls", :label="$t('Hide Controls')", :hint="$t('Note: Hiding controls disables autoplay so the stream can start with sound when the viewer clicks play.')")
							bunt-switch(name="noRelated", v-model="stream.config.noRelated", :label="$t('Limit related videos to same channel')")
							bunt-switch(name="disableKb", v-model="stream.config.disableKb", :label="$t('Disable Keyboard Controls')")
							bunt-switch(name="showInfo", v-model="stream.config.showInfo", :label="$t('Hide Video Info')")

		.scheduled-actions-footer(v-if="isScheduledMode")
			bunt-button.btn-add-another(@click="addScheduledStream")
				i.mdi.mdi-plus(aria-hidden="true")
				span {{ $t('Add scheduled streams') }}

		.interpretation-plugin-language-streams(v-if="roomId && showPluginLanguageStreams")
			LanguageAudioSourceList(
				:title="$t('Interpretation source')"
				:entries="pluginLanguageStreamEntries"
			)

		.global-stream-error(v-if="globalError")
			| {{ globalError }}

	transition(name="prompt")
		prompt.c-delete-confirm-prompt(v-if="deletingStreamIndex !== null", @close="deletingStreamIndex = null")
			.content
				h2 {{ $t('Delete Stream') }}
				p {{ $t('Are you sure you want to delete Stream') }} {{ deletingStreamIndex + 1 }}?
				.prompt-actions
					bunt-button.btn-danger(@click="executeDeleteStream") {{ $t('Delete') }}
					bunt-button.btn-cancel(@click="deletingStreamIndex = null") {{ $t('Cancel') }}
</template>
<script>
import { defineComponent, reactive } from 'vue'
import moment from 'moment-timezone'
import api from 'lib/api'
import Prompt from 'components/Prompt'
import LanguageAudioSourceList from 'components/LanguageAudioSourceList'
import mixin from './mixin'
import { normalizeYoutubeVideoId } from 'lib/validators'
import {
	PLAYBACK_MODE_ALWAYS_ON,
	PLAYBACK_MODE_SCHEDULE_DRIVEN,
	STREAM_TYPE_HLS,
	STREAM_TYPE_YOUTUBE,
	createDefaultStream,
	inferPlaybackModeFromStreams,
} from 'lib/stage-streams'

export default defineComponent({
	name: 'StageSettings',
	components: { Prompt, LanguageAudioSourceList },
	mixins: [mixin],
	inject: {
		interpretationAdmin: { default: null },
	},
	data() {
		return {
			streams: [],
			deletedScheduleIds: [],
			loading: false,
			globalError: null,
			validationErrors: {},
			deletingStreamIndex: null,
		}
	},
	computed: {
		roomId() {
			return this.config?.id ? String(this.config.id) : null
		},
		eventTimezone() {
			return this.$store.state.world?.timezone || this.$store.state.userTimezone || moment.tz.guess() || 'UTC'
		},
		isScheduledMode() {
			return inferPlaybackModeFromStreams(this.streams) === PLAYBACK_MODE_SCHEDULE_DRIVEN
		},
		showPluginLanguageStreams() {
			return Boolean(this.config?.interpretation_use_plugin_streams)
		},
		pluginLanguageStreamEntries() {
			return this.interpretationAdmin?.languageStreams ?? []
		},
	},
	created() {
		this.initStreams()
	},
	methods: {
		providerIcon(streamType) {
			if (streamType === STREAM_TYPE_YOUTUBE) return 'mdi-youtube'
			return 'mdi-video-outline'
		},
		streamUrlLabel(streamType) {
			if (streamType === STREAM_TYPE_YOUTUBE) {
				return this.$t('Stream URL / Input (YouTube ID or URL)')
			}
			return this.$t('Stream URL / Input (HLS URL)')
		},
		streamUrlPlaceholder(streamType) {
			if (streamType === STREAM_TYPE_YOUTUBE) {
				return 'https://youtube.com/watch?v=...'
			}
			return 'https://stream.example.com/live/stream.m3u8'
		},
		getStreamError(index, field) {
			return this.validationErrors[`${index}.${field}`] || null
		},
		createStreamItem({
			id = null,
			stream_type = STREAM_TYPE_YOUTUBE,
			url = '',
			start_time = null,
			end_time = null,
			config = {},
		} = {}) {
			const self = this
			const stream = reactive({
				...createDefaultStream(stream_type),
				id,
				stream_type,
				url,
				start_time: start_time ? this.parseDateTime(start_time) : null,
				end_time: end_time ? this.parseDateTime(end_time) : null,
				config: {
					enablePrivacyEnhancedMode: !!config.enablePrivacyEnhancedMode,
					loop: !!config.loop,
					modestBranding: !!config.modestBranding,
					startMuted: !!config.startMuted,
					hideControls: !!config.hideControls,
					noRelated: !!config.noRelated,
					disableKb: !!config.disableKb,
					showInfo: !!config.showInfo,
				},
				showAdvanced: false,
			})

			Object.defineProperty(stream, 'plainStartTime', {
				get() {
					if (!stream.start_time) return ''
					const tz = self.eventTimezone || 'UTC'
					return moment.tz(stream.start_time, tz).format('YYYY-MM-DDTHH:mm')
				},
				set(val) {
					if (!val) {
						stream.start_time = null
						return
					}
					const tz = self.eventTimezone || 'UTC'
					stream.start_time = moment.tz(val, tz)
				},
			})

			Object.defineProperty(stream, 'plainEndTime', {
				get() {
					if (!stream.end_time) return ''
					const tz = self.eventTimezone || 'UTC'
					return moment.tz(stream.end_time, tz).format('YYYY-MM-DDTHH:mm')
				},
				set(val) {
					if (!val) {
						stream.end_time = null
						return
					}
					const tz = self.eventTimezone || 'UTC'
					stream.end_time = moment.tz(val, tz)
				},
			})

			return stream
		},
		async initStreams() {
			if (!this.roomId) {
				this.loadFromModuleConfig()
				return
			}
			this.loading = true
			this.globalError = null
			try {
				const schedules = await this.fetchStreamSchedules()
				if (schedules && schedules.length > 0) {
					this.streams = schedules.map(s =>
						this.createStreamItem({
							id: s.id,
							stream_type: s.stream_type,
							url: s.url,
							start_time: s.start_time,
							end_time: s.end_time,
							config: s.config || {},
						})
					)
				} else {
					this.loadFromModuleConfig()
				}
			} catch (err) {
				console.warn('Failed to load stream schedules, falling back to module config:', err)
				this.loadFromModuleConfig()
			} finally {
				this.loading = false
			}
		},
		loadFromModuleConfig() {
			const ytModule = this.modules['livestream.youtube']
			const nativeModule = this.modules['livestream.native']

			if (ytModule?.config?.ytid) {
				this.streams = [
					this.createStreamItem({
						stream_type: STREAM_TYPE_YOUTUBE,
						url: ytModule.config.ytid,
						config: {
							enablePrivacyEnhancedMode: ytModule.config.enablePrivacyEnhancedMode,
							loop: ytModule.config.loop,
							modestBranding: ytModule.config.modestBranding,
							startMuted: ytModule.config.startMuted,
							hideControls: ytModule.config.hideControls,
							noRelated: ytModule.config.noRelated,
							disableKb: ytModule.config.disableKb,
							showInfo: ytModule.config.showInfo,
						},
					}),
				]
			} else if (nativeModule?.config?.hls_url) {
				this.streams = [
					this.createStreamItem({
						stream_type: STREAM_TYPE_HLS,
						url: nativeModule.config.hls_url,
						config: {
							startMuted: nativeModule.config.startMuted,
						},
					}),
				]
			} else {
				this.streams = [this.createStreamItem({ stream_type: STREAM_TYPE_YOUTUBE, url: '' })]
			}
		},
		getApiBaseUrl(targetRoomId = this.roomId) {
			const world = this.$store.state.world
			let organizer = world?.organizer_slug
			let event = world?.slug || world?.id
			if (!organizer || organizer === 'default') {
				const pathParts = window.location.pathname.split('/').filter(Boolean)
				if (pathParts.length >= 2) {
					organizer = pathParts[0]
					event = pathParts[1]
				}
			}
			return `/api/v1/organizers/${organizer}/events/${event}/rooms/${targetRoomId}/stream-schedules/`
		},
		getCsrfToken() {
			const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
			return match ? match[1] : null
		},
		async fetchStreamSchedules() {
			if (!this.roomId) return []
			const url = this.getApiBaseUrl()
			const authHeader = api._config.token
				? `Bearer ${api._config.token}`
				: api._config.clientId
				? `Client ${api._config.clientId}`
				: null
			const headers = { Accept: 'application/json' }
			if (authHeader) headers.Authorization = authHeader

			const response = await fetch(url, { headers, credentials: 'include' })
			if (response.status === 404) return []
			if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`)
			const data = await response.json()
			return Array.isArray(data) ? data : data.results || []
		},
		addScheduledStream() {
			const tz = this.eventTimezone || 'UTC'
			if (this.streams.length === 1 && !this.isScheduledMode) {
				if (!this.streams[0].start_time) {
					this.streams[0].start_time = moment().tz(tz).startOf('hour')
				}
				if (!this.streams[0].end_time) {
					this.streams[0].end_time = moment(this.streams[0].start_time).add(2, 'hours')
				}
			}
			const lastStream = this.streams[this.streams.length - 1]
			const baseStart = lastStream?.end_time
				? moment(lastStream.end_time)
				: moment().tz(tz).startOf('hour')
			const baseEnd = moment(baseStart).add(2, 'hours')

			this.streams.push(
				this.createStreamItem({
					stream_type: STREAM_TYPE_YOUTUBE,
					url: '',
					start_time: baseStart,
					end_time: baseEnd,
				})
			)
		},
		confirmDeleteStream(index) {
			this.deletingStreamIndex = index
		},
		executeDeleteStream() {
			if (this.deletingStreamIndex === null) return
			const index = this.deletingStreamIndex
			const removed = this.streams.splice(index, 1)[0]
			if (removed?.id) {
				this.deletedScheduleIds.push(removed.id)
			}
			this.deletingStreamIndex = null

			if (this.streams.length === 0) {
				this.streams.push(this.createStreamItem({ stream_type: STREAM_TYPE_YOUTUBE, url: '' }))
			}
		},
		clearScheduleTimes(stream) {
			stream.start_time = null
			stream.end_time = null
		},
		onStreamTypeChange(stream) {
			// Clear URL when switching provider if incompatible
			if (stream.stream_type === STREAM_TYPE_YOUTUBE && stream.url.includes('.m3u8')) {
				stream.url = ''
			} else if (stream.stream_type === STREAM_TYPE_HLS && (stream.url.includes('youtube') || stream.url.includes('youtu.be'))) {
				stream.url = ''
			}
		},
		onStreamUrlBlur(stream) {
			if (!stream.url) return
			if (stream.stream_type === STREAM_TYPE_YOUTUBE) {
				const id = normalizeYoutubeVideoId(stream.url)
				if (id && !stream.url.startsWith('http')) {
					stream.url = `https://www.youtube.com/watch?v=${id}`
				}
			}
		},
		parseDateTime(datetime) {
			if (!datetime) return null
			if (moment.isMoment(datetime)) return datetime.clone()
			if (datetime instanceof Date) return moment(datetime)
			const val = String(datetime)
			const hasTz = /([zZ]|[+-]\d\d:?\d\d)$/.test(val)
			return hasTz ? moment.parseZone(val) : moment.utc(val)
		},
		validate() {
			this.validationErrors = {}
			this.globalError = null
			let isValid = true

			this.streams.forEach((stream, index) => {
				if (!stream.url || !stream.url.trim()) {
					this.validationErrors[`${index}.url`] = this.$t('Stream URL is required')
					isValid = false
				} else if (stream.stream_type === STREAM_TYPE_YOUTUBE && !normalizeYoutubeVideoId(stream.url)) {
					this.validationErrors[`${index}.url`] = this.$t('Invalid YouTube URL or Video ID')
					isValid = false
				}

				if (this.isScheduledMode) {
					if (!stream.start_time) {
						this.validationErrors[`${index}.start_time`] = this.$t('Start time is required')
						isValid = false
					}
					if (!stream.end_time) {
						this.validationErrors[`${index}.end_time`] = this.$t('End time is required')
						isValid = false
					}
					if (stream.start_time && stream.end_time && !stream.end_time.isAfter(stream.start_time)) {
						this.validationErrors[`${index}.end_time`] = this.$t('End time must be after start time')
						isValid = false
					}
				}
			})

			// Check for schedule overlaps in scheduled mode
			if (this.isScheduledMode && isValid) {
				for (let i = 0; i < this.streams.length; i++) {
					for (let j = i + 1; j < this.streams.length; j++) {
						const a = this.streams[i]
						const b = this.streams[j]
						if (a.start_time && a.end_time && b.start_time && b.end_time) {
							if (a.start_time.isBefore(b.end_time) && a.end_time.isAfter(b.start_time)) {
								this.globalError = this.$t(
									'Stream {first} overlaps with Stream {second}. Please ensure schedule times do not overlap.',
									{ first: i + 1, second: j + 1 }
								)
								isValid = false
								break
							}
						}
					}
					if (!isValid) break
				}
			}

			return isValid
		},
		beforeSave() {
			if (!this.config.module_config) {
				this.config.module_config = []
			}
			// Remove any existing livestream modules
			this.config.module_config = this.config.module_config.filter(
				m => m.type !== 'livestream.native' && m.type !== 'livestream.youtube'
			)

			if (!this.isScheduledMode && this.streams.length > 0) {
				const primary = this.streams[0]
				if (primary.stream_type === STREAM_TYPE_YOUTUBE) {
					const ytid = normalizeYoutubeVideoId(primary.url) || primary.url
					const config = {
						playback_mode: PLAYBACK_MODE_ALWAYS_ON,
						ytid,
					}
					if (primary.config.enablePrivacyEnhancedMode) config.enablePrivacyEnhancedMode = true
					if (primary.config.loop) config.loop = true
					if (primary.config.modestBranding) config.modestBranding = true
					if (primary.config.startMuted) config.startMuted = true
					if (primary.config.hideControls) config.hideControls = true
					if (primary.config.noRelated) config.noRelated = true
					if (primary.config.disableKb) config.disableKb = true
					if (primary.config.showInfo) config.showInfo = true

					this.config.module_config.push({
						type: 'livestream.youtube',
						config,
					})
				} else {
					this.config.module_config.push({
						type: 'livestream.native',
						config: {
							playback_mode: PLAYBACK_MODE_ALWAYS_ON,
							hls_url: primary.url,
							startMuted: !!primary.config?.startMuted,
						},
					})
				}
			} else {
				// Scheduled mode
				this.config.module_config.push({
					type: 'livestream.native',
					config: {
						playback_mode: PLAYBACK_MODE_SCHEDULE_DRIVEN,
					},
				})
			}
		},
		async saveStreamSchedules(targetRoomId) {
			const roomId = targetRoomId || this.roomId
			if (!roomId) return

			const baseUrl = this.getApiBaseUrl(roomId)
			const authHeader = api._config.token
				? `Bearer ${api._config.token}`
				: api._config.clientId
				? `Client ${api._config.clientId}`
				: null
			const headers = {
				Accept: 'application/json',
				'Content-Type': 'application/json',
			}
			if (authHeader) headers.Authorization = authHeader
			const csrfToken = this.getCsrfToken()
			if (csrfToken) headers['X-CSRFToken'] = csrfToken

			// Process deletions first
			const remainingDeletions = []
			for (const scheduleId of this.deletedScheduleIds) {
				try {
					const res = await fetch(`${baseUrl}${scheduleId}/`, {
						method: 'DELETE',
						headers,
						credentials: 'include',
					})
					if (!res.ok && res.status !== 404) {
						const text = await res.text().catch(() => '')
						console.warn('Failed to delete stream schedule:', scheduleId, text)
						remainingDeletions.push(scheduleId)
						this.deletedScheduleIds = remainingDeletions
						throw new Error(`Failed to delete stream schedule: ${text || res.statusText}`)
					}
				} catch (err) {
					if (!remainingDeletions.includes(scheduleId)) {
						remainingDeletions.push(scheduleId)
					}
					this.deletedScheduleIds = remainingDeletions
					throw err
				}
			}
			this.deletedScheduleIds = []

			if (this.isScheduledMode) {
				for (let i = 0; i < this.streams.length; i++) {
					const stream = this.streams[i]
					const payload = {
						title: `Stream ${i + 1}`,
						url: stream.url,
						stream_type: stream.stream_type,
						start_time: stream.start_time ? stream.start_time.toISOString() : null,
						end_time: stream.end_time ? stream.end_time.toISOString() : null,
						config: {
							enablePrivacyEnhancedMode: stream.config?.enablePrivacyEnhancedMode,
							loop: stream.config?.loop,
							modestBranding: stream.config?.modestBranding,
							startMuted: stream.config?.startMuted,
							hideControls: stream.config?.hideControls,
							noRelated: stream.config?.noRelated,
							disableKb: stream.config?.disableKb,
							showInfo: stream.config?.showInfo,
						},
					}

					if (stream.id) {
						const res = await fetch(`${baseUrl}${stream.id}/`, {
							method: 'PATCH',
							headers,
							body: JSON.stringify(payload),
							credentials: 'include',
						})
						if (!res.ok) {
							const text = await res.text()
							throw new Error(`Failed to update stream schedule ${i + 1}: ${text}`)
						}
					} else {
						const res = await fetch(baseUrl, {
							method: 'POST',
							headers,
							body: JSON.stringify(payload),
							credentials: 'include',
						})
						if (!res.ok) {
							const text = await res.text()
							throw new Error(`Failed to create stream schedule ${i + 1}: ${text}`)
						}
						const saved = await res.json()
						stream.id = saved.id
					}
				}
			} else {
				// In always-on mode, clear any remaining DB schedules for this room
				try {
					const existingSchedules = await this.fetchStreamSchedules()
					for (const schedule of existingSchedules) {
						await fetch(`${baseUrl}${schedule.id}/`, {
							method: 'DELETE',
							headers,
							credentials: 'include',
						})
					}
				} catch (err) {
					console.warn('Error clearing legacy stream schedules:', err)
				}
			}
		},
	},
})
</script>
<style lang="stylus">
.c-stage-settings
	display: flex
	flex-direction: column
	gap: 16px

	.stream-section-header
		display: flex
		justify-content: space-between
		align-items: flex-start
		flex-wrap: wrap
		gap: 12px
		margin-bottom: 8px
		.header-info
			h2
				font-size: 20px
				font-weight: 600
				margin: 0
				color: $clr-grey-900
			.subtitle
				font-size: 13px
				color: $clr-secondary-text-light
				margin: 2px 0 0 0
		.header-actions
			display: flex
			align-items: center
			gap: 8px
			.btn-add-scheduled-group
				display: inline-flex
				align-items: center
				gap: 8px
			.btn-add-scheduled
				themed-button-primary()
				height: 36px
				padding: 0 14px
				font-size: 13px
				font-weight: 500
				border-radius: 6px

	.info-tooltip-wrapper
		position: relative
		display: inline-flex
		align-items: center
		justify-content: center
		width: 28px
		height: 28px
		border-radius: 50%
		color: $clr-grey-600
		cursor: pointer
		outline: none
		&:hover, &:focus
			color: var(--clr-primary)
			.tooltip-bubble
				opacity: 1
				visibility: visible
				transform: translateY(0)
		.mdi-information-outline
			font-size: 20px
		.tooltip-bubble
			position: absolute
			top: 36px
			right: 0
			width: 220px
			padding: 8px 12px
			background: $clr-grey-900
			color: $clr-white
			font-size: 12px
			line-height: 16px
			border-radius: 6px
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15)
			opacity: 0
			visibility: hidden
			transform: translateY(-4px)
			transition: opacity 0.2s ease, transform 0.2s ease, visibility 0.2s ease
			z-index: 100
			pointer-events: none
			&::before
				content: ''
				position: absolute
				bottom: 100%
				right: 8px
				border: 5px solid transparent
				border-bottom-color: $clr-grey-900

	.loading-container
		display: flex
		justify-content: center
		padding: 32px

	.streams-list
		display: flex
		flex-direction: column
		gap: 16px

	.stream-card
		background: #ffffff
		border: 1px solid $clr-grey-200
		border-radius: 8px
		padding: 16px
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)
		transition: border-color 0.2s ease, box-shadow 0.2s ease
		&:hover
			border-color: $clr-grey-300
			box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06)

		.stream-card-header
			display: flex
			justify-content: space-between
			align-items: center
			margin-bottom: 16px
			padding-bottom: 8px
			border-bottom: 1px solid $clr-grey-100
			.header-left
				display: flex
				align-items: center
				gap: 8px
				.drag-handle
					color: $clr-grey-400
					font-size: 18px
					cursor: grab
				.stream-title
					font-size: 15px
					font-weight: 600
					color: $clr-grey-800
			.btn-delete-stream
				background: transparent
				border: none
				color: $clr-grey-500
				cursor: pointer
				padding: 4px
				border-radius: 4px
				font-size: 18px
				display: inline-flex
				align-items: center
				justify-content: center
				transition: color 0.15s ease, background-color 0.15s ease
				&:hover
					color: $clr-danger
					background: rgba($clr-danger, 0.08)

		.fields-grid
			display: grid
			grid-template-columns: 200px 1fr
			gap: 16px
			margin-bottom: 16px
			@media (max-width: 640px)
				grid-template-columns: 1fr

		.field-group
			display: flex
			flex-direction: column
			gap: 6px
			.field-label
				font-size: 13px
				font-weight: 500
				color: $clr-grey-700
				.required-star
					color: $clr-danger

		.custom-provider-select
			position: relative
			display: flex
			align-items: center
			background: #ffffff
			border: 1px solid $clr-grey-300
			border-radius: 6px
			height: 40px
			box-sizing: border-box
			&:focus-within
				border-color: var(--clr-primary)
				box-shadow: 0 0 0 2px rgba(187, 0, 17, 0.15)
			.provider-icon-badge
				display: flex
				align-items: center
				justify-content: center
				padding-left: 10px
				font-size: 20px
				pointer-events: none
				.mdi-youtube
					color: #FF0000
				.mdi-video-outline
					color: #1976D2
			.provider-select
				width: 100%
				height: 100%
				padding: 0 32px 0 8px
				border: none
				background: transparent
				font-size: 14px
				font-family: inherit
				color: $clr-grey-800
				cursor: pointer
				outline: none
				appearance: none
			.dropdown-arrow
				position: absolute
				right: 8px
				color: $clr-grey-500
				font-size: 18px
				pointer-events: none

		.input-wrapper
			position: relative
			display: flex
			align-items: center
			.text-input, .datetime-input
				width: 100%
				height: 40px
				padding: 0 12px
				border: 1px solid $clr-grey-300
				border-radius: 6px
				font-size: 14px
				font-family: inherit
				background: #ffffff
				color: $clr-grey-800
				box-sizing: border-box
				outline: none
				transition: border-color 0.15s ease, box-shadow 0.15s ease
				&:focus
					border-color: var(--clr-primary)
					box-shadow: 0 0 0 2px rgba(187, 0, 17, 0.15)
				&.has-error
					border-color: $clr-danger
			.datetime-input
				cursor: pointer
				&::-webkit-calendar-picker-indicator
					cursor: pointer
					opacity: 0.6
					transition: opacity 0.15s ease
					&:hover
						opacity: 1

		.field-error
			font-size: 12px
			color: $clr-danger
			margin-top: 2px

		.datetime-grid
			display: grid
			grid-template-columns: 1fr 1fr
			gap: 8px
			margin-top: 8px
			@media (max-width: 640px)
				grid-template-columns: 1fr

		.timezone-hint
			grid-column: 1 / -1
			font-size: 12px
			color: $clr-secondary-text-light
			margin-top: -8px
			margin-bottom: 8px

		.single-stream-scheduled-hint
			display: flex
			align-items: center
			justify-content: space-between
			flex-wrap: wrap
			gap: 8px
			padding: 8px 12px
			background: $clr-grey-50
			border-radius: 6px
			font-size: 13px
			color: $clr-grey-700
			margin-bottom: 16px
			.btn-clear-times
				background: transparent
				border: none
				color: var(--clr-primary)
				font-size: 13px
				font-weight: 500
				cursor: pointer
				text-decoration: underline
				padding: 0
				&:hover
					color: darken(#bb0011, 15%)

		.youtube-advanced-settings
			margin-top: 12px
			border-top: 1px solid $clr-grey-100
			padding-top: 10px

		.accordion-header
			display: flex
			align-items: center
			justify-content: space-between
			width: 100%
			padding: 6px 0
			background: transparent
			border: none
			cursor: pointer
			font-size: 13px
			font-weight: 500
			color: $clr-grey-700
			outline: none
			&:hover
				color: $clr-grey-900
			i
				font-size: 18px
				color: $clr-grey-500

		.advanced-switches
			display: flex
			flex-direction: column
			gap: 8px
			margin-top: 8px
			padding-left: 4px

	.scheduled-actions-footer
		display: flex
		margin-top: 8px
		.btn-add-another
			themed-button-secondary()
			font-size: 13px
			font-weight: 500
			border-radius: 6px
			height: 38px
			display: inline-flex
			align-items: center
			gap: 6px

	.interpretation-plugin-language-streams
		margin-top: 24px
		padding-top: 16px
		border-top: 1px solid $clr-grey-300

	.global-stream-error
		color: $clr-danger
		background: rgba($clr-danger, 0.08)
		border-left: 3px solid $clr-danger
		padding: 10px 14px
		border-radius: 4px
		font-size: 13px
		margin-top: 12px

.c-delete-confirm-prompt
	.content
		padding: 24px
		h2
			margin: 0 0 12px 0
			font-size: 18px
			color: $clr-grey-900
		p
			margin: 0 0 20px 0
			font-size: 14px
			color: $clr-grey-700
		.prompt-actions
			display: flex
			justify-content: flex-end
			gap: 10px
			.btn-danger
				themed-button-primary()
				background-color: $clr-danger !important
			.btn-cancel
				themed-button-secondary()
</style>
