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
					svg.filter-icon(viewBox="0 0 24 24", fill="currentColor", aria-hidden="true")
						path(d="M12.87 15.07l-2.54-2.51c.86-1.02 1.52-2.12 1.99-3.28H14V7h-4V5H8v2H4v2h7.17c-.39 1.17-.96 2.27-1.7 3.25-.48-.63-.9-1.31-1.25-2.03H6.1c.5 1.09 1.17 2.14 2 3.11L3 20h2l5-5 3.11 3.11.76-3.04z")
						path(d="M15.5 11h-2L9 22h2l1-3h4l1 3h2l-3.5-11zm-2.3 6 .8-2.8.8 2.8h-1.6z")
					span.btn-label {{ t.language }}
					span.badge(v-if="selectedLanguages.length") {{ selectedLanguages.length }}
				.dropdown-menu(v-if="openDropdown === 'language'")
					label.dropdown-item(v-for="lang in availableLanguages", :key="lang")
						input(type="checkbox", :value="lang", v-model="selectedLanguages")
						| {{ formatLanguageLabel(lang) }}
		.filter-group(v-if="availableTracks.length > 1")
			.dropdown-wrapper
				button.filter-btn(@click="toggleDropdown('track')", :class="{'active': selectedTracks.length}")
					svg.filter-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M9.568 3H5.25A2.25 2.25 0 0 0 3 5.25v4.318c0 .597.237 1.17.659 1.591l9.581 9.581c.699.699 1.78.872 2.607.33a18.095 18.095 0 0 0 5.223-5.223c.542-.827.369-1.908-.33-2.607L11.16 3.66A2.25 2.25 0 0 0 9.568 3Z")
						path(d="M6 6h.008v.008H6V6Z")
					span.btn-label {{ t.track }}
					span.badge(v-if="selectedTracks.length") {{ selectedTracks.length }}
				.dropdown-menu(v-if="openDropdown === 'track'")
					label.dropdown-item(v-for="track in availableTracks", :key="track.id")
						input(type="checkbox", :value="track.id", v-model="selectedTracks")
						span.track-color(v-if="track.color", :style="{'background-color': track.color}")
						| {{ getLocalizedString(track.name) }}
					.dropdown-actions(v-if="selectedTracks.length")
						button.clear-btn(@click="selectedTracks = []") {{ t.clear }}
		button.filter-btn.clear-filters-btn(
			v-if="hasActiveFilters",
			:title="t.reset_all_filters",
			:aria-label="t.reset_all_filters",
			@click="clearAllFilters"
		)
			svg.filter-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				path(d="M18 6L6 18M6 6l12 12")
		.sort-group
			.dropdown-wrapper
				button.filter-btn(@click="toggleDropdown('sort')")
					svg.filter-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M3 7.5 7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5")
					span.btn-label {{ currentSortLabel }}
				.dropdown-menu(v-if="openDropdown === 'sort'")
					button.dropdown-item(v-for="opt in sortOptions", :key="opt.value", :class="{'selected': sortBy === opt.value}", @click="sortBy = opt.value; openDropdown = null")
						| {{ opt.label }}
		.view-toggle
			button.filter-btn.view-btn(@click="toggleView", :title="viewToggleTitle")
				svg.filter-icon(v-if="viewMode === 'list'", viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					path(d="M4 6h16M4 12h16M4 18h16")
				svg.filter-icon(v-else, viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					rect(x="3" y="3" width="7" height="7")
					rect(x="14" y="3" width="7" height="7")
					rect(x="3" y="14" width="7" height="7")
					rect(x="14" y="14" width="7" height="7")
	.speakers-grid(v-if="filteredSpeakers.length && viewMode === 'list'")
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
	.speakers-details(v-else-if="filteredSpeakers.length && viewMode === 'details'")
		.featured-speakers-grid
			.featured-speaker-column(v-for="speaker in filteredSpeakers", :key="speaker.code")
				details.featured-speaker-card
					summary.featured-speaker-summary
						.thumbnail
							img(
								v-if="speaker.avatar || speaker.avatar_url",
								:src="speaker.avatar || speaker.avatar_url",
								:alt="speaker.name || t.speaker_fallback",
								loading="lazy"
							)
							.avatar-placeholder(v-else)
								svg(viewBox="0 0 24 24")
									path(fill="currentColor", d="M12,1A5.8,5.8 0 0,1 17.8,6.8A5.8,5.8 0 0,1 12,12.6A5.8,5.8 0 0,1 6.2,6.8A5.8,5.8 0 0,1 12,1M12,15C18.63,15 24,17.67 24,21V23H0V21C0,17.67 5.37,15 12,15Z")
							.caption.text-center
								h4 {{ speaker.name || t.speaker_fallback }}
								p(v-if="speaker.biography") {{ speaker.biography }}
					.featured-speaker-details
						.featured-speaker-bio(v-if="speaker.biography") {{ speaker.biography }}
						template(v-if="speaker.sessions && speaker.sessions.length")
							hr.featured-speaker-divider
							.featured-speaker-sessions
								h4 {{ t.sessions }}
								.featured-speaker-session(v-for="session in speaker.sessions", :key="session.id")
									small.featured-speaker-session-time {{ formatSessionDateTime(session) }}
									a.featured-speaker-session-link(
										:href="getSessionLink(session)",
										:style="getSessionStyle(session)",
										@click="onSessionClick($event, session)"
									)
										span.featured-speaker-session-slot {{ formatSessionSlot(session) }}
										span.featured-speaker-session-title {{ getLocalizedString(session.title) }}
						.featured-speaker-profile-link
							a(:href="getSpeakerLink(speaker)", @click="onSpeakerClick($event, speaker)") {{ t.view_profile }}
	.empty(v-else)
		| {{ t.no_speakers_found }}
	.backdrop(v-if="openDropdown", @click="openDropdown = null")
</template>

<script>
import moment from 'moment-timezone'
import { getLocalizedString } from '../utils'

function normalizeLocaleCode (code) {
	if (!code || typeof code !== 'string') return null
	return code.replace(/_/g, '-').trim().toLowerCase()
}

function localePrimary (code) {
	const normalized = normalizeLocaleCode(code)
	if (!normalized) return null
	return normalized.split('-')[0] || null
}

function localesMatch (filterValue, sessionValue) {
	const a = normalizeLocaleCode(filterValue)
	const b = normalizeLocaleCode(sessionValue)
	if (!a || !b) return false
	if (a === b) return true
	return localePrimary(a) && localePrimary(a) === localePrimary(b)
}

export default {
	name: 'SpeakersList',
	inject: {
		scheduleData: { default: null },
		eventUrl: { default: '' },
		generateSpeakerLinkUrl: {
			default() {
				return ({speaker}) => `#speakers/${speaker.code}`
			}
		},
		onSessionLinkClick: {
			default() {
				return () => {}
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
			sortBy: 'featured',
			openDropdown: null,
			viewMode: 'list',
		}
	},
	computed: {
		speakerCodeFromAny() {
			return (sp) => {
				if (!sp) return null
				if (typeof sp === 'string') return sp
				return sp.code || null
			}
		},
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
				featured: m.featured || 'Featured',
				sessions: m.sessions || 'Sessions',
				view_profile: m.view_profile || 'View speaker profile',
				view_list: m.view_list || 'Switch to list view',
				view_details: m.view_details || 'Switch to details view',
				clear: m.clear || 'Clear',
				reset_all_filters: m.reset_all_filters || 'Reset all filters',
			}
		},
		hasActiveFilters() {
			return Boolean(this.searchQuery) || this.selectedLanguages.length > 0 || this.selectedTracks.length > 0
		},
		sortOptions() {
			return [
				{ value: 'featured', label: this.t.featured },
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
		resolvedSessions() {
			if (!this.scheduleData) return []
			return this.scheduleData.sessions || []
		},
		availableTracks() {
			if (!this.scheduleData) return []
			return this.scheduleData.schedule?.tracks || []
		},
		availableLanguages() {
			const locales = (this.scheduleData?.schedule?.content_locales || []).filter(Boolean)
			if (locales.length) return [...new Set(locales)].sort()
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
			const talks = this.resolvedSessions.length ? this.resolvedSessions : this.rawTalks
			return (schedule?.speakers || []).map(speaker => {
				const speakerTalks = this.resolvedSessions.length
					? talks.filter(sess => (sess.speakers || []).some(sp => this.speakerCodeFromAny(sp) === speaker.code))
					: talks.filter(t => (t.speakers || []).some(sp => this.speakerCodeFromAny(sp) === speaker.code))
				return {
					...speaker,
					sessions: speakerTalks,
				}
			})
		},
		viewToggleTitle() {
			return this.viewMode === 'list' ? this.t.view_details : this.t.view_list
		},
		trackFilteredSpeakers() {
			if (!this.selectedTracks.length) return this.resolvedSpeakers
			return this.resolvedSpeakers.filter(speaker =>
				(speaker.sessions || []).some(s => this.selectedTracks.includes(s?.track?.id ?? s?.track))
			)
		},
		languageFilteredSpeakers() {
			if (!this.selectedLanguages.length) return this.trackFilteredSpeakers
			const fallbackLocale = this.scheduleData?.schedule?.content_locales?.[0] || null
			return this.trackFilteredSpeakers.filter(speaker => {
				return (speaker.sessions || []).some(s => {
					const sessionLocale = s?.content_locale || fallbackLocale
					if (!sessionLocale) return false
					return this.selectedLanguages.some(sel => localesMatch(sel, sessionLocale))
				})
			})
		},
		sortedSpeakers() {
			const speakers = [...this.languageFilteredSpeakers]
			if (this.sortBy === 'featured') {
				return speakers.sort((a, b) => {
					const af = a.is_featured ? 1 : 0
					const bf = b.is_featured ? 1 : 0
					if (af !== bf) return bf - af
					const ap = Number.isFinite(a.featured_position) ? a.featured_position : 1e9
					const bp = Number.isFinite(b.featured_position) ? b.featured_position : 1e9
					if (ap !== bp) return ap - bp
					return (a.name || '').localeCompare(b.name || '')
				})
			}
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
		getSessionLink(session) {
			const base = (this.eventUrl || '').replace(/\/?$/, '/')
			return session?.id ? `${base}talk/${session.id}/` : '#'
		},
		onSessionClick(event, session) {
			this.onSessionLinkClick(event, session)
		},
		getSessionStyle(session) {
			return {
				'--session-color': session?.track?.color || 'var(--pretalx-clr-primary)'
			}
		},
		formatLanguageLabel(code) {
			if (!code) return ''
			const uiLang = localStorage.getItem('userLanguage') || 'en'
			try {
				return new Intl.DisplayNames([uiLang], { type: 'language' }).of(code) || code
			} catch {
				return code
			}
		},
		formatSessionSlot(session) {
			const tz = this.scheduleData?.timezone
			const hasAmPm = this.scheduleData?.hasAmPm
			if (!tz || !session?.start || !session?.end) return ''
			const start = moment.isMoment(session.start) ? session.start : moment.tz(session.start, tz)
			const end = moment.isMoment(session.end) ? session.end : moment.tz(session.end, tz)
			const fmt = hasAmPm ? 'h:mm A' : 'HH:mm'
			return `${start.clone().tz(tz).format(fmt)} - ${end.clone().tz(tz).format(fmt)}`
		},
		formatSessionDateTime(session) {
			const tz = this.scheduleData?.timezone
			const hasAmPm = this.scheduleData?.hasAmPm
			if (!tz || !session?.start) return ''
			const start = moment.isMoment(session.start) ? session.start : moment.tz(session.start, tz)
			const fmt = hasAmPm ? 'MMM D, YYYY h:mm A' : 'MMM D, YYYY HH:mm'
			return start.clone().tz(tz).format(fmt)
		},
		toggleDropdown(name) {
			this.openDropdown = this.openDropdown === name ? null : name
		},
		clearAllFilters() {
			this.searchQuery = ''
			this.selectedLanguages = []
			this.selectedTracks = []
			this.openDropdown = null
		},
		toggleView() {
			this.viewMode = this.viewMode === 'list' ? 'details' : 'list'
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
		min-width: 0
		width: 100%
		max-width: 100%
		box-sizing: border-box
		.search-box
			display: flex
			align-items: center
			gap: 8px
			border: 1px solid #ddd
			border-radius: 6px
			padding: 6px 10px
			background: #fff
			flex: 1 1 260px
			min-width: 220px
			max-width: 100%
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
				min-width: 0
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
		.filter-group, .sort-group, .view-toggle
			flex: 0 1 auto
			min-width: 0
			position: relative
			.dropdown-wrapper
				position: relative
				max-width: 100%
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
			min-width: 0
			max-width: 100%
			overflow: hidden
			text-overflow: ellipsis
			color: #555
			.btn-label
				flex: 1
				min-width: 0
				overflow: hidden
				text-overflow: ellipsis
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
				flex-shrink: 0
				min-width: 18px
				height: 18px
				border-radius: 9px
				background: var(--pretalx-clr-primary, #3aa57c)
				color: #fff
				font-size: 11px
				font-weight: 600
				padding: 0 4px
			&.clear-filters-btn
				padding: 6px 10px
				justify-content: center
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
			max-width: 360px
			box-sizing: border-box
			max-height: 260px
			overflow-y: auto
			overflow-x: hidden
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
				min-width: 0
				white-space: normal
				overflow-wrap: anywhere
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
			@media (max-width: 420px)
				max-width: 90vw
		.sort-group
			.dropdown-menu
				left: auto
				right: 0
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
	.speakers-details
		display: flex
		flex-direction: column
		padding: 16px
		gap: 12px

		.featured-speakers-grid
			display: flex
			flex-wrap: wrap
			justify-content: center
			gap: 18px

		.featured-speaker-column
			width: 320px
			max-width: 100%

		.featured-speaker-card
			margin: 0
			border-radius: 6px
			overflow: hidden
			background: $clr-white
			border: 1px solid $clr-grey-300

		.featured-speaker-summary
			cursor: pointer
			list-style: none
			&::-webkit-details-marker
				display: none

			.thumbnail
				margin: 0
				padding: 0
				border: none
				background: transparent
				img
					width: 100%
					aspect-ratio: 1 / 1
					object-fit: cover
					border-radius: 6px
					display: block
				.caption
					padding: 10px 6px 12px
					h4
						margin: 8px 0 0
						color: $clr-primary-text-light
						font-size: 22px
						font-weight: 600
						line-height: 1.2
					p
						margin: 4px 0 0
						color: $clr-secondary-text-light
						font-size: 12px
						line-height: 1.35
						display: -webkit-box
						-webkit-line-clamp: 3
						-webkit-box-orient: vertical
						overflow: hidden

		.avatar-placeholder
			width: 100%
			aspect-ratio: 1 / 1
			display: flex
			align-items: center
			justify-content: center
			background: $clr-grey-100
			color: $clr-grey-500
			svg
				width: 45%
				height: 45%

		.featured-speaker-details
			margin-top: 8px
			padding: 12px
			background: $clr-grey-100
			border-top: 1px solid $clr-grey-300

		.featured-speaker-bio
			color: $clr-primary-text-light
			font-size: 13px
			line-height: 1.55
			white-space: pre-wrap

		.featured-speaker-divider
			margin: 12px 0 8px
			border-color: $clr-grey-300

		.featured-speaker-sessions
			margin-top: 0
			padding: 0
			h4
				margin: 0 0 10px
				color: $clr-primary-text-light
				font-size: 16px
				font-weight: 600

		.featured-speaker-session
			margin-bottom: 12px
			&:last-child
				margin-bottom: 0

		.featured-speaker-session-time
			display: block
			color: $clr-secondary-text-light
			margin-bottom: 4px
			font-size: 13px
			line-height: 1.35
			font-weight: 600

		.featured-speaker-session-link
			display: block
			background-color: var(--session-color, var(--pretalx-clr-primary))
			color: $clr-white
			border-radius: 4px
			padding: 9px 11px
			text-decoration: none
			&:hover
				opacity: 0.92
				text-decoration: none

		.featured-speaker-session-slot
			display: block
			font-size: 12px
			line-height: 1.2
			margin-bottom: 2px
			opacity: 0.92

		.featured-speaker-session-title
			display: block
			font-size: 14px
			font-weight: 600
			line-height: 1.3

		.featured-speaker-profile-link
			margin-top: 12px
			text-align: right
			a
				color: var(--pretalx-clr-primary, var(--clr-primary))
				text-decoration: none
				&:hover
					text-decoration: underline
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
