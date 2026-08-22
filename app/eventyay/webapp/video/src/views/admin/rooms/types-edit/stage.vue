<template lang="pug">
.c-stage-settings
	.loading(v-if="loading")
		bunt-progress-circular(size="large")
	.error(v-else-if="loadError") {{ loadError }}
	template(v-else)
		.stream-card(v-for="(stream, index) in streams", :key="stream.localId")
			.stream-card-header
				h2 Stream {{ index + 1 }}
				bunt-icon-button(
					v-if="index > 0"
					@click="removeStream(index)"
					tooltip="Remove stream"
					tooltip-placement="left"
					aria-label="Remove stream"
				) delete-outline
			bunt-select(
				name="stream-source"
				:model-value="stream.stream_type"
				@update:model-value="changeStreamType(stream, $event)"
				:options="streamSourceOptions(stream)"
				option-value="id"
				option-label="label"
				label="Stream type / provider *"
				dropdown-class="stage-stream-source-dropdown"
			)
			.field-error(v-if="stream.errors.stream_type") {{ stream.errors.stream_type }}
			bunt-input(
				name="stream-url"
				v-model="stream.url"
				:label="streamUrlLabel(stream.stream_type)"
				required
				@blur="normalizeStreamUrl(stream)"
			)
			.field-hint(v-if="stream.stream_type === 'iframe'") {{ IFRAME_PROVIDER_HELP_TEXT }}
			.field-error(v-if="stream.errors.url") {{ stream.errors.url }}
			.schedule-fields(v-if="scheduledMode")
				.datetime-field
					label.datetime-label Start date & time *
					input.datetime-input(
						type="datetime-local"
						:value="formatInputDate(stream.start_time)"
						:class="{'has-error': stream.errors.start_time}"
						@input="setStreamDate(stream, 'start_time', $event.target.value)"
					)
					.field-error(v-if="stream.errors.start_time") {{ stream.errors.start_time }}
				.datetime-field
					label.datetime-label End date & time *
					input.datetime-input(
						type="datetime-local"
						:value="formatInputDate(stream.end_time)"
						:class="{'has-error': stream.errors.end_time}"
						@input="setStreamDate(stream, 'end_time', $event.target.value)"
					)
					.field-error(v-if="stream.errors.end_time") {{ stream.errors.end_time }}
				.timezone-hint All times shown in the event timezone ({{ eventTimezone }}).
			LanguageAudioSourceList(
				title="Languages and Audio Source (optional)"
				:entries="stream.config.languageUrls"
			)
			.youtube-options(v-if="stream.stream_type === 'youtube'")
				bunt-switch(name="enablePrivacyEnhancedMode", v-model="stream.config.enablePrivacyEnhancedMode", label="Enable No-Cookies")
				bunt-switch(name="loop", v-model="stream.config.loop", label="Loop")
				bunt-switch(name="modestBranding", v-model="stream.config.modestBranding", label="Enable Modest Branding")
				bunt-switch(name="startMuted", v-model="stream.config.startMuted", label="Start muted")
				bunt-switch(name="hideControls", v-model="stream.config.hideControls", label="Hide Controls", hint="Note: Hiding controls disables autoplay (browsers require muted autoplay, but users can't unmute without controls)")
				bunt-switch(name="noRelated", v-model="stream.config.noRelated", label="Limit related videos to same channel")
				bunt-switch(name="disableKb", v-model="stream.config.disableKb", label="Disable Keyboard Controls")
				bunt-switch(name="showInfo", v-model="stream.config.showInfo", label="Hide Video Info")
			.hls-options(v-if="stream.stream_type === 'hls' && !scheduledMode")
				upload-url-input(name="streamOfflineImage", v-model="stream.config.streamOfflineImage", label="Stream offline image")
				bunt-input(name="muxenvkey", v-if="$features.enabled('muxdata')", v-model="stream.config.mux_env_key", label="MUX data environment key")
				bunt-input(name="subtitle_url", v-model="stream.config.subtitle_url", label="URL for external subtitles")
				h4 Alternative Streams
				.alternative(v-for="(alternative, alternativeIndex) in (stream.config.alternatives || [])", :key="alternativeIndex")
					bunt-input(name="label", v-model="alternative.label", label="Label")
					bunt-input(name="hls_url", v-model="alternative.hls_url", label="HLS URL")
					bunt-icon-button(@click="deleteAlternativeStream(stream, alternativeIndex)") delete-outline
				bunt-button(@click="addAlternativeStream(stream)") Add alternative stream
		.add-stream-control
			bunt-button(@click="addScheduledStream") Add scheduled streams
			button.stream-help-button(
				type="button"
				aria-label="Adding several streams requires a stream schedule."
				aria-describedby="stream-schedule-help"
			)
				i.bunt-icon.mdi.mdi-information-outline(aria-hidden="true")
				span#stream-schedule-help.stream-help-tooltip(role="tooltip") Adding several streams requires a stream schedule.
		.collection-error(v-if="collectionError") {{ collectionError }}
		.interpretation-plugin-language-streams(v-if="showPluginLanguageStreams")
			LanguageAudioSourceList(
				title="Interpretation source"
				:entries="pluginLanguageStreamEntries"
			)
