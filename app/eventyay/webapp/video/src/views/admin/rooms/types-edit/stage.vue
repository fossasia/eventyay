<template lang="pug">
.c-stage-settings
	h2 {{ $t('Stream type') }}
	.ui-radio-options
		label.ui-radio-option(v-for="option in playbackModeOptions", :key="option.id")
			input(
				type="radio",
				:name="playbackModeInputName",
				:value="option.id",
				:checked="playbackMode === option.id",
				@change="playbackMode = option.id"
			)
			.radio-copy
				.ui-radio-title {{ option.label }}
				.ui-radio-description {{ option.description }}
	template(v-if="playbackMode === PLAYBACK_MODE_ALWAYS_ON")
		h2 {{ $t('Default stream source') }}
		bunt-select(name="stream-source", v-model="streamSource", :options="translatedStreamSourceOptions", option-value="id", option-label="label", :label="$t('Stream source')", dropdown-class="stage-stream-source-dropdown")
		template(v-if="modules['livestream.native']")
			bunt-input(name="url", v-model="modules['livestream.native'].config.hls_url", :label="$t('HLS URL')")
			upload-url-input(name="streamOfflineImage", v-model="modules['livestream.native'].config.streamOfflineImage", :label="$t('Stream offline image')")
			bunt-input(name="muxenvkey", v-if="$features.enabled('muxdata')", v-model="modules['livestream.native'].config.mux_env_key", :label="$t('MUX data environment key')")
			bunt-input(name="subtitle_url", v-model="modules['livestream.native'].config.subtitle_url", :label="$t('URL for external subtitles')")
			h4 {{ $t('Alternative Streams') }}
			.alternative(v-for="(a, i) in (modules['livestream.native'].config.alternatives || [])" :key="i")
				bunt-input(name="label", v-model="a.label", :label="$t('Label')")
				bunt-input(name="hls_url", v-model="a.hls_url", :label="$t('HLS URL')")
				bunt-icon-button(@click="deleteAlternativeStream(i)") delete-outline
			bunt-button(@click="modules['livestream.native'].config.alternatives = [...(modules['livestream.native'].config.alternatives || []), {label: '', hls_url: ''}]") {{ $t('Add alternative stream') }}
		// YouTube stream settings
		bunt-input(v-else-if="modules['livestream.youtube']", name="ytid", v-model="modules['livestream.youtube'].config.ytid", :label="$t('YouTube Video ID or URL')", :validation="v$.modules['livestream.youtube'].config.ytid", @blur="normalizePrimaryYoutubeId")
		// Language and URL input for YouTube stream
		.language-urls(v-if="modules['livestream.youtube']")
			LanguageAudioSourceList(
				:title="$t('Languages and Audio Source')"
				:entries="modules['livestream.youtube'].config.languageUrls"
			)
			LanguageAudioSourceList.plugin-language-streams(
				v-if="showPluginLanguageStreams"
				:title="$t('Interpretation source')"
				:entries="pluginLanguageStreamEntries"
			)
			// Switch button for no-cookies domain
			.bunt-switch-container
				bunt-switch(name="enablePrivacyEnhancedMode", v-model="enablePrivacyEnhancedMode", :label="$t('Enable No-Cookies')")
				bunt-switch(name="loop", v-model="loop", :label="$t('Loop')")
				bunt-switch(name="modestBranding", v-model="modestBranding", :label="$t('Enable Modest Branding')")
				bunt-switch(name="startMuted", v-model="startMuted", :label="$t('Start muted')")
				bunt-switch(name="hideControls", v-model="hideControls", :label="$t('Hide Controls')", :hint="$t('Note: Hiding controls disables autoplay so the stream can start with sound when the viewer clicks play.')")
				bunt-switch(name="noRelated", v-model="noRelated", :label="$t('Limit related videos to same channel')")
				bunt-switch(name="disableKb", v-model="disableKb", :label="$t('Disable Keyboard Controls')")
				bunt-switch(name="showInfo", v-model="showInfo", :label="$t('Hide Video Info')")
</template>
<script>
import { defineComponent } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import UploadUrlInput from 'components/UploadUrlInput'
import LanguageAudioSourceList from 'components/LanguageAudioSourceList'
import mixin from './mixin'
import {youtubeid, normalizeYoutubeVideoId} from 'lib/validators'
import {
	PLAYBACK_MODE_ALWAYS_ON,
	PLAYBACK_MODE_SCHEDULE_DRIVEN,
	getStagePlaybackMode,
	STREAM_SOURCE_OPTIONS,
	translatePlaybackModeOptions,
	translateStreamSourceOptions
} from 'lib/stage-streams'

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
	}
	return config
}

export default defineComponent({
	components: { UploadUrlInput, LanguageAudioSourceList },
	mixins: [mixin],
	props: {
		interpretationAdmin: {
			type: Object,
			default: null,
		},
	},
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			b_streamSource: null,
			streamSourceConfigs: {},
			playbackModeInputName: `playback-mode-${++playbackModeInputId}`,
			PLAYBACK_MODE_ALWAYS_ON,
		}
	},
	validations() {
		return {
			modules: {
				'livestream.youtube': {
					config: {
						ytid: {
							youtubeid: youtubeid(this.$t('not a valid YouTube video ID or URL'))
						}
					}
				}
			}
		}
	},
	computed: {
		translatedStreamSourceOptions() {
			this.$store.state.userLocale
			return translateStreamSourceOptions(this.$t.bind(this), STREAM_SOURCE_OPTIONS)
		},
		playbackModeOptions() {
			this.$store.state.userLocale
			return translatePlaybackModeOptions(this.$t.bind(this))
		},
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
		startMuted: {
			get() {
				return !!this.modules['livestream.youtube']?.config.startMuted
			},
			set(value) {
				this.setYoutubeConfigProp('startMuted', value)
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
		},
		showPluginLanguageStreams() {
			return Boolean(this.config?.interpretation_use_plugin_streams)
		},
		pluginLanguageStreamEntries() {
			return this.interpretationAdmin?.languageStreams ?? []
		}
	},
	created() {
		if (this.modules['livestream.native']) {
			this.b_streamSource = 'hls'
		} else if (this.modules['livestream.youtube']) {
			this.b_streamSource = 'youtube'
			// languageUrls is set in the created lifecycle hook
			if (!this.modules['livestream.youtube'].config.languageUrls) {
				this.modules['livestream.youtube'].config.languageUrls = []
			}
		}
	},
	methods: {
		currentStreamModule() {
			return this.modules['livestream.native'] || this.modules['livestream.youtube']
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
		setYoutubeConfigProp(prop, value) {
			if (!this.modules['livestream.youtube']) return

			if (value) {
				this.modules['livestream.youtube'].config[prop] = true
			} else {
				delete this.modules['livestream.youtube'].config[prop]
			}
		},
		deleteAlternativeStream(index) {
			if (!this.modules['livestream.native']?.config.alternatives) return
			this.modules['livestream.native'].config.alternatives.splice(index, 1)
			if (this.modules['livestream.native'].config.alternatives.length === 0) {
				this.modules['livestream.native'].config.alternatives = undefined
			}
		},
	}
})
</script>
<style lang="stylus">
.c-stage-settings
	// no local radio styles needed anymore
	.plugin-language-streams
		margin-top: 24px
		padding-top: 16px
		border-top: 1px solid $clr-grey-300
.bunt-switch-container
	margin-top: 16px
@supports (-moz-appearance: none)
	.stage-stream-source-dropdown
		margin-left: 8px
</style>
