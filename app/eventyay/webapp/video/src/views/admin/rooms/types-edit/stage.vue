<template lang="pug">
.c-stage-settings
	h2 Stream type
	.radio-options
		label.radio-option(v-for="option in PLAYBACK_MODE_OPTIONS", :key="option.id")
			input(
				type="radio",
				:name="playbackModeInputName",
				:value="option.id",
				:checked="playbackMode === option.id",
				@change="playbackMode = option.id"
			)
			.radio-copy
				.radio-title {{ option.label }}
				.radio-description {{ option.description }}
	template(v-if="playbackMode === PLAYBACK_MODE_ALWAYS_ON")
		h2 Default stream source
		bunt-select(name="stream-source", v-model="streamSource", :options="STREAM_SOURCE_OPTIONS", option-value="id", option-label="label", label="Stream source")
		template(v-if="modules['livestream.native']")
			bunt-input(name="url", v-model="modules['livestream.native'].config.hls_url", label="HLS URL")
			upload-url-input(name="streamOfflineImage", v-model="modules['livestream.native'].config.streamOfflineImage", label="Stream offline image")
			bunt-input(name="muxenvkey", v-if="$features.enabled('muxdata')", v-model="modules['livestream.native'].config.mux_env_key", label="MUX data environment key")
			bunt-input(name="subtitle_url", v-model="modules['livestream.native'].config.subtitle_url", label="URL for external subtitles")
			h4 Alternative Streams
			.alternative(v-for="(a, i) in (modules['livestream.native'].config.alternatives || [])" :key="i")
				bunt-input(name="label", v-model="a.label", label="Label")
				bunt-input(name="hls_url", v-model="a.hls_url", label="HLS URL")
				bunt-icon-button(@click="deleteAlternativeStream(i)") delete-outline
			bunt-button(@click="modules['livestream.native'].config.alternatives = [...(modules['livestream.native'].config.alternatives || []), {label: '', hls_url: ''}]") Add alternative stream
		// YouTube stream settings
		bunt-input(v-else-if="modules['livestream.youtube']", name="ytid", v-model="modules['livestream.youtube'].config.ytid", label="YouTube Video ID or URL", :validation="v$.modules['livestream.youtube'].config.ytid", @blur="normalizePrimaryYoutubeId")
		// Language and URL input for YouTube stream
		.language-urls(v-if="modules['livestream.youtube']")
			h4 Languages and Audio Source
			.language-url-entry(v-for="(entry, index) in modules['livestream.youtube'].config.languageUrls" :key="index")
				bunt-select(name="language", v-model="entry.language", :options="ISO_LANGUAGE_OPTIONS", label="Language")
				bunt-input(name="youtube_id" v-model="entry.youtube_id" label="Audio Source (YouTube ID or WHEP URL)" @blur="normalizeLanguageYoutubeId(entry)")
				bunt-icon-button(@click="deleteLanguageUrl(index)") delete-outline
			bunt-button(@click="addLanguageUrl") + Add Language and Audio Source
			// Switch button for no-cookies domain
			.bunt-switch-container
				bunt-switch(name="enablePrivacyEnhancedMode", v-model="enablePrivacyEnhancedMode", label="Enable No-Cookies")
				bunt-switch(name="loop", v-model="loop", label="Loop")
				bunt-switch(name="modestBranding", v-model="modestBranding", label="Enable Modest Branding")
				bunt-switch(name="hideControls", v-model="hideControls", label="Hide Controls", hint="Note: Hiding controls disables autoplay (browsers require muted autoplay, but users can't unmute without controls)")
				bunt-switch(name="noRelated", v-model="noRelated", label="Limit related videos to same channel")
				bunt-switch(name="disableKb", v-model="disableKb", label="Disable Keyboard Controls")
				bunt-switch(name="showInfo", v-model="showInfo", label="Hide Video Info")
		bunt-input(v-else-if="modules['livestream.iframe']", name="iframe-player", v-model="modules['livestream.iframe'].config.url", label="Iframe player url", :hint="IFRAME_PROVIDER_HELP_TEXT")
</template>
<script>
import { defineComponent } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import UploadUrlInput from 'components/UploadUrlInput'
import mixin from './mixin'
import {youtubeid, normalizeYoutubeVideoId} from 'lib/validators'
import ISO6391 from 'iso-639-1'
import {
	PLAYBACK_MODE_ALWAYS_ON,
	PLAYBACK_MODE_OPTIONS,
	PLAYBACK_MODE_SCHEDULE_DRIVEN,
	IFRAME_PROVIDER_HELP_TEXT,
	getStagePlaybackMode,
	getStreamSourceOptions
} from 'lib/stage-streams'