</template>
<script>
import { defineComponent } from 'vue'
import UploadUrlInput from 'components/UploadUrlInput'
import LanguageAudioSourceList from 'components/LanguageAudioSourceList'
import api from 'lib/api'
import moment from 'lib/timetravelMoment'
import { normalizeYoutubeVideoId } from 'lib/validators'
import {
	IFRAME_PROVIDER_HELP_TEXT,
	PLAYBACK_MODE_SCHEDULE_DRIVEN,
	getStagePlaybackMode,
	getStreamSourceOptions,
} from 'lib/stage-streams'

const STREAM_MODULE_TYPES = new Set([
	'livestream.native',
	'livestream.youtube',
	'livestream.iframe',
])
const MODULE_BY_STREAM_TYPE = {
	hls: 'livestream.native',
	youtube: 'livestream.youtube',
	iframe: 'livestream.iframe',
	vimeo: 'livestream.iframe',
}
const STREAM_TYPE_BY_MODULE = {
	'livestream.native': 'hls',
	'livestream.youtube': 'youtube',
	'livestream.iframe': 'iframe',
}
const URL_FIELD_BY_STREAM_TYPE = {
	hls: 'hls_url',
	youtube: 'ytid',
	iframe: 'url',
	vimeo: 'url',
}
let nextLocalStreamId = 0

function clone(value) {
	return JSON.parse(JSON.stringify(value || {}))
}

function newStream(overrides = {}) {
	return {
		localId: `stream-${++nextLocalStreamId}`,
		id: null,
		title: '',
		stream_type: 'youtube',
		url: '',
		start_time: null,
		end_time: null,
		config: { languageUrls: [], startMuted: true },
		providerState: {},
		errors: {},
		...overrides,
	}
}

function extractResponseError(data) {
	if (!data) return 'Failed to save stream configuration.'
	if (typeof data === 'string') return data
	if (Array.isArray(data)) return extractResponseError(data[0])
	for (const value of Object.values(data)) {
		const message = extractResponseError(value)
		if (message) return message
	}
	return 'Failed to save stream configuration.'
}

