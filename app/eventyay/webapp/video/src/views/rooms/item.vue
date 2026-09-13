<template lang="pug">
.c-room(v-if="room", :class="{'standalone-chat': modules['chat.native'] && room.modules.length === 1}")
	.room-feature-disabled(v-if="roomIsDisabled")
		.disabled-card
			i.mdi.mdi-alert-circle-outline(aria-hidden="true")
			h2 {{ $t('Feature No Longer Available') }}
			p.disabled-message {{ roomDisabledReason }}
			router-link.btn-back-dashboard(:to="{name: 'home'}") {{ $t('Back to Dashboard') }}
	.stage(v-else-if="modules['livestream.native'] || modules['livestream.youtube'] || modules['livestream.vimeo']")
		media-source-placeholder
		LiveCaptions(v-if="ccEnabled", :ws-url="selectedCcWsUrl")
		reactions-overlay(v-if="hasLivestream")
		upcoming-stream-countdown(:room="room")
		.stage-tool-blocker(v-if="activeStageTool !== null", @click="activeStageTool = null")
		.stage-tools(v-if="hasLivestream")
			.cc-controls(v-if="showPluginLanguageDropdown")
				.dropdown-wrapper
					i.mdi.mdi-account-voice
					AudioTranslationDropdown(:key="`${room.id}-plugin`", :languages="pluginLanguages", :selected-language="selectedPluginLanguage", :label="$t('Interpretation')", @languageChanged="handlePluginLanguageChange")
				button.stage-tool.cc-toggle(:class="{active: ccEnabled}", @click="toggleCc", :title="$t('Toggle Captions')")
					i.mdi.mdi-closed-caption
				.dropdown-wrapper(v-if="ccEnabled")
					i.mdi.mdi-translate
					AudioTranslationDropdown(:key="`${room.id}-cc`", :languages="pluginLanguages", :selected-language="selectedCcLanguage", :label="$t('Caption Language')", @languageChanged="handleCcLanguageChange")
			reactions-bar(:expanded="true", @expand="activeStageTool = 'reaction'")
	.stage(v-else-if="modules['call.janus'] || modules['call.bigbluebutton'] || modules['call.zoom'] || modules['call.jitsi'] || modules['call.loungemesh']")
		media-source-placeholder
	roulette(v-else-if="modules['networking.roulette'] && $features.enabled('roulette')", :module="modules['networking.roulette']", :room="room")
	landing-page(v-else-if="modules['page.landing']", :module="modules['page.landing']")
	markdown-page(v-else-if="modules['page.markdown']", :module="modules['page.markdown']")
	chat(v-else-if="room.modules.length === 1 && modules['chat.native']", :room="room", :module="modules['chat.native']", mode="standalone", :key="room.id")
	.room-sidebar(v-if="hasSidebar", :class="unreadTabsClasses", role="complementary")
		bunt-tabs(v-if="(!!modules['question'] + !!modules['poll'] + !!modules['chat.native']) > 1 && activeSidebarTab", :active-tab="activeSidebarTab")
			bunt-tab(v-if="modules['chat.native']", id="chat", :header="$t('Chat')", @selected="activeSidebarTab = 'chat'")
			bunt-tab(v-if="modules['question']", id="questions", :header="$t('Questions')", @selected="activeSidebarTab = 'questions'")
			bunt-tab(v-if="modules['poll']", id="polls", :header="$t('Polls')", @selected="activeSidebarTab = 'polls'")
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
import LiveCaptions from 'components/LiveCaptions'
import UpcomingStreamCountdown from 'components/UpcomingStreamCountdown'
import { normalizeAudioTranslationSource } from 'lib/validators'
import { pluginLanguageStreams, roomUsesPluginLanguageStreams } from '../../interpretation-streams'
import { interpretationApiUrl, interpretationAuthHeaders } from 'lib/interpretation-api'
import { hasOrganizerTraits } from 'lib/traitGrants'
import { hasEmbeddedSuite, isRoomVisibleToAttendee } from 'lib/video-providers'

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
		LiveCaptions,
		UpcomingStreamCountdown,
	},
	props: {
		room: Object,
		modules: Object
	},
	data() {
		return {
			localActiveSidebarTab: null,
			unreadTabs: {
				chat: false,
				questions: false,
				polls: false
			},
			activeStageTool: null, // reaction, qa
			pluginLanguages: [],
			ccEnabled: false,
			isManualCCOverride: false,
			selectedCcLanguage: 'Original',
			listenerToken: null,
			activeTranslationConfig: null,
		}
	},
	computed: {
		activeSidebarTab: {
			get() {
				return this.$store.state.activeRoomSidebarTab || this.localActiveSidebarTab || (this.modules['chat.native'] ? 'chat' : this.modules.question ? 'questions' : this.modules.poll ? 'polls' : null)
			},
			set(tab) {
				this.localActiveSidebarTab = tab
				this.$store.commit('setActiveRoomSidebarTab', tab)
			}
		},
		rooms() {
			return this.$store.state.rooms
		},
		roomIsDisabled() {
			if (!this.room) return false
			if (this.room.is_disabled) return true
			if (this.hasOrganiserPermissions) return false
			return !isRoomVisibleToAttendee(this.room, this.$store.state.world?.video_providers)
		},
		roomDisabledReason() {
			return this.room?.disabled_reason || this.$t('This feature is no longer available. Please contact system administrator.')
		},
		hasOrganiserPermissions() {
			if (!window.eventyay?.isOrganizerArea) return false
			if (window.eventyay?.hasOrganiserPermissions) return true
			const tokenTraits = this.$store.state.user?.traits || []
			return (
				hasOrganizerTraits(tokenTraits) ||
				this.hasPermission('world:users.list') ||
				this.hasPermission('world:update') ||
				this.hasPermission('room:update')
			)
		},
		hasEmbeddedCallSuite() {
			return hasEmbeddedSuite(this.modules)
		},
		hasSidebar() {
			if (this.roomIsDisabled) return false
			// Video conference suites (BigBlueButton, Jitsi, Zoom) have their own native in-frame
			// options for chats, polls, questions, etc.; do not show platform native sidebar for them.
			// Janus WebRTC uses native platform chat and displays the sidebar when chat.native is attached.
			if (this.hasEmbeddedCallSuite) return false
			if (this.room?.modules?.length === 1 && this.modules['chat.native']) return false
			if (this.$store.state.roomSidebarCollapsedByRoom?.[this.room?.id]) return false
			return Boolean(
				this.modules['chat.native'] ||
				this.modules['question'] ||
				this.modules['poll']
			)
		},
		currentInterpretation() {
			if (!this.room?.id) return null
			return this.$store.state.interpretationStreamsByRoom?.[this.room.id] || this.$store.state.youtubeTranslationsByRoom?.[this.room.id] || null
		},
		showPluginLanguageDropdown() {
			return roomUsesPluginLanguageStreams(this.room) && this.pluginLanguages.length > 0
		},
		selectedPluginLanguage() {
			return this.getLanguageForTranslation(this.currentInterpretation, this.pluginLanguages) || 'Original'
		},
		selectedCcWsUrl() {
			if (!this.ccEnabled) return null
			const lang = this.pluginLanguages.find(l => l.language === this.selectedCcLanguage)
			if (lang && lang.caption_ws_url && this.listenerToken) {
				return `${lang.caption_ws_url}${lang.caption_ws_url.includes('?') ? '&' : '?'}token=${this.listenerToken}`
			}
			return null
		},
		usesStreamPolling() {
			return Boolean(
				this.modules['livestream.native'] ||
				this.modules['livestream.youtube'] ||
				this.modules['livestream.vimeo']
			)
		},
		unreadTabsClasses() {
			return Object.entries(this.unreadTabs).filter(([tab, value]) => value).map(([tab]) => `tab-${tab}-unread`)
		},
		hasLivestream() {
			return Boolean(
				this.modules['livestream.native'] ||
				this.modules['livestream.youtube'] ||
				this.modules['livestream.vimeo']
			)
		},

	},
	watch: {
		activeSidebarTab(tab) {
			this.unreadTabs[tab] = false
		},
		room: {
			handler(room, oldRoom) {
				if (room?.id !== oldRoom?.id) {
					this.$store.dispatch('stopStreamPolling')
					this.listenerToken = null
					if (room?.id && this.usesStreamPolling) {
						this.$store.dispatch('startStreamPolling', room.id)
					}
					if (room?.id && this.showPluginLanguageDropdown) {
						this.fetchListenerToken()
					}
				}
				this.initializeLanguages()
				this.checkDirectAccess()
			},
			immediate: true
		},
		rooms: {
			handler() {
				this.checkDirectAccess()
			},
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
		showPluginLanguageDropdown: {
			handler(val) {
				if (val && this.room?.id && !this.listenerToken) {
					this.fetchListenerToken()
				}
			},
			immediate: true
		}
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
	mounted() {
		this.checkDirectAccess()
	},
	beforeUnmount() {
		this.$store.dispatch('stopStreamPolling')
	},
	methods: {
		async fetchListenerToken() {
			if (!this.room?.id) return;
			const currentRoomId = this.room.id;
			// Use interpretationApiUrl + interpretationAuthHeaders so X-CSRFToken is included
			const url = interpretationApiUrl(this.$store, this.room.id, 'listener-token/');
			const headers = await interpretationAuthHeaders(true);
			try {
				const response = await fetch(url, { method: 'POST', headers, credentials: 'include' });
				if (this.room?.id !== currentRoomId) return;
				if (response.ok) {
					const data = await response.json();
					if (data && data.token) {
						this.listenerToken = data.token;
					}
				} else {
					console.error('listener-token failed:', response.status);
				}
			} catch (err) {
				if (this.room?.id === currentRoomId) {
					console.error('Failed to fetch listener token', err);
				}
			}
		},
		checkDirectAccess() {
			if (!this.rooms) return
			if (!this.hasOrganiserPermissions) {
				const roomId = this.roomId || this.$route.params.roomId
				if (roomId && (!this.room || this.roomIsDisabled)) {
					this.$router.replace({ name: 'about' })
				}
			}
		},
		changedTabContent(tab) {
			if (tab === this.activeSidebarTab) return
			this.unreadTabs[tab] = true
		},
		handlePluginLanguageChange(translationConfig) {
			this.updateActiveTranslation(translationConfig)
			if (!this.isManualCCOverride && this.ccEnabled) {
				this.selectedCcLanguage = this.getLanguageForTranslation(translationConfig, this.pluginLanguages) || 'Original'
			}
		},
		handleCcLanguageChange(translationConfig) {
			this.isManualCCOverride = true
			this.selectedCcLanguage = this.getLanguageForTranslation(translationConfig, this.pluginLanguages) || 'Original'
		},
		toggleCc() {
			this.ccEnabled = !this.ccEnabled
			if (this.ccEnabled && !this.isManualCCOverride) {
				this.selectedCcLanguage = this.selectedPluginLanguage
			}
		},
		updateActiveTranslation(translationConfig) {
			this.activeTranslationConfig = translationConfig;
			this.recomputeInterpretationAudio();
		},
		recomputeInterpretationAudio() {
			let finalConfig = this.activeTranslationConfig;
			if (finalConfig && finalConfig.language === 'Original') {
				finalConfig = null;
			}
			if (finalConfig && !finalConfig.url && !finalConfig.youtube_id) {
				finalConfig = null;
			}
			this.$store.commit('updateInterpretationAudio', {
				roomId: this.room?.id,
				interpretation: finalConfig
			})
		},
		initializeLanguages() {
			this.pluginLanguages = roomUsesPluginLanguageStreams(this.room)
				? pluginLanguageStreams(this.room)
				: []
			this.clearStaleTranslation()
		},
		getLanguageForTranslation(translationConfig, languages) {
			if (!translationConfig?.url || !languages?.length) return 'Original'
			const matchingLanguage = languages.find(entry => (
				entry.language !== 'Original' &&
				normalizeAudioTranslationSource(entry.url || entry.youtube_id) === translationConfig.url &&
				!!entry.use_video === !!translationConfig.useVideo
			))
			return matchingLanguage?.language || null
		},
		clearStaleTranslation() {
			if (!this.room?.id || !this.currentInterpretation) return
			const matchesPlugin = this.getLanguageForTranslation(this.currentInterpretation, this.pluginLanguages)
			if (!this.showPluginLanguageDropdown || !matchesPlugin) {
				this.$store.commit('updateInterpretationAudio', {
					roomId: this.room.id,
					interpretation: null
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
	max-width: 100%
	overflow: hidden
	.stage
		display: flex
		flex-direction: column
		min-height: 0
		min-width: 0
		max-width: 100%
		flex: auto
		overflow: hidden
		position: relative
		+below('m')
			height: auto
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
			&.tab-{tab}-unread [aria-controls="{tab}"] .bunt-tab-header-item-text
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
		min-height: 40px
		justify-content: space-between
		align-items: center
		width: 100%
		box-sizing: border-box
		margin: 0 auto
		flex-wrap: wrap
		gap: 6px
		padding: 4px 16px
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
				left: 50%
				transform: translateX(-50%)
				content: ''
				display: block
				height: 2px
				width: calc(100% - 16px)
				background-color: var(--clr-primary)
		.cc-controls
			display: flex
			align-items: center
			gap: 8px
			flex-wrap: wrap
			flex-shrink: 0
			.dropdown-wrapper
				display: flex
				align-items: center
				gap: 4px
				.mdi
					font-size: 20px
					color: var(--clr-secondary-text-light)
			.cc-toggle
				margin: 0
				padding: 4px
				display: flex
				align-items: center
				.mdi
					font-size: 22px
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
				width: 100%
				min-height: 0
	.room-feature-disabled
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		width: 100%
		height: 100%
		min-height: 60vh
		padding: 32px
		background-color: $clr-grey-50
		flex: auto

		.disabled-card
			max-width: 520px
			text-align: center
			padding: 40px 32px
			background-color: $clr-white
			border: 1px solid $clr-grey-200
			border-radius: 8px
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05)

			i.mdi
				font-size: 56px
				color: #d9534f
				margin-bottom: 16px
				display: block

			h2
				font-size: 22px
				font-weight: 600
				color: $clr-grey-900
				margin: 0 0 12px

			.disabled-message
				font-size: 15px
				line-height: 1.5
				color: $clr-grey-700
				margin: 0 0 24px

			.btn-back-dashboard
				display: inline-block
				padding: 9px 22px
				background-color: #337ab7
				color: #ffffff
				border-radius: 4px
				font-size: 14px
				font-weight: 500
				text-decoration: none
				transition: background-color 0.15s ease
				&:hover
					background-color: #286090
					text-decoration: none
</style>