const STREAM_SOURCE_OPTIONS = getStreamSourceOptions()
const STREAM_SOURCE_BY_ID = STREAM_SOURCE_OPTIONS.reduce((acc, option) => {
	acc[option.id] = option
	return acc
}, {})
const STREAM_SOURCE_BY_MODULE = STREAM_SOURCE_OPTIONS.reduce((acc, option) => {
	acc[option.module] = option
	return acc
}, {})
let playbackModeInputId = 0

function cloneConfig(config) {
	return JSON.parse(JSON.stringify(config || {}))
}

function getDefaultStreamConfig(streamSource, playbackMode = PLAYBACK_MODE_ALWAYS_ON) {
	const config = { playback_mode: playbackMode }
	if (playbackMode === PLAYBACK_MODE_SCHEDULE_DRIVEN) return config
	if (streamSource === 'hls') {
		config.hls_url = ''
	} else if (streamSource === 'youtube') {
		config.ytid = ''
		config.languageUrls = []
	} else if (streamSource === 'iframe') {
		config.url = ''
	}
	return config
}

export default defineComponent({
	components: { UploadUrlInput },
	mixins: [mixin],
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			STREAM_SOURCE_OPTIONS,
			ISO_LANGUAGE_OPTIONS: [],
			b_streamSource: null,
			streamSourceConfigs: {},
			playbackModeInputName: `playback-mode-${++playbackModeInputId}`,
			PLAYBACK_MODE_ALWAYS_ON,
			PLAYBACK_MODE_OPTIONS,
			IFRAME_PROVIDER_HELP_TEXT
		}
	},
	validations() {
		return {
			modules: {
				'livestream.youtube': {
					config: {
						ytid: {
							youtubeid: youtubeid('not a valid YouTube video ID or URL')
						}
					}
				}
			}
		}
	},
	computed: {
		playbackMode: {
			get() {
				return getStagePlaybackMode(this.currentStreamModule())
			},
			set(value) {
				if (value === PLAYBACK_MODE_SCHEDULE_DRIVEN) {
					this.setScheduleDrivenModule()
					return
				}
				this.ensureStreamSourceModule(this.b_streamSource || 'hls', value)
			}
		},
		streamSource: {
			get() {
				return this.b_streamSource
			},
			set(value) {
				this.ensureStreamSourceModule(value, this.playbackMode)
			}
		},
		enablePrivacyEnhancedMode: {
			get() {
				return !!this.modules['livestream.youtube']?.config.enablePrivacyEnhancedMode
			},
			set(value) {
				this.setYoutubeConfigProp('enablePrivacyEnhancedMode', value)
			}
		},
		loop: {
			get() {
				return !!this.modules['livestream.youtube']?.config.loop
			},
			set(value) {
				this.setYoutubeConfigProp('loop', value)
			}
		},
		modestBranding: {
			get() {
				return !!this.modules['livestream.youtube']?.config.modestBranding
			},
			set(value) {
				this.setYoutubeConfigProp('modestBranding', value)
			}
		},
		hideControls: {
			get() {
				return !!this.modules['livestream.youtube']?.config.hideControls
			},
			set(value) {
				this.setYoutubeConfigProp('hideControls', value)
			}
		},
		noRelated: {
			get() {
				return !!this.modules['livestream.youtube']?.config.noRelated
			},
			set(value) {
				this.setYoutubeConfigProp('noRelated', value)
			}
		},
		disableKb: {
			get() {
				return !!this.modules['livestream.youtube']?.config.disableKb
			},
			set(value) {
				this.setYoutubeConfigProp('disableKb', value)
			}
		},
		showInfo: {
			get() {
				return !!this.modules['livestream.youtube']?.config.showInfo
			},
			set(value) {
				this.setYoutubeConfigProp('showInfo', value)
			}
		}
	},
	created() {
		// Initialize language options
		this.ISO_LANGUAGE_OPTIONS = this.getLanguageOptions()

		if (this.modules['livestream.native']) {
			this.b_streamSource = 'hls'
		} else if (this.modules['livestream.youtube']) {
			this.b_streamSource = 'youtube'
			// languageUrls is set in the created lifecycle hook
			if (!this.modules['livestream.youtube'].config.languageUrls) {
				this.modules['livestream.youtube'].config.languageUrls = []
			}
		} else if (this.modules['livestream.iframe']) {
			this.b_streamSource = 'iframe'
		}
	},
	methods: {
		currentStreamModule() {
			return this.modules['livestream.native'] || this.modules['livestream.youtube'] || this.modules['livestream.iframe']
		},
		rememberCurrentStreamConfig() {
			const module = this.currentStreamModule()
			if (!module) return
			if (getStagePlaybackMode(module) === PLAYBACK_MODE_SCHEDULE_DRIVEN) return

			const option = STREAM_SOURCE_BY_MODULE[module.type]
			if (option) this.streamSourceConfigs[option.id] = cloneConfig(module.config)
		},
		getStoredStreamConfig(streamSource, playbackMode) {
			if (playbackMode === PLAYBACK_MODE_SCHEDULE_DRIVEN) {
				return getDefaultStreamConfig(streamSource, playbackMode)
			}
			const storedConfig = this.streamSourceConfigs[streamSource]
			const config = storedConfig
				? cloneConfig(storedConfig)
				: getDefaultStreamConfig(streamSource, playbackMode)
			config.playback_mode = playbackMode
			return config
		},
		replaceStreamSourceModule(streamSource, playbackMode, updateSelectedSource = true) {
			const option = STREAM_SOURCE_BY_ID[streamSource]
			if (!option) return
			this.rememberCurrentStreamConfig()
			this.config.module_config = this.config.module_config.filter(module =>
				!STREAM_SOURCE_OPTIONS.some(sourceOption => sourceOption.module === module.type)
			)
			this.config.module_config.push({
				type: option.module,
				config: this.getStoredStreamConfig(streamSource, playbackMode)
			})
			if (updateSelectedSource) this.b_streamSource = streamSource
		},
		setScheduleDrivenModule() {
			this.replaceStreamSourceModule('hls', PLAYBACK_MODE_SCHEDULE_DRIVEN, false)
		},
		ensureStreamSourceModule(streamSource, playbackMode) {
			this.replaceStreamSourceModule(streamSource, playbackMode)
		},
		normalizePrimaryYoutubeId() {
			const val = this.modules['livestream.youtube']?.config?.ytid
			if (!val) return
			const id = normalizeYoutubeVideoId(val)
			if (id) this.modules['livestream.youtube'].config.ytid = id
		},
		normalizeLanguageYoutubeId(entry) {
			if (!entry?.youtube_id) return
			try {
				new URL(entry.youtube_id)
				const id = normalizeYoutubeVideoId(entry.youtube_id)
				if (id) entry.youtube_id = id
				return
			} catch (e) {
				const id = normalizeYoutubeVideoId(entry.youtube_id)
				if (id) entry.youtube_id = id
			}
		},
		setYoutubeConfigProp(prop, value) {
			if (!this.modules['livestream.youtube']) return

			if (value) {
				this.modules['livestream.youtube'].config[prop] = true
			} else {
				delete this.modules['livestream.youtube'].config[prop]
			}
		},
		addLanguageUrl() {
			if (!this.modules['livestream.youtube']) return
			if (!this.modules['livestream.youtube'].config.languageUrls) {
				this.modules['livestream.youtube'].config.languageUrls = []
			}
			this.modules['livestream.youtube'].config.languageUrls.push({ language: '', youtube_id: '' })
		},
		deleteLanguageUrl(index) {
			if (!this.modules['livestream.youtube']?.config.languageUrls) return
			this.modules['livestream.youtube'].config.languageUrls.splice(index, 1)
		},
		deleteAlternativeStream(index) {
			if (!this.modules['livestream.native']?.config.alternatives) return
			this.modules['livestream.native'].config.alternatives.splice(index, 1)
			if (this.modules['livestream.native'].config.alternatives.length === 0) {
				this.modules['livestream.native'].config.alternatives = undefined
			}
		},
		getLanguageOptions() {
			return ISO6391.getAllCodes().map(code => ({
				id: ISO6391.getName(code),
				label: ISO6391.getName(code),
			}))
		}
	}
})
</script>
<style lang="stylus">
.c-stage-settings
	.radio-options
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		max-width: 520px
		margin-bottom: 16px
	.radio-option
		display: flex
		gap: 10px
		padding: 10px 12px
		cursor: pointer
		color: $clr-primary-text-light
		&:not(:last-child)
			border-bottom: border-separator()
		input
			margin-top: 3px
			flex: none
		.radio-title
			font-weight: 500
			line-height: 20px
		.radio-description
			color: $clr-secondary-text-light
			font-size: 12px
			line-height: 18px
.bunt-switch-container
	margin-top: 16px
</style>
