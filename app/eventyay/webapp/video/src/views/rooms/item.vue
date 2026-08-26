<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.stage(v-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['call.janus']")
		media-source-placeholder
		reactions-overlay(v-if="hasLivestream")
		upcoming-stream-countdown(:room="room")
		.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
		.stage-tools(v-if="hasLivestream")
			// Added dropdown menu for audio translations near the reactions bar
			reactions-bar(:expanded="true", @expand="activeStageTool = 'reaction'")
			AudioTranslationDropdown(v-if="showCoreLanguageDropdown", :key="`${room.id}-core`", :languages="coreLanguages", :selected-language="selectedCoreLanguage", :label="$t('Audio Translation')", @languageChanged="handleCoreLanguageChange")
			AudioTranslationDropdown(v-if="showPluginLanguageDropdown", :key="`${room.id}-plugin`", :languages="pluginLanguages", :selected-language="selectedPluginLanguage", :label="$t('Interpretation')", @languageChanged="handlePluginLanguageChange")
	media-source-placeholder(v-else-if="modules['call.bigbluebutton'] || modules['call.zoom'] || modules['call.jitsi']")
	roulette(v-else-if="modules['networking.roulette'] && $features.enabled('roulette')", :module="modules['networking.roulette']", :room="room")
	landing-page(v-else-if="modules['page.landing']", :module="modules['page.landing']")
	markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
	chat(v-if="room.modules.length === 1 && modules['chat.native']", :room="room", :module="modules['chat.native']", mode="standalone", :key="room.id")
	.room-sidebar(v-else-if="modules['chat.native'] || modules['question'] || modules['poll']", :class="unreadTabsClasses", role="complementary")
		bunt-tabs(v-if="(!!modules['question'] + !!modules['poll'] + !!modules['chat.native']) > 1 && activeSidebarTab", :active-tab="activeSidebarTab")
			bunt-tab(v-if="modules['chat.native']", id="chat", :header="$t('Room:sidebar:tabs-header:chat')", @selected="activeSidebarTab = 'chat'")
			bunt-tab(v-if="modules['question']", id="questions", :header="$t('Room:sidebar:tabs-header:questions')", @selected="activeSidebarTab = 'questions'")
			bunt-tab(v-if="modules['poll']", id="polls", :header="$t('Room:sidebar:tabs-header:polls')", @selected="activeSidebarTab = 'polls'")
		chat(v-if="modules['chat.native']", v-show="activeSidebarTab === 'chat'", :room="room", :module="modules['chat.native']", mode="compact", :key="room.id", @change="changedTabContent('chat')")
		questions(v-if="modules['question']", v-show="activeSidebarTab === 'questions'", :module="modules['question']", @change="changedTabContent('questions')")
		polls(v-if="modules['poll']", v-show="activeSidebarTab === 'polls'", :module="modules['poll']", @change="changedTabContent('polls')")
</template>
<script>
// TODO
// - questions without chat
// - tab activity
import Chat from 'components/Chat'
import LandingPage from 'components/LandingPage'
import MarkdownPage from 'components/MarkdownPage'
import ReactionsBar from 'components/ReactionsBar'
import ReactionsOverlay from 'components/ReactionsOverlay'
import Roulette from 'components/Roulette'
import Polls from 'components/Polls'
import Questions from 'components/Questions'
import MediaSourcePlaceholder from 'components/MediaSourcePlaceholder'
import AudioTranslationDropdown from 'components/AudioTranslationDropdown'
import UpcomingStreamCountdown from 'components/UpcomingStreamCountdown'
import { isUsableAudioTranslationEntry, normalizeAudioTranslationSource } from 'lib/validators'
import { pluginLanguageStreams, roomUsesPluginLanguageStreams } from '../../interpretation-streams'
import { getStagePlaybackMode, PLAYBACK_MODE_SCHEDULE_DRIVEN } from 'lib/stage-streams'

export default {
	name: 'Room',
	components: {
		Chat,
		LandingPage,
		MarkdownPage,
		ReactionsBar,
		ReactionsOverlay,
		Roulette,
		Polls,
		Questions,
		MediaSourcePlaceholder,
		AudioTranslationDropdown,
		UpcomingStreamCountdown,
	},
	props: {
		room: Object,
		modules: Object
	},
	data() {
		return {
			activeSidebarTab: null, // chat, questions, polls
			unreadTabs: {
				chat: false,
				questions: false,
				polls: false
			},
			activeStageTool: null, // reaction, qa
			coreLanguages: [],
			pluginLanguages: [],
		}
	},
	computed: {
		currentYoutubeTranslation() {
			if (!this.room?.id) return null
			return this.$store.state.youtubeTranslationsByRoom?.[this.room.id] || null
		},
		showCoreLanguageDropdown() {
			if (roomUsesPluginLanguageStreams(this.room)) {
				return this.coreLanguages.length > 0
			}
			return this.coreLanguages.length > 1
		},
		showPluginLanguageDropdown() {
			return roomUsesPluginLanguageStreams(this.room) && this.pluginLanguages.length > 0
		},
		selectedCoreLanguage() {
			return this.getLanguageForTranslation(this.currentYoutubeTranslation, this.coreLanguages) || 'Original'
		},
		selectedPluginLanguage() {
			return this.getLanguageForTranslation(this.currentYoutubeTranslation, this.pluginLanguages) || 'Original'
		},
		usesStreamPolling() {
			return Boolean(
				this.modules['livestream.native'] ||
				this.modules['livestream.youtube']
			)
		},
		unreadTabsClasses() {
			return Object.entries(this.unreadTabs).filter(([tab, value]) => value).map(([tab]) => `tab-${tab}-unread`)
		},
		hasLivestream() {
			return Boolean(
				this.modules['livestream.native'] ||
				this.modules['livestream.youtube']
			)
		}
	},
	watch: {
		activeSidebarTab(tab) {
			this.unreadTabs[tab] = false
		},
		room: {
			handler: 'initializeLanguages',
			immediate: true
		},
		'room.currentStream': {
			handler: 'initializeLanguages'
		},
		'room.interpretation_language_streams': {
			handler: 'initializeLanguages'
		},
		'room.interpretation_use_plugin_streams': {
			handler: 'initializeLanguages'
		},
		'room.id'(roomId) {
			this.$store.dispatch('stopStreamPolling')
			if (roomId && this.usesStreamPolling) {
				this.$store.dispatch('startStreamPolling', roomId)
			}
		},
	},
	async created() {
		if (this.modules['chat.native']) {
			this.activeSidebarTab = 'chat'
		} else if (this.modules.question) {
			this.activeSidebarTab = 'questions'
		} else if (this.modules.poll) {
			this.activeSidebarTab = 'polls'
		}
		if (this.room?.id && this.usesStreamPolling) {
			await this.$nextTick()
			this.$store.dispatch('startStreamPolling', this.room.id)
		}
	},
	beforeUnmount() {
		this.$store.dispatch('stopStreamPolling')
	},
	methods: {
		changedTabContent(tab) {
			if (tab === this.activeSidebarTab) return
			this.unreadTabs[tab] = true
		},
		handleCoreLanguageChange(translationConfig) {
			this.updateActiveTranslation(translationConfig)
		},
		handlePluginLanguageChange(translationConfig) {
			this.updateActiveTranslation(translationConfig)
		},
		updateActiveTranslation(translationConfig) {
			this.$store.commit('updateYoutubeTransAudio', {
				roomId: this.room?.id,
				youtubeTranslation: translationConfig
			})
		},
		initializeLanguages() {
			this.coreLanguages = this.buildCoreLanguages()
			this.pluginLanguages = roomUsesPluginLanguageStreams(this.room)
				? pluginLanguageStreams(this.room)
				: []
			this.clearStaleTranslation()
		},
		buildCoreLanguages() {
			let languageUrls = null

			const stageModule = this.modules['livestream.native'] || this.modules['livestream.youtube']
			const isScheduleDriven = getStagePlaybackMode(stageModule) === PLAYBACK_MODE_SCHEDULE_DRIVEN

			if (isScheduleDriven) {
				if (this.room?.currentStream?.stream_type === 'youtube' && this.room.currentStream.config?.languageUrls) {
					languageUrls = this.room.currentStream.config.languageUrls
				}
			} else {
				const ytModule = this.modules['livestream.youtube']
				if (ytModule?.config?.languageUrls) {
					languageUrls = ytModule.config.languageUrls
				}
			}

			const languages = languageUrls
				? languageUrls.filter(entry => isUsableAudioTranslationEntry(entry))
				: []
			if (!languages.find(lang => lang.language === 'Original')) {
				languages.unshift({language: 'Original', youtube_id: null, use_video: false})
			}
			return languages
		},
		getLanguageForTranslation(translationConfig, languages) {
			if (!translationConfig?.url || !languages?.length) return 'Original'
			const matchingLanguage = languages.find(entry => (
				entry.language !== 'Original' &&
				normalizeAudioTranslationSource(entry.youtube_id) === translationConfig.url &&
				!!entry.use_video === !!translationConfig.useVideo
			))
			return matchingLanguage?.language || null
		},
		clearStaleTranslation() {
			if (!this.room?.id || !this.currentYoutubeTranslation) return
			const matchesCore = this.getLanguageForTranslation(this.currentYoutubeTranslation, this.coreLanguages)
			const matchesPlugin = this.getLanguageForTranslation(this.currentYoutubeTranslation, this.pluginLanguages)
			const hasCoreList = this.showCoreLanguageDropdown
			const hasPluginList = this.showPluginLanguageDropdown
			if (
				(!hasCoreList || !matchesCore) &&
				(!hasPluginList || !matchesPlugin)
			) {
				this.$store.commit('updateYoutubeTransAudio', {
					roomId: this.room.id,
					youtubeTranslation: null
				})
			}
		}
	}
}
</script>
<style lang="stylus">
.c-room
	flex: auto
	display: flex
	min-height: 0
	min-width: 0
	.stage
		display: flex
		flex-direction: column
		min-height: 0
		flex: auto
		overflow: hidden
		position: relative
	.c-media-source-placeholder
		flex: auto
	.room-sidebar
		display: flex
		flex-direction: column
		min-height: 0
		width: var(--chatbar-width)
		flex: none
		border-left: border-separator()
		> .bunt-tabs
			tabs-style(active-color: var(--clr-primary), indicator-color: var(--clr-primary), background-color: transparent)
			margin: 0
			border-bottom: border-separator()
			.bunt-tabs-header-items
				justify-content: center
		for tab in chat questions polls
			&.tab-{tab}-unread [aria-controls=\"{tab}\"] .bunt-tab-header-item-text
				position: relative
				&::after
					content: ''
					position: absolute
					top: -2px
					right: -8px
					display: block
					height: 5px
					width: 5px
					border-radius: 50%
					background-color: $clr-danger
	.stage-tools
		flex: none
		display: flex
		min-height: 56px
		justify-content: flex-end
		align-items: center
		flex-wrap: wrap
		gap: 4px
		user-select: none
		.stage-tool
			font-size: 16px
			color: $clr-secondary-text-light
			margin-right: 16px
			cursor: pointer
			padding: 8px
			position: relative
			&:hover
				border-radius: 4px
				background-color: $clr-grey-100
			&.active::before
				position: absolute
				bottom: 6px
				content: ''
				display: block
				height: 2px
				width: calc(100% - 16px)
				background-color: var(--clr-primary)
		+below('m')
			justify-content: space-between
	.stage-tool-blocker
		position: fixed
		top: 0
		left: 0
		width: 100vw
		height: var(--vh100)
		z-index: 800
	&.standalone-chat
		flex: auto
	&:not(.standalone-chat)
		.c-chat
			min-height: 0
	+below('m')
		flex-direction: column
		.stage
			flex: none
		.room-sidebar
			width: 100%
			flex: auto
		.c-media-source-placeholder
			height: var(--mobile-media-height)
			flex: none
		&:not(.standalone-chat)
			.c-chat
				flex: auto
				width: 100vw
				min-height: 0
</style>
