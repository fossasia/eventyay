<template lang="pug">
prompt.c-create-stage-prompt(@close="$emit('close')")
	.content
		h1 {{ $t('CreateStagePrompt:headline:text') }}
		form(@submit.prevent="create")
			bunt-input(name="name", :label="$t('CreateStagePrompt:name:label')", icon="theater", :placeholder="$t('CreateStagePrompt:name:placeholder')", v-model="name", :validation="v$.name")
			.stage-mode
				.fieldset-label Stream type
				.ui-radio-options
					label.ui-radio-option(v-for="option in PLAYBACK_MODE_OPTIONS", :key="option.id")
						input(type="radio", name="playbackMode", :value="option.id", v-model="playbackMode")
						.radio-copy
							.ui-radio-title {{ option.label }}
							.ui-radio-description {{ option.description }}
			.default-source(v-if="playbackMode === PLAYBACK_MODE_ALWAYS_ON")
				.stream-source
					.fieldset-label Default stream source
					.ui-radio-options
						label.ui-radio-option(v-for="option in streamSourceOptions", :key="option.id")
							input(type="radio", name="streamSource", :value="option.id", v-model="streamSource")
							.radio-copy
								.ui-radio-title {{ option.label }}
				bunt-input(v-if="streamSource === 'hls'", name="url", :label="$t('CreateStagePrompt:url:label')", icon="link", placeholder="https://example.com/stream.m3u8", v-model="url", :validation="v$.url")
				bunt-input(v-else-if="streamSource === 'youtube'", name="youtubeId", label="YouTube Video ID or URL", icon="youtube", placeholder="https://www.youtube.com/watch?v=...", v-model="youtubeId", :validation="v$.youtubeId", @blur="normalizeYoutubeId")
				template(v-else-if="streamSource === 'iframe'")
					bunt-input(name="url", label="Iframe player URL", icon="link", placeholder="https://example.com/player", v-model="url", :validation="v$.url")
					.field-hint {{ IFRAME_PROVIDER_HELP_TEXT }}
			bunt-input-outline-container(:label="$t('CreateChatPrompt:description:label')")
				template(#default="{focus, blur}")
					textarea(v-model="description", @focus="focus", @blur="blur")
			bunt-button(type="submit", :loading="loading", :error-message="error") {{ $t('CreateStagePrompt:submit:label') }}
</template>
<script>
import { useVuelidate } from '@vuelidate/core'
import { mapGetters } from 'vuex'
import Prompt from 'components/Prompt'
import { required, url, youtubeid, normalizeYoutubeVideoId } from 'lib/validators'
import {
	PLAYBACK_MODE_ALWAYS_ON,
	PLAYBACK_MODE_OPTIONS,
	IFRAME_PROVIDER_HELP_TEXT,
	getStreamSourceOptions
} from 'lib/stage-streams'

export default {
	components: { Prompt },
	emits: ['close'],
	setup: () => ({ v$: useVuelidate() }),
	data() {
		return {
			name: '',
			playbackMode: PLAYBACK_MODE_ALWAYS_ON,
			streamSource: 'hls',
			url: '',
			youtubeId: '',
			description: '',
			loading: false,
			error: null,
			PLAYBACK_MODE_ALWAYS_ON,
			PLAYBACK_MODE_OPTIONS,
			IFRAME_PROVIDER_HELP_TEXT,
			streamSourceOptions: getStreamSourceOptions()
		}
	},
	computed: {
		...mapGetters(['hasPermission']),
	},
	validations() {
		const urlRules = {}
		const youtubeRules = {}
		if (this.playbackMode === PLAYBACK_MODE_ALWAYS_ON && ['hls', 'iframe'].includes(this.streamSource)) {
			urlRules.required = required('Stream URL is required')
			urlRules.url = url('must be a valid url')
		}
		if (this.playbackMode === PLAYBACK_MODE_ALWAYS_ON && this.streamSource === 'youtube') {
			youtubeRules.required = required('YouTube Video ID or URL is required')
			youtubeRules.youtubeid = youtubeid('not a valid YouTube video ID or URL')
		}
		return {
			url: urlRules,
			youtubeId: youtubeRules,
			name: {
				required: required('Name is required')
			}
		}
	},
	methods: {
		normalizeYoutubeId() {
			const id = normalizeYoutubeVideoId(this.youtubeId)
			if (id) this.youtubeId = id
		},
		buildLivestreamModule() {
			const config = {
				playback_mode: this.playbackMode,
			}
			if (this.playbackMode !== PLAYBACK_MODE_ALWAYS_ON) {
				// Schedule entries provide the concrete source type and URL at playback time.
				return { type: 'livestream.native', config }
			}
			if (this.streamSource === 'youtube') {
				config.ytid = normalizeYoutubeVideoId(this.youtubeId) || this.youtubeId
				return { type: 'livestream.youtube', config }
			}
			if (this.streamSource === 'iframe') {
				config.url = this.url
				return { type: 'livestream.iframe', config }
			}
			config.hls_url = this.url
			return { type: 'livestream.native', config }
		},
		async create() {
			this.error = null
			this.v$.$touch()
			if (this.v$.$invalid) return

			// Check permission before creating
			if (!this.hasPermission('world:rooms.create.stage')) {
				this.error = 'You do not have permission to create stages.'
				return
			}

			this.loading = true
			const modules = []
			modules.push({
				type: 'chat.native',
				config: {
					volatile: true,
				}
			})
			modules.push(this.buildLivestreamModule())
			let room
			try {
				({ room } = await this.$store.dispatch('createRoom', {
					name: this.name,
					description: this.description,
					modules
				}))
				this.loading = false
				this.$router.push({name: 'room', params: {roomId: room}})
				this.$emit('close')
			} catch (error) {
				this.loading = false
				this.error = error.message || error
			}
		}
	}
}
</script>
<style lang="stylus">
.c-create-stage-prompt
	.content
		display: flex
		flex-direction: column
		padding: 32px
		position: relative
		h1
			margin: 0
			text-align: center
		p
			max-width: 320px
		form
			display: flex
			flex-direction: column
			align-self: stretch
			.bunt-input-outline-container
				margin-top: 16px
				textarea
					background-color: transparent
					border: none
					outline: none
					resize: vertical
					min-height: 64px
					padding: 0 8px
			.stage-mode, .stream-source
				margin-top: 16px
				.fieldset-label
					font-size: 12px
					font-weight: 500
					color: $clr-secondary-text-light
					margin-bottom: 8px
			.default-source
				display: flex
				flex-direction: column
				.field-hint
					margin-top: 4px
					font-size: 12px
					line-height: 18px
					color: $clr-secondary-text-light
			.bunt-button
				themed-button-primary()
				margin-top: 16px
</style>
