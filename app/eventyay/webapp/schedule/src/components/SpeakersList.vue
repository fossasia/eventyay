<template lang="pug">
.c-speakers-list(v-scrollbar.y="")
	.speakers-toolbar
		.search-box
			svg.search-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				circle(cx="11", cy="11", r="8")
				line(x1="21", y1="21", x2="16.65", y2="16.65")
			input.search-input(v-model="searchQuery", :placeholder="t.search_speakers")
			button.search-clear(v-if="searchQuery", @click="searchQuery = ''")
				svg(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					path(d="M18 6L6 18M6 6l12 12")
		.filter-group(v-if="availableLanguages.length > 1")
			.dropdown-wrapper
				button.filter-btn(@click="toggleDropdown('language')", :class="{'active': selectedLanguages.length}")
					svg.filter-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5a17.92 17.92 0 0 1-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418")
					| {{ t.language }}
					span.badge(v-if="selectedLanguages.length") {{ selectedLanguages.length }}
				.dropdown-menu(v-if="openDropdown === 'language'")
					label.dropdown-item(v-for="lang in availableLanguages", :key="lang")
						input(type="checkbox", :value="lang", v-model="selectedLanguages")
						| {{ lang }}
					.dropdown-actions(v-if="selectedLanguages.length")
						button.clear-btn(@click="selectedLanguages = []") {{ t.clear }}
		.filter-group(v-if="availableTracks.length > 1")
			.dropdown-wrapper
				button.filter-btn(@click="toggleDropdown('track')", :class="{'active': selectedTracks.length}")
					svg.filter-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z")
						path(d="M6 6h.008v.008H6V6Z")
					| {{ t.track }}
					span.badge(v-if="selectedTracks.length") {{ selectedTracks.length }}
				.dropdown-menu(v-if="openDropdown === 'track'")
					label.dropdown-item(v-for="track in availableTracks", :key="track.id")
						input(type="checkbox", :value="track.id", v-model="selectedTracks")
						span.track-color(v-if="track.color", :style="{'background-color': track.color}")
						| {{ getLocalizedString(track.name) }}
					.dropdown-actions(v-if="selectedTracks.length")
						button.clear-btn(@click="selectedTracks = []") {{ t.clear }}
		.sort-group
			.dropdown-wrapper
				button.filter-btn(@click="toggleDropdown('sort')")
					svg.filter-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M3 7.5 7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5")
					| {{ currentSortLabel }}
				.dropdown-menu(v-if="openDropdown === 'sort'")
					button.dropdown-item(v-for="opt in sortOptions", :key="opt.value", :class="{'selected': sortBy === opt.value}", @click="sortBy = opt.value; openDropdown = null")
						| {{ opt.label }}
	.speakers-grid(v-if="filteredSpeakers.length")
		a.speaker-card(
			v-for="speaker in filteredSpeakers",
			:key="speaker.code",
			:href="getSpeakerLink(speaker)",
			@click="onSpeakerClick($event, speaker)"
		)
			.speaker-avatar
				img(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url", :alt="speaker.name")
				.avatar-placeholder(v-else)
					svg(viewBox="0 0 24 24")
						path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
			.speaker-info
				.name {{ speaker.name || t.speaker_fallback }}
				.biography(v-if="speaker.biography") {{ speaker.biography }}
				.sessions-list(v-if="speaker.sessions && speaker.sessions.length")
					span.session-title(v-for="(session, idx) in speaker.sessions", :key="session.id")
						| {{ getLocalizedString(session.title) }}
						span.separator(v-if="idx < speaker.sessions.length - 1") ,&nbsp;
	.empty(v-else)
		| {{ t.no_speakers_found }}
	.backdrop(v-if="openDropdown", @click="openDropdown = null")
</template>

<script>
import { getLocalizedString } from '../utils'

export default {
	name: 'SpeakersList',
	inject: {
		scheduleData: { default: null },
		generateSpeakerLinkUrl: {
			default() {
				return ({speaker}) => `#speakers/${speaker.code}`
			}
		},
		onSpeakerLinkClick: {
			default() {
				return () => {}
			}
		},
		translationMessages: { default: () => ({}) }
	},
	props: {
		speakers: {
			type: Array,
			default: () => []
		}
	},
	data() {
		return {
			getLocalizedString,
			searchQuery: '',
			selectedLanguages: [],
			selectedTracks: [],
			sortBy: 'a-z',
			openDropdown: null,
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				speaker_fallback: m.speaker_fallback || 'Speaker',
				no_speakers_found: m.no_speakers_found || 'No speakers found.',
				search_speakers: m.search_speakers || 'Search speakers\u2026',
				language: m.language || 'Language',
				track: m.track || 'Track',
				sort: m.sort || 'Sort',
				a_to_z: m.a_to_z || 'A \u2192 Z',
				z_to_a: m.z_to_a || 'Z \u2192 A',
				clear: m.clear || 'Clear',
			}
		},
		sortOptions() {
			return [
				{ value: 'a-z', label: this.t.a_to_z },
				{ value: 'z-a', label: this.t.z_to_a },
			]
		},
		currentSortLabel() {
			const opt = this.sortOptions.find(o => o.value === this.sortBy)
			return opt ? opt.label : this.t.a_to_z
		},
		rawTalks() {
			if (!this.scheduleData) return []
			return this.scheduleData.schedule?.talks || []
		},
		availableTracks() {
			if (!this.scheduleData) return []
			return this.scheduleData.schedule?.tracks || []
		},
		availableLanguages() {
			const locales = this.scheduleData?.schedule?.content_locales || []
			if (locales.length) return locales
			const langs = new Set()
			for (const talk of this.rawTalks) {
				if (talk.content_locale) langs.add(talk.content_locale)
			}
			return [...langs].sort()
		},
		resolvedSpeakers() {
			if (this.speakers?.length) return this.speakers
			if (!this.scheduleData) return []
			const schedule = this.scheduleData.schedule
			const talks = this.rawTalks
			return (schedule?.speakers || []).map(speaker => {
				const speakerTalks = talks.filter(t =>
					t.speakers?.includes(speaker.code)
				)
				return {
					...speaker,
					sessions: speakerTalks,
				}
			})
		},
		trackFilteredSpeakers() {
			if (!this.selectedTracks.length) return this.resolvedSpeakers
			return this.resolvedSpeakers.filter(speaker =>
				(speaker.sessions || []).some(s => this.selectedTracks.includes(s.track))
			)
		},
		languageFilteredSpeakers() {
			if (!this.selectedLanguages.length) return this.trackFilteredSpeakers
			return this.trackFilteredSpeakers.filter(speaker =>
				(speaker.sessions || []).some(s => this.selectedLanguages.includes(s.content_locale))
			)
		},
		sortedSpeakers() {
			const speakers = [...this.languageFilteredSpeakers]
			if (this.sortBy === 'a-z') {
				return speakers.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
			}
			if (this.sortBy === 'z-a') {
				return speakers.sort((a, b) => (b.name || '').localeCompare(a.name || ''))
			}
			// default: a-z
			return speakers.sort((a, b) => (a.name || '').localeCompare(b.name || ''))
		},
		filteredSpeakers() {
			if (!this.searchQuery) return this.sortedSpeakers
			const q = this.searchQuery.toLowerCase()
			return this.sortedSpeakers.filter(speaker => {
				const name = (speaker.name || '').toLowerCase()
				const bio = (speaker.biography || '').toLowerCase()
				const sessionTitles = (speaker.sessions || [])
					.map(s => (getLocalizedString(s.title) || '').toLowerCase())
					.join(' ')
				return [name, bio, sessionTitles].some(f => f.includes(q))
			})
		}
	},
	methods: {
		getSpeakerLink(speaker) {
			return this.generateSpeakerLinkUrl({speaker})
		},
		onSpeakerClick(event, speaker) {
			this.onSpeakerLinkClick(event, speaker)
		},
		toggleDropdown(name) {
			this.openDropdown = this.openDropdown === name ? null : name
		}
	}
}
</script>

<style lang="stylus">
.c-speakers-list
	display: flex
	flex-direction: column
	min-height: 0
	position: relative
	.speakers-toolbar
		display: flex
		align-items: center
		gap: 8px
		padding: 12px 16px 0
		flex-wrap: wrap
		.search-box
			display: flex
			align-items: center
			gap: 8px
			border: 1px solid #ddd
			border-radius: 6px
			padding: 6px 10px
			background: #fff
			flex: 1
			min-width: 180px
			&:focus-within
				border-color: var(--pretalx-clr-primary, #3aa57c)
				box-shadow: 0 0 0 2px rgba(58, 165, 124, 0.15)
			.search-icon
				width: 16px
				height: 16px
				flex-shrink: 0
				color: #999
			.search-input
				flex: 1
				border: none
				outline: none
				font-size: 14px
				background: transparent
				&::placeholder
					color: #999
			.search-clear
				border: none
				background: transparent
				cursor: pointer
				padding: 2px
				display: flex
				align-items: center
				color: #999
				&:hover
					color: #333
				svg
					width: 14px
					height: 14px
		.filter-group, .sort-group
			position: relative
			.dropdown-wrapper
				position: relative
		.filter-btn
			display: flex
			align-items: center
			gap: 5px
			padding: 6px 12px
			border: 1px solid #ddd
			border-radius: 6px
			background: #fff
			font-size: 13px
			cursor: pointer
			white-space: nowrap
			color: #555
			&:hover
				border-color: #bbb
				background: #f8f8f8
			&.active
				border-color: var(--pretalx-clr-primary, #3aa57c)
				color: var(--pretalx-clr-primary, #3aa57c)
				background: rgba(58, 165, 124, 0.06)
			.filter-icon
				width: 14px
				height: 14px
				flex-shrink: 0
			.badge
				display: inline-flex
				align-items: center
				justify-content: center
				min-width: 18px
				height: 18px
				border-radius: 9px
				background: var(--pretalx-clr-primary, #3aa57c)
				color: #fff
				font-size: 11px
				font-weight: 600
				padding: 0 4px
		.dropdown-menu
			position: absolute
			top: calc(100% + 4px)
			left: 0
			background: #fff
			border: 1px solid #ddd
			border-radius: 6px
			box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12)
			z-index: 100
			min-width: 180px
			max-height: 260px
			overflow-y: auto
			padding: 4px 0
			.dropdown-item
				display: flex
				align-items: center
				gap: 6px
				padding: 7px 12px
				font-size: 13px
				cursor: pointer
				border: none
				background: none
				width: 100%
				text-align: left
				color: #333
				&:hover
					background: #f5f5f5
				&.selected
					color: var(--pretalx-clr-primary, #3aa57c)
					font-weight: 600
				input[type="checkbox"]
					accent-color: var(--pretalx-clr-primary, #3aa57c)
				.track-color
					display: inline-block
					width: 10px
					height: 10px
					border-radius: 2px
					flex-shrink: 0
			.dropdown-actions
				border-top: 1px solid #eee
				padding: 4px 8px
				.clear-btn
					border: none
					background: none
					color: var(--pretalx-clr-primary, #3aa57c)
					font-size: 12px
					cursor: pointer
					padding: 4px
					&:hover
						text-decoration: underline
	.backdrop
		position: fixed
		top: 0
		left: 0
		right: 0
		bottom: 0
		z-index: 50
	.speakers-grid
		display: flex
		flex-direction: column
		padding: 16px
		gap: 12px
	.speaker-card
		display: flex
		align-items: flex-start
		gap: 12px
		padding: 12px
		border: 1px solid $clr-grey-300
		border-radius: 6px
		text-decoration: none
		color: $clr-primary-text-light
		cursor: pointer
		&:hover
			background-color: $clr-grey-100
			.name
				color: var(--pretalx-clr-primary, var(--clr-primary))
				text-decoration: underline
	.speaker-avatar
		flex-shrink: 0
		width: 64px
		height: 64px
		img, .avatar-placeholder
			width: 64px
			height: 64px
			border-radius: 50%
			object-fit: cover
			box-shadow: rgba(0, 0, 0, 0.12) 0px 1px 3px 0px, rgba(0, 0, 0, 0.24) 0px 1px 2px 0px
		.avatar-placeholder
			background: rgba(0,0,0,0.1)
			display: flex
			align-items: center
			justify-content: center
			svg
				width: 60%
				height: 60%
				color: rgba(0,0,0,0.3)
	.speaker-info
		flex: 1
		min-width: 0
		.name
			font-weight: 600
			font-size: 16px
			margin-bottom: 4px
		.biography
			font-size: 14px
			color: $clr-secondary-text-light
			display: -webkit-box
			-webkit-line-clamp: 3
			-webkit-box-orient: vertical
			overflow: hidden
			margin-bottom: 4px
		.sessions-list
			font-size: 13px
			color: $clr-secondary-text-light
			.session-title
				font-style: italic
	.empty
		padding: 32px
		text-align: center
		color: $clr-secondary-text-light
</style>
