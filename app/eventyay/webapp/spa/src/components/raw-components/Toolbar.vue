 <template lang="pug">
.c-schedule-toolbar
	.toolbar-left
		template(v-for="group in filterGroups", :key="group.refKey")
			.filter-dropdown-area(:ref="'filterDrop_' + group.refKey")
				button.toolbar-btn(@click="toggleFilterDropdown(group.refKey)")
					span {{ group.title }}
					span.filter-badge(v-if="selectedCount(group) > 0") {{ selectedCount(group) }}
					svg.chevron-icon(:class="{open: openFilterDropdowns[group.refKey]}", viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M6 9l6 6 6-6")
				.filter-dropdown-menu(v-if="openFilterDropdowns[group.refKey]")
					template(v-if="group.data.length")
						label.filter-dropdown-item(v-for="item in group.data", :key="item.value")
							input.filter-checkbox(type="checkbox", :checked="item.selected", @change="toggleFilter(item)")
							span.track-color-dot(v-if="item.color", :style="{backgroundColor: item.color}")
							span.filter-dropdown-label(:style="item.color ? {'--track-color': item.color} : {}") {{ item.label }}
					.filter-dropdown-empty(v-else) No {{ group.title.toLowerCase() }} available
		button.toolbar-btn.sessions-toggle(:class="{active: sessionsMode}", @click="$emit('toggleSessionsMode')", :title="sessionsMode ? t.calendar_view : t.list_view")
			template(v-if="sessionsMode")
				svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					rect(x="3", y="4", width="18", height="18", rx="2", ry="2")
					line(x1="16", y1="2", x2="16", y2="6")
					line(x1="8", y1="2", x2="8", y2="6")
					line(x1="3", y1="10", x2="21", y2="10")
				|  {{ t.calendar_view }}
			template(v-else)
				svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					line(x1="8", y1="6", x2="21", y2="6")
					line(x1="8", y1="12", x2="21", y2="12")
					line(x1="8", y1="18", x2="21", y2="18")
					line(x1="3", y1="6", x2="3.01", y2="6")
					line(x1="3", y1="12", x2="3.01", y2="12")
					line(x1="3", y1="18", x2="3.01", y2="18")
				|  {{ t.list_view }}
		button.toolbar-btn.fav-toggle(v-if="favsCount", :class="{active: onlyFavs}", @click="$emit('toggleFavs')")
			svg.star-icon(viewBox="0 0 24 24")
				polygon(
					:style="{fill: '#FFA000', stroke: '#FFA000'}"
					points="14.43,10 12,2 9.57,10 2,10 8.18,14.41 5.83,22 12,17.31 18.18,22 15.83,14.41 22,10"
				)
			|  {{ favsCount }}
		button.toolbar-btn.reset-btn(v-if="hasActiveFilters", @click="$emit('resetFilters')", :title="t.reset_all_filters")
			svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				path(d="M18 6L6 18M6 6l12 12")
	.toolbar-center(v-if="days && days.length > 1")
		button.day-arrow(:disabled="dayWindowStart <= 0", @click="shiftDays(-2)")
			svg(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				path(d="M15 18l-6-6 6-6")
		button.day-btn(
			v-for="day in visibleDays",
			:key="day.id",
			:class="{active: currentDay === day.id}",
			@click="$emit('selectDay', day.id)")
			| {{ day.label }}
		button.day-arrow(:disabled="dayWindowStart + 3 >= days.length", @click="shiftDays(2)")
			svg(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				path(d="M9 18l6-6-6-6")
	.toolbar-right
		.timezone-area(v-if="!inEventTimezone")
			.timezone-compact(ref="timezoneDropdown")
				button.toolbar-btn.tz-btn(@click="toggleTzDropdown", :title="timezoneModel")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						circle(cx="12", cy="12", r="10")
						line(x1="2", y1="12", x2="22", y2="12")
						path(d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z")
					span.tz-label {{ timezoneModel.replace(/^.*\//, '').replace(/_/g, ' ') }}
					svg.chevron-icon(:class="{open: tzOpen}", viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M6 9l6 6 6-6")
				.tz-dropdown-menu(v-if="tzOpen")
					.tz-section-label Pinned
					.tz-option(
						v-for="option in pinnedTimezones",
						:key="option.id",
						:class="{ active: timezoneModel === option.id }",
						@click="selectTimezone(option.id); tzOpen = false"
					)
						span {{ option.label }}
					.tz-divider
					.tz-section-label {{ t.other_timezones }}
					input.tz-search(v-model="tzSearch", placeholder="Search timezones...", @click.stop)
					.tz-scroll
						.tz-option(
							v-for="option in filteredOtherTimezones",
							:key="option.id",
							:class="{ active: timezoneModel === option.id }",
							@click="selectTimezone(option.id); tzOpen = false"
						)
							span {{ option.label }}
		.timezone-label(v-else) {{ scheduleTimezone }}
		.version-area(v-if="versionOptions.length || changelogUrl")
			.version-dropdown(ref="versionDropdown")
				button.toolbar-btn.version-btn(@click="versionOpen = !versionOpen")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M12 8v4l3 3")
						circle(cx="12", cy="12", r="10")
					span.version-current {{ currentVersionLabel }}
					svg.chevron-icon(:class="{open: versionOpen}", viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M6 9l6 6 6-6")
				.version-menu(v-if="versionOpen")
					a.version-item(
						v-for="v in versionOptions",
						:key="v.version",
						:href="v.url",
						:class="{active: v.version === version}"
					)
						span {{ formatVersionLabel(v.version) }}
						span.version-current-badge(v-if="v.isCurrent") {{ t.current }}
					.version-menu-divider(v-if="changelogUrl && versionOptions.length")
					a.version-item.changelog-link(v-if="changelogUrl", :href="changelogUrl")
						svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
							path(d="M4 19.5A2.5 2.5 0 016.5 17H20")
							path(d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z")
						span {{ t.view_changelog }}
		.version-warning(v-if="version && !isCurrent")
			small.text-muted {{ versionWarningText }}
			a.current-version-link(v-if="currentScheduleUrl", :href="currentScheduleUrl")
				|  {{ t.go_to_current_version }}
		.exporter-area(v-if="resolvedExporters.length")
			.exporter-dropdown(ref="exportDropdown")
				button.toolbar-btn(@click="exportOpen = !exportOpen")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4")
						polyline(points="7 10 12 15 17 10")
						line(x1="12", y1="15", x2="12", y2="3")
					|  {{ t.export }}
				.exporter-menu(v-if="exportOpen")
					a.exporter-item(
						v-for="exp in resolvedExporters",
						:key="exp.identifier",
						:href="exp.export_url",
						target="_blank",
						@mouseover="hoveredExporter = exp",
						@mouseleave="hoveredExporter = null"
					)
						span.exporter-icon(v-if="exp.icon")
							svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", v-html="faIconSvg(exp.icon)")
						span.exporter-name {{ exp.verbose_name }}
						transition(name="fade")
							.qr-hover(v-if="hoveredExporter === exp && exp.qrcode_svg", v-html="exp.qrcode_svg")
		.search-area(ref="searchArea")
			.search-compact(:class="{expanded: searchExpanded}")
				button.toolbar-btn.search-toggle(@click="toggleSearch", :title="t.search")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						circle(cx="11", cy="11", r="8")
						line(x1="21", y1="21", x2="16.65", y2="16.65")
				input.search-input(v-if="searchExpanded", ref="searchInput", :value="searchQuery", @input="$emit('update:searchQuery', $event.target.value)", :placeholder="t.search_placeholder", @keydown.esc="closeSearch")
				button.search-clear(v-if="searchExpanded && searchQuery", @click="$emit('update:searchQuery', ''); $refs.searchInput.focus()")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						path(d="M18 6L6 18M6 6l12 12")
		button.toolbar-btn(v-if="showPrint", @click="printSchedule", :title="t.print")
			svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				polyline(points="6 9 6 2 18 2 18 9")
				path(d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2")
				rect(x="6", y="14", width="12", height="8")
		button.toolbar-btn(v-if="showFullscreen", @click="toggleFullscreen", :title="isFullscreen ? t.exit_fullscreen : t.fullscreen")
			svg.tb-icon(v-if="!isFullscreen", viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				polyline(points="15 3 21 3 21 9")
				polyline(points="9 21 3 21 3 15")
				line(x1="21", y1="3", x2="14", y2="10")
				line(x1="3", y1="21", x2="10", y2="14")
			svg.tb-icon(v-else, viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
				polyline(points="4 14 10 14 10 20")
				polyline(points="20 10 14 10 14 4")
				line(x1="14", y1="10", x2="21", y2="3")
				line(x1="3", y1="21", x2="10", y2="14")
</template>

<script>
// FA icon name → inline SVG path mapping (shadow DOM blocks external CSS)
const FA_SVG_MAP = {
	'fa-calendar': '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
	'fa-code': '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
	'fa-google': '<circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="M8 12h8"/>',
	'fa-users': '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>',
	'fa-question-circle': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
	'fa-question-circle-o': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
}

export default {
	name: 'ScheduleToolbar',
	inject: {
		translationMessages: { default: () => ({}) }
	},
	props: {
		version: { type: String, default: '' },
		isCurrent: { type: Boolean, default: true },
		changelogUrl: { type: String, default: '' },
		currentScheduleUrl: { type: String, default: '' },
		versions: { type: Array, default: () => [] },
		exporters: { type: Array, default: () => [] },
		filterGroups: { type: Array, default: () => [] },
		showFullscreen: { type: Boolean, default: true },
		showPrint: { type: Boolean, default: true },
		fullscreenTarget: { type: Object, default: null },
		sessionsMode: { type: Boolean, default: false },
		searchQuery: { type: String, default: '' },
		favsCount: { type: Number, default: 0 },
		onlyFavs: { type: Boolean, default: false },
		hasActiveFilters: { type: Boolean, default: false },
		inEventTimezone: { type: Boolean, default: true },
		currentTimezone: String,
		scheduleTimezone: String,
		userTimezone: String,
		days: { type: Array, default: () => [] },
		currentDay: { type: String, default: '' }
	},

	emits: ['fullscreen-change', 'toggleFavs', 'resetFilters', 'saveTimezone', 'update:currentTimezone', 'update:searchQuery', 'filterToggle', 'selectDay', 'toggleSessionsMode'],
	data() {
		return {
			exportOpen: false,
			versionOpen: false,
			tzOpen: false,
			searchExpanded: false,
			tzSearch: '',
			hoveredExporter: null,
			isFullscreen: false,
			openFilterDropdowns: {},
			dayWindowStart: 0
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				no_matching_options: m.no_matching_options || 'Sorry, no matching options.',
				other_timezones: m.other_timezones || 'Other Timezones',
				view_changelog: m.view_changelog || 'View Changelog',
				go_to_current_version: m.go_to_current_version || 'Go to current version',
				reset_all_filters: m.reset_all_filters || 'Reset all filters',
				print: m.print || 'Print',
				fullscreen: m.fullscreen || 'Fullscreen',
				exit_fullscreen: m.exit_fullscreen || 'Exit Fullscreen',
				latest: m.latest || 'Latest',
				version_warning_editable: m.version_warning_editable || 'You are currently viewing the editable schedule version, which is unreleased and may change at any time.',
				version_warning_old: m.version_warning_old || 'You are currently viewing an older schedule version.',
				export: m.export || 'Export',
				current: m.current || 'current',
				list_view: m.list_view || 'List View',
				calendar_view: m.calendar_view || 'Calendar View',
				search: m.search || 'Search',
				search_placeholder: m.search_placeholder || 'Search sessions…',
			}
		},
		resolvedExporters() {
			return this.exporters || []
		},
		currentVersionLabel() {
			if (this.version) return this.formatVersionLabel(this.version)
			return this.t.latest
		},
		versionOptions() {
			if (!this.versions || !this.versions.length) return []
			const currentVersion = this.versions.find(v => v.isCurrent)?.version
			return this.versions.map(v => ({
				...v,
				isCurrent: v.version === currentVersion || v.isCurrent
			}))
		},
		versionWarningText() {
			if (!this.version) {
				return this.t.version_warning_editable
			}
			return this.t.version_warning_old
		},
		availableTimezones() {
			if (typeof Intl?.supportedValuesOf === 'function') {
				return Intl.supportedValuesOf('timeZone') || []
			}
			return []
		},
		pinnedTimezones() {
			const pinned = []
			const seen = new Set()
			const addTimezone = (id, suffix) => {
				if (!id || seen.has(id)) return
				pinned.push({ id, label: `${id} (${suffix})` })
				seen.add(id)
			}
			addTimezone(this.userTimezone, 'local')
			addTimezone(this.scheduleTimezone, 'event')
			return pinned
		},
		otherTimezones() {
			const pinnedIds = new Set(this.pinnedTimezones.map(o => o.id))
			const knownTimezones = this.availableTimezones.length ? [...this.availableTimezones] : []
			for (const tz of [this.scheduleTimezone, this.userTimezone]) {
				if (tz && !knownTimezones.includes(tz)) knownTimezones.push(tz)
			}
			return knownTimezones
				.filter(Boolean)
				.filter(tz => !pinnedIds.has(tz))
				.filter((tz, i, arr) => arr.indexOf(tz) === i)
				.sort((a, b) => a.localeCompare(b))
				.map(tz => ({ id: tz, label: tz }))
		},
		allTimezoneOptions() {
			return [...this.pinnedTimezones, ...this.otherTimezones]
		},
		filteredOtherTimezones() {
			if (!this.tzSearch) return this.otherTimezones
			const q = this.tzSearch.toLowerCase()
			return this.otherTimezones.filter(tz => tz.label.toLowerCase().includes(q))
		},
		timezoneModel: {
			get() { return this.currentTimezone },
			set(value) { this.$emit('update:currentTimezone', value) }
		},
		visibleDays() {
			if (!this.days || this.days.length <= 1) return []
			return this.days
				.slice(this.dayWindowStart, this.dayWindowStart + 3)
				.map(day => ({
					id: day.format('YYYY-MM-DD'),
					label: day.format('ddd D MMM')
				}))
		}
	},
	watch: {
		currentDay(newDay) {
			if (!this.days || this.days.length <= 1) return
			const idx = this.days.findIndex(d => d.format('YYYY-MM-DD') === newDay)
			if (idx < 0) return
			if (idx < this.dayWindowStart) {
				this.dayWindowStart = Math.max(0, idx)
			} else if (idx >= this.dayWindowStart + 3) {
				this.dayWindowStart = Math.min(this.days.length - 3, idx - 2)
			}
		},
		days: {
			immediate: true,
			handler(newDays) {
				if (!newDays || newDays.length <= 1) return
				const idx = newDays.findIndex(d => d.format('YYYY-MM-DD') === this.currentDay)
				if (idx >= 0) {
					this.dayWindowStart = Math.max(0, Math.min(idx, newDays.length - 3))
				}
			}
		}
	},
	mounted() {
		document.addEventListener('click', this.outsideClick, true)
		document.addEventListener('fullscreenchange', this.onFullscreenChange)
	},
	beforeUnmount() {
		document.removeEventListener('click', this.outsideClick, true)
		document.removeEventListener('fullscreenchange', this.onFullscreenChange)
	},
	methods: {
		formatVersionLabel(version) {
			if (!version) return ''
			return version.startsWith('v') ? version : 'v' + version
		},
		outsideClick(event) {
			const path = event.composedPath ? event.composedPath() : [event.target]
			if (this.$refs.exportDropdown && !path.includes(this.$refs.exportDropdown)) {
				this.exportOpen = false
			}
			if (this.$refs.versionDropdown && !path.includes(this.$refs.versionDropdown)) {
				this.versionOpen = false
			}
			if (this.$refs.timezoneDropdown && !path.includes(this.$refs.timezoneDropdown)) {
				if (this.tzOpen) {
					this.tzOpen = false
					this.tzSearch = ''
					this.$emit('saveTimezone')
				}
			}
			for (const key of Object.keys(this.openFilterDropdowns)) {
				const refName = 'filterDrop_' + key
				const el = this.$refs[refName]
				const dropdownEl = Array.isArray(el) ? el[0] : el
				if (dropdownEl && !path.includes(dropdownEl)) {
					this.openFilterDropdowns[key] = false
				}
			}
			if (this.searchExpanded && this.$refs.searchArea && !path.includes(this.$refs.searchArea)) {
				this.closeSearch()
			}
		},
		toggleFilterDropdown(refKey) {
			this.openFilterDropdowns = {
				...this.openFilterDropdowns,
				[refKey]: !this.openFilterDropdowns[refKey]
			}
		},
		selectedCount(group) {
			return group.data.filter(i => i.selected).length
		},
		toggleFullscreen() {
			const target = this.fullscreenTarget || this.$el.closest('.pretalx-schedule') || document.documentElement
			if (!document.fullscreenElement) {
				target.requestFullscreen?.().catch(err => {
					console.error('Fullscreen request failed:', err)
				})
			} else {
				document.exitFullscreen?.()
			}
		},
		onFullscreenChange() {
			this.isFullscreen = !!document.fullscreenElement
			this.$emit('fullscreen-change', this.isFullscreen)
		},
		printSchedule() {
			window.print()
		},
		faIconSvg(icon) {
			if (!icon) return ''
			return FA_SVG_MAP[icon] || '<circle cx="12" cy="12" r="10"/>'
		},
		findTimezoneOption(value) {
			return this.allTimezoneOptions.find(o => o.id === value)
		},
		getTimezoneLabel(option) {
			return option?.label || option || ''
		},
		selectTimezone(value) {
			this.$emit('update:currentTimezone', value)
			this.$emit('saveTimezone')
		},
		toggleTzDropdown() {
			this.tzOpen = !this.tzOpen
			this.tzSearch = ''
		},
		toggleFilter(item) {
			item.selected = !item.selected
			this.$emit('filterToggle', item)
		},
		shiftDays(delta) {
			const max = Math.max(0, this.days.length - 3)
			this.dayWindowStart = Math.max(0, Math.min(max, this.dayWindowStart + delta))
		},
		toggleSearch() {
			this.searchExpanded = !this.searchExpanded
			if (this.searchExpanded) {
				this.$nextTick(() => this.$refs.searchInput?.focus())
			} else {
				this.$emit('update:searchQuery', '')
			}
		},
		closeSearch() {
			this.searchExpanded = false
			this.$emit('update:searchQuery', '')
		}
	}
}
</script>

<style lang="stylus">
.c-schedule-toolbar
	display: flex
	align-items: center
	justify-content: space-between
	flex-wrap: nowrap
	gap: 8px
	font-size: 14px
	position: sticky
	top: var(--pretalx-sticky-top-offset, 0px)
	z-index: 100
	background-color: $clr-white
	height: 40px
	box-sizing: border-box
	.tb-icon
		width: 16px
		height: 16px
		flex-shrink: 0
	.toolbar-left
		display: flex
		align-items: center
		gap: 6px
		flex-wrap: nowrap
		flex: 1
		min-width: 0
		.fav-toggle
			display: flex
			align-items: center
			gap: 4px
			&.active
				border: 2px solid #FFA000
			.star-icon
				width: 18px
				height: 18px
		.reset-btn
			color: #666
		.filter-dropdown-area
			position: relative
		.filter-dropdown-menu
			position: absolute
			left: 0
			top: 100%
			background: #fff
			min-width: 200px
			max-height: 260px
			overflow-y: auto
			box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
			border-radius: 4px
			z-index: 200
			padding: 4px 0
		.filter-dropdown-item
			display: flex
			align-items: center
			gap: 6px
			padding: 6px 12px
			cursor: pointer
			font-size: 13px
			&:hover
				background-color: #f5f5f5
			.filter-checkbox
				accent-color: var(--track-color, var(--clr-primary, #3aa57c))
				margin: 0
			.track-color-dot
				width: 10px
				height: 10px
				border-radius: 50%
				flex-shrink: 0
			.filter-dropdown-label
				white-space: nowrap
		.filter-badge
			font-size: 11px
			background: var(--clr-primary, #3aa57c)
			color: #fff
			padding: 0 6px
			border-radius: 10px
			line-height: 18px
			min-width: 18px
			text-align: center
		.filter-dropdown-empty
			padding: 10px 14px
			color: #999
			font-size: 13px
			font-style: italic
		.sessions-toggle
			white-space: nowrap
	.toolbar-center
		display: flex
		align-items: center
		gap: 2px
		flex-shrink: 0
		.day-arrow
			border: none
			background: transparent
			cursor: pointer
			padding: 2px
			display: flex
			align-items: center
			justify-content: center
			border-radius: 2px
			color: #555
			&:hover:not(:disabled)
				background-color: rgba(0, 0, 0, 0.06)
			&:disabled
				opacity: 0.25
				cursor: default
			svg
				width: 18px
				height: 18px
		.day-btn
			border: none
			background: transparent
			cursor: pointer
			padding: 4px 10px
			border-radius: 3px
			font-size: 13px
			font-weight: 500
			white-space: nowrap
			color: #555
			&:hover
				background-color: rgba(0, 0, 0, 0.05)
			&.active
				background-color: var(--pretalx-clr-primary, #3aa57c)
				color: #fff
				font-weight: 600
	.toolbar-right
		display: flex
		align-items: center
		gap: 4px
		flex-shrink: 0
		flex: 1
		justify-content: flex-end
		.search-area
			position: relative
			display: flex
			align-items: center
			.search-compact
				display: flex
				align-items: center
				gap: 0
				border-radius: 4px
				transition: all 0.2s ease
				&.expanded
					background: #f5f5f5
					border: 1px solid #ddd
				.search-toggle
					flex-shrink: 0
				.search-input
					border: none
					background: transparent
					outline: none
					font-size: 13px
					padding: 4px 4px 4px 0
					width: 140px
					max-width: 180px
					&::placeholder
						color: #999
				.search-clear
					border: none
					background: transparent
					cursor: pointer
					padding: 2px 4px
					display: flex
					align-items: center
					color: #999
					&:hover
						color: #333
					.tb-icon
						width: 14px
						height: 14px
		.timezone-area
			position: relative
			margin-right: 4px
			.timezone-compact
				position: relative
				display: inline-block
			.tz-btn
				gap: 4px
				.tz-label
					font-size: 12px
					color: #555
					white-space: nowrap
					overflow: hidden
					text-overflow: ellipsis
					max-width: 120px
			.tz-dropdown-menu
				position: absolute
				right: 0
				top: 100%
				background: #fff
				width: 260px
				box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18)
				border-radius: 4px
				z-index: 200
				padding: 4px 0
			.tz-section-label
				display: block
				padding: 6px 12px 2px
				font-weight: 600
				font-size: 11px
				color: $clr-secondary-text-light
				text-transform: uppercase
				letter-spacing: 0.03em
			.tz-option
				display: flex
				align-items: center
				padding: 6px 12px
				cursor: pointer
				font-size: 13px
				&:hover
					background-color: #f5f5f5
				&.active
					font-weight: 600
					background-color: #e8f4fd
			.tz-divider
				height: 1px
				background: #e0e0e0
				margin: 4px 0
			.tz-search
				display: block
				box-sizing: border-box
				width: calc(100% - 16px)
				margin: 4px 8px
				padding: 5px 8px
				border: 1px solid #ccc
				border-radius: 3px
				font-size: 13px
				outline: none
				&:focus
					border-color: var(--pretalx-clr-primary, #3aa57c)
			.tz-scroll
				max-height: 200px
				overflow-y: auto
		.timezone-label
			cursor: default
			color: $clr-secondary-text-light
			padding: 4px 8px
			margin-right: 8px
		.version-area
			position: relative
		.version-dropdown
			position: relative
			display: inline-block
		.version-btn
			font-weight: 600
			.version-current
				margin: 0 4px
		.version-menu
			position: absolute
			right: 0
			top: 100%
			background: #fff
			min-width: 180px
			box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
			border-radius: 4px
			z-index: 200
			padding: 4px 0
			max-height: 300px
			overflow-y: auto
		.version-menu-divider
			height: 1px
			background: #e0e0e0
			margin: 4px 0
		.version-item
			display: flex
			align-items: center
			justify-content: space-between
			gap: 8px
			padding: 6px 12px
			color: #333
			text-decoration: none
			cursor: pointer
			&:hover
				background-color: #f5f5f5
			&.active
				font-weight: 600
				background-color: #e8f4fd
			.version-current-badge
				font-size: 11px
				color: #fff
				background: #4caf50
				padding: 1px 6px
				border-radius: 10px
			&.changelog-link
				gap: 6px
				justify-content: flex-start
		.version-warning
			color: #856404
			background: #fff3cd
			padding: 2px 8px
			border-radius: 4px
			font-size: 12px
			display: flex
			align-items: center
			gap: 4px
			.current-version-link
				color: #856404
				font-weight: 600
				font-size: 12px
				text-decoration: underline
				white-space: nowrap
				&:hover
					color: #533f03
		.exporter-area
			position: relative
			.exporter-dropdown
				position: relative
				display: inline-block
			.exporter-menu
				position: absolute
				right: 0
				top: 100%
				background: #fff
				min-width: 280px
				box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
				border-radius: 4px
				z-index: 200
				padding: 4px 0
				white-space: nowrap
			.exporter-item
				display: flex
				align-items: center
				gap: 8px
				padding: 6px 12px
				color: #333
				text-decoration: none
				position: relative
				&:hover
					background-color: #f5f5f5
				.exporter-icon
					width: 20px
					text-align: center
				.qr-hover
					position: absolute
					right: 100%
					top: 0
					padding: 8px
					background: #fff
					border: 1px solid #ddd
					border-radius: 4px
					box-shadow: 2px 2px 8px rgba(0, 0, 0, 0.1)
					z-index: 210
	.toolbar-btn
		border: none
		background: transparent
		cursor: pointer
		height: 32px
		padding: 0 10px
		border-radius: 2px
		font-size: 14px
		display: flex
		align-items: center
		gap: 4px
		&:hover
			background-color: rgba(0, 0, 0, 0.05)
		&.sessions-toggle.active
			background-color: var(--pretalx-clr-primary, #3aa57c)
			color: #fff
			border-radius: 4px
	.fade-enter-active, .fade-leave-active
		transition: opacity 0.3s
	.fade-enter-from, .fade-leave-to
		opacity: 0

.chevron-icon
	width: 14px
	height: 14px
	transition: transform 0.2s
	flex-shrink: 0
	&.open
		transform: rotate(180deg)

@media (max-width: 600px)
	.c-schedule-toolbar
		flex-wrap: wrap
		height: auto
		min-height: 40px
		padding: 4px 6px
		gap: 4px
		.toolbar-left
			order: 1
			flex: 1 1 100%
			overflow-x: auto
			-webkit-overflow-scrolling: touch
			scrollbar-width: none
			&::-webkit-scrollbar
				display: none
		.toolbar-center
			order: 2
			flex: 1 1 auto
			justify-content: center
			.day-btn
				padding: 3px 6px
				font-size: 12px
		.toolbar-right
			order: 3
			flex: 0 0 auto
			gap: 2px
		.toolbar-btn
			padding: 0 6px
			height: 28px
			font-size: 12px

@media print
	.c-schedule-toolbar
		display: none
</style>
       