export default defineComponent({
	components: { UploadUrlInput, LanguageAudioSourceList },
	props: {
		config: {
			type: Object,
			required: true,
		},
		modules: {
			type: Object,
			required: true,
		},
		roomId: {
			type: [String, Number],
			default: null,
		},
		interpretationAdmin: {
			type: Object,
			default: null,
		},
	},
	data() {
		return {
			streams: [],
			forceScheduled: false,
			loading: Boolean(this.roomId),
			loadError: null,
			collectionError: null,
			IFRAME_PROVIDER_HELP_TEXT,
		}
	},
	computed: {
		scheduledMode() {
			return this.forceScheduled || this.streams.length > 1
		},
		eventTimezone() {
			return this.$store.state.world?.timezone || 'UTC'
		},
		showPluginLanguageStreams() {
			return Boolean(this.config?.interpretation_use_plugin_streams)
		},
		pluginLanguageStreamEntries() {
			return this.interpretationAdmin?.languageStreams ?? []
		},
	},
	async created() {
		const module = this.currentStreamModule()
		this.forceScheduled = getStagePlaybackMode(module) === PLAYBACK_MODE_SCHEDULE_DRIVEN
		if (this.forceScheduled && this.roomId) {
			await this.fetchSchedules()
		} else {
			this.streams = [this.streamFromModule(module)]
			this.loading = false
		}
	},
	methods: {
		currentStreamModule() {
			return this.modules['livestream.native'] || this.modules['livestream.youtube'] || this.modules['livestream.iframe']
		},
		streamFromModule(module) {
			const streamType = STREAM_TYPE_BY_MODULE[module?.type] || 'hls'
			const config = clone(module?.config)
			const url = config[URL_FIELD_BY_STREAM_TYPE[streamType]] || ''
			config.languageUrls = config.languageUrls || []
			return newStream({ stream_type: streamType, url, config })
		},
		streamFromSchedule(schedule) {
			const config = clone(schedule.config)
			config.languageUrls = config.languageUrls || []
			return newStream({
				id: schedule.id,
				title: schedule.title || '',
				stream_type: schedule.stream_type,
				url: schedule.url,
				start_time: schedule.start_time ? moment.parseZone(schedule.start_time) : null,
				end_time: schedule.end_time ? moment.parseZone(schedule.end_time) : null,
				config,
			})
		},
		streamSourceOptions(stream) {
			const options = getStreamSourceOptions()
			if (stream.stream_type === 'vimeo') {
				return [...options, { id: 'vimeo', label: 'Vimeo' }]
			}
			return options
		},
		streamUrlLabel(streamType) {
			return {
				youtube: 'YouTube video, playlist or live URL *',
				hls: 'HLS stream URL *',
				iframe: 'Iframe player URL *',
				vimeo: 'Vimeo URL *',
			}[streamType] || 'Stream URL / Input *'
		},
		changeStreamType(stream, streamType) {
			stream.providerState[stream.stream_type] = {
				url: stream.url,
				config: clone(stream.config),
			}
			const saved = stream.providerState[streamType]
			stream.stream_type = streamType
			stream.url = saved?.url || ''
			stream.config = saved?.config || {
				languageUrls: [],
				...(streamType === 'youtube' ? { startMuted: true } : {}),
			}
			stream.errors = {}
		},
		normalizeStreamUrl(stream) {
			if (this.scheduledMode || stream.stream_type !== 'youtube' || !stream.url) return
			const normalized = normalizeYoutubeVideoId(stream.url)
			if (normalized) stream.url = normalized
		},
		addScheduledStream() {
			this.forceScheduled = true
			this.streams.push(newStream())
			this.collectionError = null
		},
		removeStream(index) {
			if (index <= 0) return
			this.streams.splice(index, 1)
			if (this.streams.length === 1) {
				this.forceScheduled = false
				this.streams[0].start_time = null
				this.streams[0].end_time = null
			}
			this.collectionError = null
		},
		setStreamDate(stream, field, value) {
			stream[field] = value ? moment.tz(value, this.eventTimezone) : null
			delete stream.errors[field]
		},
		formatInputDate(value) {
			if (!value) return ''
			return moment.isMoment(value)
				? value.clone().tz(this.eventTimezone).format('YYYY-MM-DDTHH:mm')
				: moment.parseZone(value).tz(this.eventTimezone).format('YYYY-MM-DDTHH:mm')
		},
		addAlternativeStream(stream) {
			stream.config.alternatives = [
				...(stream.config.alternatives || []),
				{ label: '', hls_url: '' },
			]
		},
		deleteAlternativeStream(stream, index) {
			stream.config.alternatives.splice(index, 1)
			if (stream.config.alternatives.length === 0) delete stream.config.alternatives
		},
		isValidUrl(value) {
			try {
				const parsed = new URL(value)
				return ['http:', 'https:'].includes(parsed.protocol)
			} catch {
				return false
			}
		},
		validate() {
			this.collectionError = null
			let valid = !this.loading && !this.loadError
			for (const stream of this.streams) {
				stream.errors = {}
				if (!stream.stream_type) {
					stream.errors.stream_type = 'Stream type / provider is required.'
					valid = false
				}
				if (!stream.url?.trim()) {
					stream.errors.url = 'Stream URL / input is required.'
					valid = false
				} else if (stream.stream_type === 'youtube') {
					if (!normalizeYoutubeVideoId(stream.url)) {
						stream.errors.url = 'Enter a valid YouTube video ID or URL.'
						valid = false
					}
				} else if (!this.isValidUrl(stream.url)) {
					stream.errors.url = 'Enter a valid stream URL.'
					valid = false
				}
				if (this.scheduledMode) {
					if (!stream.start_time) {
						stream.errors.start_time = 'Start date & time is required.'
						valid = false
					}
					if (!stream.end_time) {
						stream.errors.end_time = 'End date & time is required.'
						valid = false
					} else if (stream.start_time && !stream.end_time.isAfter(stream.start_time)) {
						stream.errors.end_time = 'End date & time must be after start date & time.'
						valid = false
					}
				}
			}
			if (this.scheduledMode) {
				const ordered = [...this.streams]
					.filter(stream => stream.start_time && stream.end_time)
					.sort((left, right) => left.start_time.valueOf() - right.start_time.valueOf())
				for (let index = 1; index < ordered.length; index++) {
					if (ordered[index].start_time.isBefore(ordered[index - 1].end_time)) {
						ordered[index].errors.start_time = 'Stream schedules cannot overlap.'
						ordered[index - 1].errors.end_time = 'Stream schedules cannot overlap.'
						valid = false
					}
				}
			}
			if (!valid && !this.streams.some(stream => Object.keys(stream.errors).length)) {
				this.collectionError = this.loadError || 'Stream configuration is not ready.'
			}
			if (valid) this.syncModuleConfig()
			return valid
		},
		syncModuleConfig() {
			let streamModule
			if (this.scheduledMode) {
				streamModule = {
					type: 'livestream.native',
					config: { playback_mode: PLAYBACK_MODE_SCHEDULE_DRIVEN },
				}
			} else {
				const stream = this.streams[0]
				const config = clone(stream.config)
				for (const field of Object.values(URL_FIELD_BY_STREAM_TYPE)) delete config[field]
				config.playback_mode = 'always_on'
				config[URL_FIELD_BY_STREAM_TYPE[stream.stream_type]] = stream.url
				streamModule = {
					type: MODULE_BY_STREAM_TYPE[stream.stream_type],
					config,
				}
			}
			const moduleConfig = this.config.module_config || []
			const firstStreamIndex = moduleConfig.findIndex(module => STREAM_MODULE_TYPES.has(module.type))
			const withoutStreams = moduleConfig.filter(module => !STREAM_MODULE_TYPES.has(module.type))
			withoutStreams.splice(firstStreamIndex < 0 ? 0 : firstStreamIndex, 0, streamModule)
			this.config.module_config = withoutStreams
		},
		serializeSchedules() {
			if (!this.scheduledMode) return []
			return this.streams.map(stream => ({
				...(stream.id ? { id: stream.id } : {}),
				title: stream.title || '',
				url: this.serializeScheduledUrl(stream),
				start_time: stream.start_time.toISOString(),
				end_time: stream.end_time.toISOString(),
				stream_type: stream.stream_type,
				config: {
					...clone(stream.config),
					languageUrls: stream.config.languageUrls || [],
				},
			}))
		},
		serializeScheduledUrl(stream) {
			if (stream.stream_type !== 'youtube' || this.isValidUrl(stream.url)) {
				return stream.url
			}
			const youtubeId = normalizeYoutubeVideoId(stream.url)
			return youtubeId ? `https://www.youtube.com/watch?v=${youtubeId}` : stream.url
		},
		getAuthHeaders(contentType = false) {
			const headers = { Accept: 'application/json' }
			if (contentType) headers['Content-Type'] = 'application/json'
			if (api._config.token) headers.Authorization = `Bearer ${api._config.token}`
			else if (api._config.clientId) headers.Authorization = `Client ${api._config.clientId}`
			const csrfToken = document.cookie.match(/eventyay_csrftoken=([^;]+)/)?.[1]
			if (csrfToken) headers['X-CSRFToken'] = csrfToken
			return headers
		},
		getApiUrl(roomId = this.roomId) {
			const world = this.$store.state.world
			const organizer = world?.organizer_slug
			const event = world?.slug || world?.id
			return `/api/v1/organizers/${encodeURIComponent(organizer)}/events/${encodeURIComponent(event)}/rooms/${roomId}/`
		},
		async fetchSchedules() {
			try {
				const response = await fetch(`${this.getApiUrl()}stream-schedules/`, {
					headers: this.getAuthHeaders(),
					credentials: 'include',
				})
				if (!response.ok) {
					const data = await response.json().catch(() => null)
					throw new Error(extractResponseError(data))
				}
				const data = await response.json()
				const schedules = Array.isArray(data) ? data : data.results || []
				this.streams = schedules.map(schedule => this.streamFromSchedule(schedule))
				if (this.streams.length === 0) this.streams = [newStream()]
			} catch (error) {
				console.error('Failed to load stage stream schedules', error)
				this.loadError = error.message || 'Failed to load stream schedules.'
			} finally {
				this.loading = false
			}
		},
		async saveStreamConfiguration(roomId) {
			const response = await fetch(`${this.getApiUrl(roomId)}stream-configuration/`, {
				method: 'PUT',
				headers: this.getAuthHeaders(true),
				credentials: 'include',
				body: JSON.stringify({
					module_config: this.config.module_config,
					schedules: this.serializeSchedules(),
				}),
			})
			const data = await response.json().catch(() => null)
			if (!response.ok) throw new Error(extractResponseError(data))
			this.config.module_config = data.module_config
			if (this.scheduledMode) {
				this.streams = data.schedules.map(schedule => this.streamFromSchedule(schedule))
			} else {
				this.streams[0].id = null
				this.streams[0].errors = {}
			}
			return data
		},
	},
})
</script>
<style lang="stylus">
.c-stage-settings
	.loading
		padding: 32px
	.error, .collection-error, .field-error
		color: $clr-danger
	.field-error
		font-size: 13px
		margin: -8px 0 12px
	.stream-card
		border: border-separator()
		border-radius: 6px
		padding: 16px
		margin-bottom: 16px
		background-color: $clr-white
	.stream-card-header
		display: flex
		align-items: center
		justify-content: space-between
		h2
			margin: 0 0 12px
	.schedule-fields
		display: grid
		grid-template-columns: repeat(2, minmax(0, 1fr))
		gap: 16px
		margin: 8px 0 16px
	.datetime-field
		display: flex
		flex-direction: column
		gap: 6px
	.datetime-label
		font-size: 13px
		color: $clr-secondary-text-light
	.datetime-input
		min-height: 40px
		border: border-separator()
		border-radius: 4px
		padding: 0 10px
		font: inherit
		&.has-error
			border-color: $clr-danger
	.timezone-hint
		grid-column: 1 / -1
		font-size: 13px
		font-style: italic
		color: $clr-secondary-text-light
	.add-stream-control
		display: flex
		align-items: center
		gap: 4px
		margin: 0 0 20px
	.stream-help-button
		position: relative
		border: 0
		background: transparent
		color: $clr-secondary-text-light
		font-size: 20px
		line-height: 1
		padding: 6px
		cursor: help
		&:focus
			outline: 2px solid $clr-primary
			outline-offset: 2px
		&:hover .stream-help-tooltip, &:focus .stream-help-tooltip
			opacity: 1
			visibility: visible
	.stream-help-tooltip
		position: absolute
		z-index: 10
		left: calc(100% + 8px)
		top: 50%
		transform: translateY(-50%)
		width: 240px
		padding: 8px 10px
		border-radius: 4px
		background: $clr-primary-text-light
		color: $clr-white
		font-size: 12px
		line-height: 18px
		text-align: left
		opacity: 0
		visibility: hidden
		pointer-events: none
	.alternative
		display: grid
		grid-template-columns: 1fr 1fr auto
		gap: 8px
		align-items: center
	.youtube-options
		margin-top: 16px
	.interpretation-plugin-language-streams
		margin-top: 24px
		padding-top: 16px
		border-top: 1px solid $clr-grey-300
@media (max-width: 700px)
	.c-stage-settings
		.stream-card
			padding: 12px
		.schedule-fields
			grid-template-columns: 1fr
		.timezone-hint
			grid-column: auto
		.alternative
			grid-template-columns: 1fr
@supports (-moz-appearance: none)
	.stage-stream-source-dropdown
		margin-left: 8px
</style>
