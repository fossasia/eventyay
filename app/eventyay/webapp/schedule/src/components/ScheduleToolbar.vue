<template lang="pug">
.c-schedule-toolbar(:class="{'mobile-filters-open': mobileFiltersOpen, 'mobile-more-open': mobileMoreOpen}")
	.version-warning-banner(v-if="!isFeaturedPage && showVersionWarningBanner", ref="versionBanner")
		span.version-warning-text {{ versionWarningText }}
		a.current-version-link(v-if="currentScheduleUrl && !isWipPreview", :href="currentScheduleUrl")
			|  {{ t.go_to_current_version }}
	.toolbar-row(ref="toolbarRow")
		.toolbar-left
			button.toolbar-btn.mobile-toggle-btn.mobile-filter-toggle.icon-only(
				class="tooltip-align-left"
				@click="toggleMobileFilters",
				:class="{active: mobileFiltersOpen || effectiveHasActiveFilters}",
				:aria-expanded="mobileFiltersOpen ? 'true' : 'false'",
				:aria-label="t.filters")
				svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					line(x1="4" y1="6" x2="20" y2="6")
					line(x1="7" y1="12" x2="17" y2="12")
					line(x1="10" y1="18" x2="14" y2="18")
				span.mobile-toggle-badge(v-if="effectiveHasActiveFilters")
			.toolbar-filters(:class="{open: mobileFiltersOpen}", ref="mobileFiltersPanel")
				template(v-for="group in nonLanguageFilterGroups", :key="group.refKey")
					.filter-dropdown-area(:ref="'filterDrop_' + group.refKey")
						button.toolbar-btn(
							:aria-label="group.title",
							@click="toggleFilterDropdown(group.refKey)")
							span.filter-title
								span.filter-title-text {{ group.title }}
								span.filter-dot(v-if="selectedCount(group) > 0")
							svg.chevron-icon(:class="{open: openFilterDropdowns[group.refKey]}", viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
								path(d="M6 9l6 6 6-6")
						.filter-dropdown-menu(v-if="openFilterDropdowns[group.refKey]")
							template(v-if="group.data.length")
								label.filter-dropdown-item(v-for="item in group.data", :key="item.value")
									input.filter-checkbox(type="checkbox", :checked="item.selected", @change="toggleFilter(item)")
									span.track-color-dot(v-if="item.color", :style="{backgroundColor: item.color}")
									span.filter-dropdown-label(:style="item.color ? {'--track-color': item.color} : {}") {{ item.label }}
							.filter-dropdown-empty(v-else) No {{ group.title.toLowerCase() }} available
				.recording-filter-area(v-if="showRecordingFilter", ref="recordingDropdown")
					button.toolbar-btn.icon-only.recording-btn(
						:class="{active: recordingModel !== 'all'}",
						@click="toggleRecordingDropdown",
						@keydown.esc.prevent.stop="closeRecordingDropdown",
						:aria-label="t.filter_by_recording",
						:aria-expanded="recordingOpen ? 'true' : 'false'",
						aria-haspopup="menu")
						svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round")
							path(d="M4 7a2 2 0 012-2h8l2 2h2a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2V7z")
							path(d="M15 12l5-3v6l-5-3z")
					.recording-dropdown-menu(v-if="recordingOpen", role="menu", @keydown.esc.prevent.stop="closeRecordingDropdown", @keydown.down.prevent.stop="focusNextRecordingOption", @keydown.up.prevent.stop="focusPrevRecordingOption")
						button.recording-item(
							ref="recordingOptionButtons",
							:class="{active: recordingModel === 'all'}",
							role="menuitemradio",
							:aria-checked="recordingModel === 'all' ? 'true' : 'false'",
							@click="selectRecording('all')") {{ t.all_sessions }}
						button.recording-item(
							ref="recordingOptionButtons",
							:class="{active: recordingModel === 'yes'}",
							role="menuitemradio",
							:aria-checked="recordingModel === 'yes' ? 'true' : 'false'",
							@click="selectRecording('yes')") {{ t.recorded_only }}
						button.recording-item(
							ref="recordingOptionButtons",
							:class="{active: recordingModel === 'no'}",
							role="menuitemradio",
							:aria-checked="recordingModel === 'no' ? 'true' : 'false'",
							@click="selectRecording('no')") {{ t.not_recorded }}
			.filter-dropdown-area.language-filter-area(v-if="languageGroup", ref="filterDrop_language")
				button.toolbar-btn.icon-only(
					:aria-label="languageGroup.title",
					@click="toggleFilterDropdown(languageGroup.refKey)")
					span.filter-title.filter-icon-title
						svg.tb-icon(viewBox="0 0 24 24", fill="currentColor", aria-hidden="true")
							path(d="M12.87 15.07l-2.54-2.51c.86-1.02 1.52-2.12 1.99-3.28H14V7h-4V5H8v2H4v2h7.17c-.39 1.17-.96 2.27-1.7 3.25-.48-.63-.9-1.31-1.25-2.03H6.1c.5 1.09 1.17 2.14 2 3.11L3 20h2l5-5 3.11 3.11.76-3.04z")
							path(d="M15.5 11h-2L9 22h2l1-3h4l1 3h2l-3.5-11zm-2.3 6 .8-2.8.8 2.8h-1.6z")
						span.filter-dot(v-if="selectedCount(languageGroup) > 0")
				.filter-dropdown-menu(v-if="openFilterDropdowns[languageGroup.refKey]")
					template(v-if="languageGroup.data.length")
						label.filter-dropdown-item(v-for="item in languageGroup.data", :key="item.value")
							input.filter-checkbox(type="checkbox", :checked="item.selected", @change="toggleFilter(item)")
							span.filter-dropdown-label {{ item.label }}
					.filter-dropdown-empty(v-else) No {{ languageGroup.title.toLowerCase() }} available
			button.toolbar-btn.icon-only.fav-toggle(
				v-if="favsCount",
				:disabled="!favsCount",
				:aria-label="t.starred",
				:aria-pressed="onlyFavs ? 'true' : 'false'",
				@click="$emit('toggleFavs')")
				svg.star-icon(viewBox="0 0 24 24", aria-hidden="true")
					polygon(
						:style="onlyFavs ? {fill: '#FFA000', stroke: '#FFA000'} : {fill: 'none', stroke: '#B0B0B0'}"
						points="14.43,10 12,2 9.57,10 2,10 8.18,14.41 5.83,22 12,17.31 18.18,22 15.83,14.41 22,10"
					)
			button.toolbar-btn.icon-only.clear-filters-btn(v-if="hasActiveFilters", :aria-label="t.reset_all_filters", @click="$emit('resetFilters')")
				svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round")
					line(x1="4" y1="4" x2="20" y2="4")
					line(x1="7" y1="9" x2="17" y2="9")
					line(x1="10" y1="14" x2="14" y2="14")
					path(d="M17 17l4 4m0-4l-4 4")
			.sort-area(v-if="sessionsMode", ref="sortDropdown")
				button.toolbar-btn.icon-only.sort-btn(
					@click="sortOpen = !sortOpen",
					:class="{open: sortOpen}",
					:aria-label="t.sort_by",
					:aria-expanded="sortOpen ? 'true' : 'false'",
					aria-haspopup="menu")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round")
						line(x1="4", y1="6", x2="8", y2="6")
						line(x1="4", y1="12", x2="14", y2="12")
						line(x1="4", y1="18", x2="20", y2="18")
						line(x1="18", y1="3", x2="18", y2="15")
						polyline(points="15 12 18 15 21 12")
				.sort-dropdown-menu(v-if="sortOpen", role="menu", @keydown.esc.prevent.stop="sortOpen = false")
					button.sort-item(
						v-for="opt in resolvedSortOptions",
						:key="opt.value",
						:class="{active: sortModel === opt.value}",
						role="menuitemradio",
						:aria-checked="sortModel === opt.value ? 'true' : 'false'",
						@click="selectSort(opt.value)") {{ opt.label }}
					.sort-menu-divider
					.template-sort-inclusion
						.sort-inclusion-row
							span.sort-inclusion-label {{ t.sort_include_room }}
							button.sort-toggle-slider(type="button", :class="{on: includeRoomSortKeyModel}", role="menuitemcheckbox", :aria-label="t.sort_include_room", :aria-checked="includeRoomSortKeyModel ? 'true' : 'false'", @click.prevent.stop="toggleRoomSort")
								span.toggle-slider(aria-hidden="true")
						.sort-inclusion-row
							span.sort-inclusion-label {{ t.sort_include_datetime }}
							button.sort-toggle-slider(type="button", :class="{on: includeDateSortKeyModel}", role="menuitemcheckbox", :aria-label="t.sort_include_datetime", :aria-checked="includeDateSortKeyModel ? 'true' : 'false'", @click.prevent.stop="toggleDatetimeSort")
								span.toggle-slider(aria-hidden="true")
						.sort-inclusion-row(v-if="popularitySortAvailable")
							span.sort-inclusion-label {{ t.sort_include_popularity }}
							button.sort-toggle-slider(type="button", :class="{on: includePopularitySortKeyModel}", role="menuitemcheckbox", :aria-label="t.sort_include_popularity", :aria-checked="includePopularitySortKeyModel ? 'true' : 'false'", @click.prevent.stop="togglePopularitySort")
								span.toggle-slider(aria-hidden="true")
			button.toolbar-btn.sessions-toggle(v-if="!isFeaturedPage", :class="{active: sessionsMode}", @click="$emit('toggleSessionsMode')", :title="sessionsMode ? t.cal : t.list", :aria-label="sessionsMode ? t.cal : t.list")
				template(v-if="sessionsMode")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						rect(x="3", y="4", width="18", height="18", rx="2", ry="2")
						line(x1="16", y1="2", x2="16", y2="6")
						line(x1="8", y1="2", x2="8", y2="6")
						line(x1="3", y1="10", x2="21", y2="10")
				template(v-else)
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round")
						line(x1="8", y1="6", x2="21", y2="6")
						line(x1="8", y1="12", x2="21", y2="12")
						line(x1="8", y1="18", x2="21", y2="18")
						line(x1="3", y1="6", x2="3.01", y2="6")
						line(x1="3", y1="12", x2="3.01", y2="12")
						line(x1="3", y1="18", x2="3.01", y2="18")
				span.sessions-toggle-label {{ sessionsMode ? t.cal : t.list }}
		.toolbar-center(v-if="!isListView && days && days.length > 1", ref="dayNavCenter")
			button.day-arrow(v-if="showDayArrows", :disabled="dayWindowStart <= 0", @click="shiftDays(-1)", :title="t.previous_days", :aria-label="t.previous_days")
				svg(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					path(d="M15 18l-6-6 6-6")
			button.day-btn(
				v-for="day in visibleDays",
				:key="day.id",
				:class="{active: currentDay === day.id}",
				@click="$emit('selectDay', day.id)")
				| {{ day.label }}
			button.day-arrow(v-if="showDayArrows", :disabled="dayWindowStart + dayWindowSize >= days.length", @click="shiftDays(1)", :title="t.next_days", :aria-label="t.next_days")
				svg(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					path(d="M9 18l6-6-6-6")
		.toolbar-right
			.search-area(ref="searchArea")
				.search-compact(:class="{expanded: searchExpanded}")
					button.toolbar-btn.icon-only.search-toggle(@click="toggleSearch", :aria-label="t.search")
						svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
							circle(cx="11", cy="11", r="8")
							line(x1="21", y1="21", x2="16.65", y2="16.65")
					input.search-input(v-if="searchExpanded", ref="searchInput", :value="searchQuery", @input="$emit('update:searchQuery', $event.target.value)", :placeholder="t.search_placeholder", @keydown.esc="closeSearch")
					button.search-clear(v-if="searchExpanded && searchQuery", @click="$emit('update:searchQuery', ''); $refs.searchInput.focus()", :aria-label="t.clear_search")
						svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
							path(d="M18 6L6 18M6 6l12 12")

			button.toolbar-btn.icon-only.fullscreen-quick.tooltip-align-right(v-if="showFullscreen", @click="toggleFullscreen", :aria-label="isFullscreen ? t.exit_fullscreen : t.fullscreen")
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
			button.toolbar-btn.mobile-toggle-btn.mobile-more-toggle(
				@click="toggleMobileMore",
				:class="{active: mobileMoreOpen}",
				:aria-expanded="mobileMoreOpen ? 'true' : 'false'",
				:aria-label="t.more")
				svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
					line(x1="4" y1="7" x2="20" y2="7")
					line(x1="4" y1="12" x2="20" y2="12")
					line(x1="4" y1="17" x2="20" y2="17")
			.toolbar-right-quick
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
				.exporter-area(v-if="resolvedExporters.length || exportsDisabled")
					.exporter-dropdown(ref="exportDropdown")
						button.toolbar-btn.icon-only.tooltip-align-right(
							:class="{disabled: exportsDisabled}",
							@click="!exportsDisabled && (exportOpen = !exportOpen)",
							:aria-label="exportsDisabled ? publicOnlyFeatureHint : t.add_to_calendar",
							:aria-expanded="exportOpen ? 'true' : 'false'",
							aria-haspopup="menu")
							svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round")
								rect(x="3" y="4" width="18" height="18" rx="2" ry="2")
								line(x1="16" y1="2" x2="16" y2="6")
								line(x1="8" y1="2" x2="8" y2="6")
								line(x1="3" y1="10" x2="21" y2="10")
								line(x1="12" y1="14" x2="12" y2="18")
								line(x1="10" y1="16" x2="14" y2="16")
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
			.toolbar-secondary(:class="{open: mobileMoreOpen}", ref="mobileMorePanel")
				.version-area(v-if="!isFeaturedPage && (versionOptions.length || changelogUrl || isWipPreview)")
					.version-dropdown(ref="versionDropdown")
						button.toolbar-btn.version-btn.tooltip-align-right(
							:class="{disabled: isWipPreview}",
							@click="!isWipPreview && (versionOpen = !versionOpen)",
							:aria-label="isWipPreview ? publicOnlyFeatureHint : undefined"
						)
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
				.density-area(ref="densityDropdown")
					button.toolbar-btn.icon-only.density-btn(
						@click="densityOpen = !densityOpen",
						:aria-label="currentTimeDensityLabel",
						:aria-expanded="densityOpen ? 'true' : 'false'",
						aria-haspopup="menu")
						svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", stroke-linecap="round", stroke-linejoin="round")
							line(x1="6" y1="6" x2="18" y2="6")
							line(x1="6" y1="18" x2="18" y2="18")
							line(x1="6" y1="12" x2="18" y2="12")
							polyline(points="12 9 12 6")
							polyline(points="12 15 12 18")
							polyline(points="10 9 12 7 14 9")
							polyline(points="10 15 12 17 14 15")
					.density-menu(v-if="densityOpen", role="menu", @keydown.esc.prevent.stop="densityOpen = false")
						button.density-item(
							v-for="opt in timeDensityOptions",
							:key="opt.value",
							:class="{active: timeDensityMinutes === opt.value}",
							role="menuitemradio",
							:aria-checked="timeDensityMinutes === opt.value ? 'true' : 'false'",
							@click="selectTimeDensity(opt.value)") {{ opt.label }}
				button.toolbar-btn.icon-only(v-if="showPrint", @click="printSchedule", :aria-label="t.print")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
						polyline(points="6 9 6 2 18 2 18 9")
						path(d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2")
						rect(x="6", y="14", width="12", height="8")
				button.toolbar-btn.icon-only.fullscreen-desktop.tooltip-align-right(v-if="showFullscreen", @click="toggleFullscreen", :aria-label="isFullscreen ? t.exit_fullscreen : t.fullscreen")
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
const FA_SVG_MAP = {
	'fa-calendar': '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
	'fa-code': '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
	'fa-google': '<circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="M8 12h8"/>',
	'fa-users': '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87"/><path d="M16 3.13a4 4 0 010 7.75"/>',
	'fa-question-circle': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
	'fa-question-circle-o': '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
}

const STACKED_TOOLBAR_MAX_WIDTH = 1024

export default {
	name: 'ScheduleToolbar',
	inject: {
		translationMessages: { default: () => ({}) },
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
		,
		showRecordingFilter: { type: Boolean, default: false },
		recordingFilter: { type: String, default: 'all' },
		sortBy: { type: String, default: 'title' },
		includeRoomSortKey: { type: Boolean, default: false },
		includeDateSortKey: { type: Boolean, default: false },
		includePopularitySortKey: { type: Boolean, default: false },
		popularityFeatureEnabled: { type: Boolean, default: false },
		popularitySortAvailable: { type: Boolean, default: false },
		exportsDisabled: { type: Boolean, default: false },
		sortOptions: { type: Array, default: () => ['title', 'title_desc'] },
		timeDensityMinutes: { type: Number, default: 30 },
		isFeaturedPage: { type: Boolean, default: false },
		isListView: { type: Boolean, default: false }
	},
	emits: ['fullscreen-change', 'toggleFavs', 'resetFilters', 'saveTimezone', 'update:currentTimezone', 'update:searchQuery', 'update:recordingFilter', 'update:sortBy', 'update:includeRoomSortKey', 'update:includeDateSortKey', 'update:includePopularitySortKey', 'filterToggle', 'selectDay', 'toggleSessionsMode', 'setTimeDensityMinutes'],
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
			dayWindowStart: 0,
			maxVisibleDays: Infinity,
			recordingOpen: false,
			sortOpen: false,
			densityOpen: false,
			mobileFiltersOpen: false,
			mobileMoreOpen: false
		}
	},
	computed: {
		effectiveHasActiveFilters() {
			const groupActive = (this.filterGroups || []).some(group =>
				group.refKey !== 'language' && Array.isArray(group.data) && group.data.some(item => item.selected)
			);
			const recordingActive = this.showRecordingFilter && this.recordingModel !== 'all';
			return groupActive || recordingActive;
		},
		t() {
			const m = this.translationMessages || {}
			return {
				no_matching_options: m.no_matching_options || 'Sorry, no matching options.',
				other_timezones: m.other_timezones || 'Other Timezones',
				view_changelog: m.view_changelog || 'View Changelog',
				go_to_current_version: m.go_to_current_version || 'Go to current version',
				reset_all_filters: m.reset_all_filters || 'Reset all filters',
				sort_by: m.sort_by || 'Sort',
				sort_by_room: m.sort_by_room || 'By room',
				sort_by_title: m.sort_by_title || 'A–Z',
				sort_by_title_desc: m.sort_by_title_desc || 'Z–A',
				sort_by_popularity: m.sort_by_popularity || 'Most popular',
					starred: m.starred || 'Starred',
				print: m.print || 'Print',
				fullscreen: m.fullscreen || 'Fullscreen',
				exit_fullscreen: m.exit_fullscreen || 'Exit Fullscreen',
				latest: m.latest || 'Latest',
				version_warning_editable: m.version_warning_editable || 'You are currently viewing the editable schedule version, which is unreleased and may change at any time.',
				version_warning_wip: m.version_warning_wip || 'You are currently viewing the unreleased schedule preview. It may change at any time and is not visible to the public.',
				version_warning_old: m.version_warning_old || 'You are currently viewing an older schedule version.',
				add_to_calendar: m.add_to_calendar || 'Add to calendar',
				public_schedule_only: m.public_schedule_only || 'Only available on the public schedule once a schedule is released and public.',
				export: m.export || 'Export',
				current: m.current || 'current',
				list_view: m.list_view || 'List View',
				calendar_view: m.calendar_view || 'Calendar View',
				search: m.search || 'Search',
				clear_search: m.clear_search || 'Clear search',
				search_placeholder: m.search_placeholder || 'Search sessions…',
				previous_days: m.previous_days || 'Previous days',
				next_days: m.next_days || 'Next days',
				filter_by_recording: m.filter_by_recording || 'Filter by recording',
				all_sessions: m.all_sessions || 'All sessions',
				recorded_only: m.recorded_only || 'Recorded only',
				not_recorded: m.not_recorded || 'Not recorded',
				sort_include_room: m.sort_include_room || 'Include room',
				sort_include_datetime: m.sort_include_datetime || 'Include datetime',
				sort_include_popularity: m.sort_include_popularity || 'Most popular first',
				filters: m.filters || 'Filters',
				more: m.more || 'More',
				density_compact_view: m.density_compact_view || 'compact view',
				density_default_view: m.density_default_view || 'default view',
				density_comfortable_view: m.density_comfortable_view || 'comfortable view',
				minutes: m.minutes || 'min',
				list: (m.list_view || 'List').replace(' View', ''),
				cal: (m.calendar_view || 'Cal').replace('endar View', '').replace(' View', ''),
			}
		},
		timeDensityOptions() {
			const minText = this.t.minutes || 'min'
			return [
				{ value: 5, label: `5 ${minText}` },
				{ value: 15, label: `15 ${minText}` },
				{ value: 30, label: `30 ${minText}` },
				{ value: 60, label: `60 ${minText}` },
			]
		},
		currentTimeDensityLabel() {
			const current = this.timeDensityOptions.find(o => o.value === this.timeDensityMinutes)
			return current ? current.label : '30 min'
		},
		sortModel: {
			get() { return this.sortBy },
			set(value) { this.$emit('update:sortBy', value) }
		},
		includeRoomSortKeyModel: {
			get() { return this.includeRoomSortKey },
			set(value) { this.$emit('update:includeRoomSortKey', !!value) }
		},
		includeDateSortKeyModel: {
			get() { return this.includeDateSortKey },
			set(value) { this.$emit('update:includeDateSortKey', !!value) }
		},
		includePopularitySortKeyModel: {
			get() { return this.includePopularitySortKey },
			set(value) { this.$emit('update:includePopularitySortKey', !!value) }
		},
		resolvedSortOptions() {
			const allowed = Array.isArray(this.sortOptions) ? this.sortOptions : []
			const labelMap = {
				title: this.t.sort_by_title,
				title_desc: this.t.sort_by_title_desc,
				popularity: this.t.sort_by_popularity,
			}
			return allowed
				.filter(v => ['title', 'title_desc', 'popularity'].includes(v))
				.filter(v => v !== 'popularity' || this.popularitySortAvailable)
				.map(v => ({ value: v, label: labelMap[v] || v }))
		},
		currentSortLabel() {
			const current = this.resolvedSortOptions.find(o => o.value === this.sortModel)
			return current ? current.label : this.t.sort_by_title
		},
		resolvedExporters() {
			let list = this.exporters || []
			if (this.isFeaturedPage) {
				list = list.filter(exp => !exp.identifier.includes('-my') && !exp.identifier.includes('my-') && exp.identifier !== 'faved.ics')
			}
			return list
		},
		isWipPreview() {
			if (this.version === 'wip') {
				return true
			}
			if (typeof window !== 'undefined') {
				return window.location.pathname.includes('/schedule/v/wip/')
			}
			return false
		},
		showVersionWarningBanner() {
			if (this.isWipPreview) {
				return true
			}
			return Boolean(this.version && !this.isCurrent)
		},
		publicOnlyFeatureHint() {
			return this.t.public_schedule_only
		},
		languageGroup() {
			return (this.filterGroups || []).find(g => g.refKey === 'language') || null
		},
		nonLanguageFilterGroups() {
			return (this.filterGroups || []).filter(g => g.refKey !== 'language')
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
			if (this.isWipPreview) {
				return this.t.version_warning_wip
			}
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
			const seen = new Set()
			const result = []
			const candidates = this.availableTimezones.length ? this.availableTimezones : []
			const addTz = (tz) => {
				if (!tz || pinnedIds.has(tz) || seen.has(tz)) return
				seen.add(tz)
				result.push(tz)
			}
			for (const tz of candidates) addTz(tz)
			addTz(this.scheduleTimezone)
			addTz(this.userTimezone)
			return result
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
		recordingModel: {
			get() { return this.recordingFilter || 'all' },
			set(value) { this.$emit('update:recordingFilter', value) }
		},
		dayWindowSize() {
			if (!this.days || this.days.length <= 1) return 0
			if (!Number.isFinite(this.maxVisibleDays) || this.maxVisibleDays >= this.days.length) {
				return this.days.length
			}
			return Math.max(1, this.maxVisibleDays)
		},
		showDayArrows() {
			return Boolean(this.days && this.days.length > 1 && this.days.length > this.dayWindowSize)
		},
		visibleDays() {
			if (!this.days || this.days.length <= 1) return []
			return this.days
				.slice(this.dayWindowStart, this.dayWindowStart + this.dayWindowSize)
				.map(day => ({
					id: day.format('YYYY-MM-DD'),
					label: day.format('ddd D MMM')
				}))
		}
	},
	watch: {
		currentDay() {
			this.ensureCurrentDayVisible()
		},
		days: {
			immediate: true,
			handler() {
				this.$nextTick(() => this.updateDayNavigation())
			}
		},
		showDayArrows() {
			this.ensureCurrentDayVisible()
		},
		searchExpanded() {
			this.$nextTick(() => this.updateDayNavigation())
		}
	},
	mounted() {
		document.addEventListener('click', this.outsideClick, true)
		document.addEventListener('fullscreenchange', this.onFullscreenChange)
		if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
			this._stackedToolbarMq = window.matchMedia(`(max-width: ${STACKED_TOOLBAR_MAX_WIDTH}px)`)
			this._onStackedToolbarMqChange = () => {
				this.$nextTick(() => this.updateDayNavigation())
			}
			if (typeof this._stackedToolbarMq.addEventListener === 'function') {
				this._stackedToolbarMq.addEventListener('change', this._onStackedToolbarMqChange)
			} else if (typeof this._stackedToolbarMq.addListener === 'function') {
				this._stackedToolbarMq.addListener(this._onStackedToolbarMqChange)
			}
		}
		this.$nextTick(() => {
			this.updateVersionBannerHeight()
			this.updateToolbarHeight()
			if (typeof ResizeObserver !== 'undefined') {
				this._versionBannerResizeObserver = new ResizeObserver(() => {
					this.scheduleToolbarLayoutUpdate()
				})
				if (this.$refs.versionBanner) this._versionBannerResizeObserver.observe(this.$refs.versionBanner)
				this._versionBannerResizeObserver.observe(this.$el)
				if (this.$refs.toolbarRow) {
					this._versionBannerResizeObserver.observe(this.$refs.toolbarRow)
					for (const selector of ['.toolbar-left', '.toolbar-center', '.toolbar-right']) {
						const el = this.$refs.toolbarRow.querySelector(selector)
						if (el) this._versionBannerResizeObserver.observe(el)
					}
				}
			}
			this.updateDayNavigation()
		})
	},
	beforeUnmount() {
		document.removeEventListener('click', this.outsideClick, true)
		document.removeEventListener('fullscreenchange', this.onFullscreenChange)
		if (this._stackedToolbarMq && this._onStackedToolbarMqChange) {
			if (typeof this._stackedToolbarMq.removeEventListener === 'function') {
				this._stackedToolbarMq.removeEventListener('change', this._onStackedToolbarMqChange)
			} else if (typeof this._stackedToolbarMq.removeListener === 'function') {
				this._stackedToolbarMq.removeListener(this._onStackedToolbarMqChange)
			}
		}
		if (this._toolbarLayoutRaf) {
			cancelAnimationFrame(this._toolbarLayoutRaf)
			this._toolbarLayoutRaf = null
		}
		this._versionBannerResizeObserver?.disconnect?.()
	},
	methods: {
		scheduleToolbarLayoutUpdate() {
			if (this._toolbarLayoutRaf) return
			this._toolbarLayoutRaf = requestAnimationFrame(() => {
				this._toolbarLayoutRaf = null
				this.updateVersionBannerHeight()
				this.updateToolbarHeight()
				this.updateDayNavigation()
			})
		},
		updateVersionBannerHeight() {
			const host = this.$el?.parentElement
			if (!host) return
			const bannerEl = this.$refs.versionBanner
			const height = bannerEl ? bannerEl.getBoundingClientRect().height : 0
			host.style.setProperty('--pretalx-version-warning-height', `${height}px`)
		},
		updateToolbarHeight() {
			const host = this.$el?.parentElement
			if (!host) return
			const height = this.$el ? this.$el.getBoundingClientRect().height : 0
			// We only want the height of the toolbar portion (excluding the banner which is handled separately)
			const bannerEl = this.$refs.versionBanner
			const bannerHeight = bannerEl ? bannerEl.getBoundingClientRect().height : 0
			const toolbarHeight = height - bannerHeight
			host.style.setProperty('--pretalx-toolbar-height', `${toolbarHeight}px`)
		},
		formatVersionLabel(version) {
			if (!version) return ''
			return version.startsWith('v') ? version : 'v' + version
		},
		outsideClick(event) {
			let path
			if (typeof event.composedPath === 'function') {
				path = event.composedPath()
			} else if (Array.isArray(event.path) && event.path.length > 0) {
				path = event.path
			} else {
				path = []
				let node = event.target || null
				while (node) {
					path.push(node)
					node = node.parentNode
				}
			}
			const exportEl = this.$refs.exportDropdown
			const exportDropdownEl = Array.isArray(exportEl) ? exportEl[0] : exportEl
			if (exportDropdownEl && !path.includes(exportDropdownEl)) {
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
			if (this.$refs.recordingDropdown && !path.includes(this.$refs.recordingDropdown)) {
				this.recordingOpen = false
			}
			if (this.$refs.sortDropdown && !path.includes(this.$refs.sortDropdown)) {
				this.sortOpen = false
			}
			if (this.$refs.densityDropdown && !path.includes(this.$refs.densityDropdown)) {
				this.densityOpen = false
			}
			if (this.searchExpanded && this.$refs.searchArea && !path.includes(this.$refs.searchArea)) {
				this.closeSearch()
			}
			if (!path.includes(this.$el)) {
				this.mobileFiltersOpen = false
				this.mobileMoreOpen = false
			}
		},
		toggleMobileFilters() {
			this.mobileFiltersOpen = !this.mobileFiltersOpen
			if (this.mobileFiltersOpen) {
				this.mobileMoreOpen = false
			}
		},
		toggleMobileMore() {
			this.mobileMoreOpen = !this.mobileMoreOpen
			if (this.mobileMoreOpen) {
				this.mobileFiltersOpen = false
			}
		},
		selectTimeDensity(value) {
			this.$emit('setTimeDensityMinutes', value)
			this.densityOpen = false
			this.$nextTick(() => this.$refs.densityDropdown?.querySelector?.('button')?.focus?.())
		},
		selectSort(value) {
			this.sortModel = value
			this.sortOpen = false
			this.$nextTick(() => this.$refs.sortDropdown?.querySelector?.('button')?.focus?.())
		},
		toggleRoomSort() {
			const newVal = !this.includeRoomSortKey
			this.$emit('update:includeRoomSortKey', newVal)
		},
		toggleDatetimeSort() {
			const newVal = !this.includeDateSortKey
			this.$emit('update:includeDateSortKey', newVal)
		},
		togglePopularitySort() {
			const newVal = !this.includePopularitySortKey
			this.$emit('update:includePopularitySortKey', newVal)
		},
		toggleRecordingDropdown() {
			this.recordingOpen = !this.recordingOpen
			if (this.recordingOpen) {
				this.$nextTick(() => this.focusSelectedRecordingOption())
			}
		},
		closeRecordingDropdown() {
			this.recordingOpen = false
		},
		selectRecording(value) {
			this.recordingModel = value
			this.recordingOpen = false
			this.$nextTick(() => this.$refs.recordingDropdown?.querySelector?.('button')?.focus?.())
		},
		getRecordingOptionButtons() {
			const btns = this.$refs.recordingOptionButtons
			if (!btns) return []
			return Array.isArray(btns) ? btns : [btns]
		},
		focusSelectedRecordingOption() {
			const buttons = this.getRecordingOptionButtons()
			if (!buttons.length) return
			const idx = ['all', 'yes', 'no'].indexOf(this.recordingModel)
			const target = buttons[Math.max(0, idx)] || buttons[0]
			target?.focus?.()
		},
		focusNextRecordingOption() {
			const buttons = this.getRecordingOptionButtons()
			if (!buttons.length) return
			const idx = buttons.findIndex(b => b === document.activeElement)
			const next = buttons[(idx + 1 + buttons.length) % buttons.length] || buttons[0]
			next?.focus?.()
		},
		focusPrevRecordingOption() {
			const buttons = this.getRecordingOptionButtons()
			if (!buttons.length) return
			const idx = buttons.findIndex(b => b === document.activeElement)
			const prev = buttons[(idx - 1 + buttons.length) % buttons.length] || buttons[buttons.length - 1]
			prev?.focus?.()
		},
		toggleFilterDropdown(refKey) {
			const nextState = !this.openFilterDropdowns[refKey]
			const next = {}
			for (const key of Object.keys(this.openFilterDropdowns || {})) {
				next[key] = false
			}
			next[refKey] = nextState
			this.openFilterDropdowns = next

			if (nextState) {
				this.recordingOpen = false
				this.sortOpen = false
				this.densityOpen = false
				this.exportOpen = false
				this.versionOpen = false
				if (this.tzOpen) {
					this.tzOpen = false
					this.tzSearch = ''
				}
				this.searchExpanded = false
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
		ensureCurrentDayVisible() {
			if (!this.days || this.days.length <= 1) return
			if (!this.showDayArrows) {
				this.dayWindowStart = 0
				return
			}
			const idx = this.days.findIndex(d => d.format('YYYY-MM-DD') === this.currentDay)
			if (idx < 0) return
			const size = this.dayWindowSize
			if (idx < this.dayWindowStart) {
				this.dayWindowStart = Math.max(0, idx)
			} else if (idx >= this.dayWindowStart + size) {
				this.dayWindowStart = Math.min(this.days.length - size, idx - size + 1)
			}
		},
		async updateDayNavigation() {
			if (this._updatingDayNav) return
			const center = this.$refs.dayNavCenter
			if (!center || !this.days?.length || this.days.length <= 1) {
				this.maxVisibleDays = Infinity
				return
			}

			this._updatingDayNav = true
			try {
				const fits = () => {
					const available = this.getDayNavAvailableWidth()
					if (available <= 0) return false
					return center.scrollWidth <= available + 1
				}

				this.maxVisibleDays = this.days.length
				await this.$nextTick()
				await new Promise(resolve => requestAnimationFrame(resolve))
				if (fits()) {
					this.dayWindowStart = 0
					return
				}

				let lo = 1
				let hi = this.days.length - 1
				let bestFit = 1
				while (lo <= hi) {
					const mid = Math.floor((lo + hi) / 2)
					this.maxVisibleDays = mid
					await this.$nextTick()
					if (fits()) {
						bestFit = mid
						lo = mid + 1
					} else {
						hi = mid - 1
					}
				}

				this.maxVisibleDays = bestFit
				await this.$nextTick()
				this.ensureCurrentDayVisible()
			} finally {
				this._updatingDayNav = false
			}
		},
		getDayNavAvailableWidth() {
			const center = this.$refs.dayNavCenter
			if (!center) return 0
			return Math.max(0, center.clientWidth)
		},
		shiftDays(direction) {
			const step = Math.max(1, this.dayWindowSize - 1)
			const delta = direction < 0 ? -step : step
			const max = Math.max(0, this.days.length - this.dayWindowSize)
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
	flex-direction: column
	align-items: stretch
	justify-content: flex-start
	gap: 0
	font-size: 14px
	position: sticky
	top: var(--pretalx-sticky-top-offset, 0px)
	z-index: 100
	background-color: $clr-white
	box-sizing: border-box
	.version-warning-banner
		color: #856404
		background: #fff3cd
		padding: 6px 10px
		font-size: 13px
		line-height: 1.3
		display: flex
		align-items: center
		gap: 4px
		justify-content: center
		flex-wrap: wrap
		.version-warning-text
			color: inherit
			font-size: inherit
			line-height: inherit
		.current-version-link
			color: #856404
			font-weight: 600
			font-size: 13px
			text-decoration: underline
			white-space: nowrap
			&:hover
				color: #533f03
	.toolbar-row
		display: flex
		align-items: center
		justify-content: space-between
		flex-wrap: nowrap
		gap: 8px
		min-height: 40px
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
		.mobile-toggle-btn
			display: none
		.toolbar-filters
			display: flex
			align-items: center
			gap: 6px
			min-width: 0
		.fav-toggle
			display: flex
			align-items: center
			gap: 6px
			white-space: nowrap
			position: relative
			&.disabled
				opacity: 0.6
			&:disabled
				opacity: 0.5
				cursor: default
				&:hover
					background-color: transparent
			.star-icon
				width: 18px
				height: 18px
		.clear-filters-btn
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
				accent-color: var(--track-color, var(--pretalx-clr-primary, #3aa57c))
				margin: 0
			.track-color-dot
				width: 10px
				height: 10px
				border-radius: 50%
				flex-shrink: 0
			.filter-dropdown-label
				white-space: nowrap
		.filter-title
			position: relative
			display: inline-block
		.filter-dot
			position: absolute
			right: -4px
			top: -4px
			display: block
			width: 7px
			height: 7px
			border-radius: 50%
			background: var(--pretalx-clr-primary, #3aa57c)
			pointer-events: none
			flex-shrink: 0
		.filter-icon-title
			.tb-icon
				display: block
		.filter-dropdown-empty
			padding: 10px 14px
			color: #999
			font-size: 13px
			font-style: italic
		.recording-filter-area
			position: relative
			flex-shrink: 0
			.recording-dropdown-menu
				position: absolute
				left: 0
				top: 100%
				background: #fff
				min-width: 180px
				box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
				border-radius: 4px
				z-index: 200
				padding: 4px 0
				display: flex
				flex-direction: column
				gap: 0
				.recording-item
					border: none
					background: transparent
					text-align: left
					padding: 8px 12px
					font-size: 13px
					cursor: pointer
					color: #333
					&:hover, &:focus
						background-color: #f5f5f5
					&.active
						font-weight: 600
		.sort-area
			position: relative
			flex-shrink: 0
		.sort-btn
			svg.tb-icon
				transition: transform 0.2s ease
			&.open
				svg.tb-icon
					transform: rotate(180deg)
		.sort-dropdown-menu
			position: absolute
			left: 0
			top: 100%
			background: #fff
			min-width: 180px
			box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
			border-radius: 4px
			z-index: 200
			padding: 4px 0
			display: flex
			flex-direction: column
			gap: 0
			.sort-item
				border: none
				background: transparent
				text-align: left
				padding: 8px 12px
				font-size: 13px
				cursor: pointer
				color: #333
				&:hover, &:focus
					background-color: #f5f5f5
				&.active
					font-weight: 600
			.template-sort-inclusion
				padding: 8px 12px 6px
				.sort-inclusion-row
					display: flex
					align-items: center
					justify-content: space-between
					gap: 12px
					&:not(:last-child)
						margin-bottom: 8px
				.sort-inclusion-label
					font-size: 13px
					color: #333
				.sort-toggle-slider
					display: inline-flex
					align-items: center
					justify-content: center
					padding: 0
					border: 0
					background: transparent
					cursor: pointer
					user-select: none
					&.on .toggle-slider
						background-color: var(--pretalx-clr-primary, #3aa57c)
						&::after
							transform: translateX(20px)
					.toggle-slider
						display: inline-block
						width: 44px
						height: 24px
						background-color: #ccc
						border-radius: 12px
						transition: background-color 0.3s
						position: relative
						&::after
							content: ''
							display: block
							width: 20px
							height: 20px
							background-color: #fff
							border-radius: 50%
							transition: transform 0.3s
							position: absolute
							top: 2px
							left: 2px
			.sort-menu-divider
				height: 1px
				background: #ececec
				margin: 6px 0
	.toolbar-center
		display: flex
		align-items: center
		gap: 2px
		flex-shrink: 1
		min-width: 0
		overflow: hidden
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
			flex-shrink: 0
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
		position: relative
		.mobile-toggle-btn
			display: none
		.toolbar-right-quick
			display: flex
			align-items: center
			gap: 4px
		.sessions-toggle
			padding: 0 5px
		.fullscreen-quick
			display: none
			padding: 0 5px
		.toolbar-secondary
			display: flex
			align-items: center
			gap: 4px
		.sessions-toggle-menu
			display: none
		.density-area
			display: flex
			position: relative
			flex-shrink: 0
			.density-menu
				position: absolute
				right: 0
				top: 100%
				background: #fff
				min-width: 180px
				box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
				border-radius: 4px
				z-index: 200
				padding: 4px 0
				display: flex
				flex-direction: column
				gap: 0
				.density-item
					border: none
					background: transparent
					text-align: left
					padding: 8px 12px
					font-size: 13px
					cursor: pointer
					color: #333
					&:hover, &:focus
						background-color: #f5f5f5
					&.active
						font-weight: 600
		.sessions-toggle
			white-space: nowrap
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
					&[aria-label]
						position: relative
						&::after
							content: attr(aria-label)
							position: absolute
							left: 50%
							bottom: calc(100% + 6px)
							transform: translateX(-50%) translateY(2px)
							opacity: 0
							pointer-events: none
							background-color: rgba(0, 0, 0, 0.87)
							color: #fff
							padding: 4px 8px
							border-radius: 4px
							font-size: 12px
							line-height: 1.2
							white-space: nowrap
							z-index: 1000
						&:hover::after, &:focus-visible::after
							opacity: 1
							transform: translateX(-50%) translateY(0)
							transition: opacity 0.05s ease, transform 0.05s ease
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
		height: 28px
		padding: 0 6px
		border-radius: 2px
		font-size: 14px
		display: flex
		align-items: center
		gap: 4px
		&.icon-only[aria-label]
			position: relative
			&::after
				content: attr(aria-label)
				position: absolute
				left: 50%
				top: calc(100% + 6px)
				transform: translateX(-50%) translateY(-2px)
				opacity: 0
				pointer-events: none
				background-color: rgba(0, 0, 0, 0.87)
				color: #fff
				padding: 4px 8px
				border-radius: 4px
				font-size: 12px
				line-height: 1.2
				white-space: nowrap
				z-index: 1000
			&:hover::after, &:focus-visible::after
				opacity: 1
				transform: translateX(-50%) translateY(0)
				transition: opacity 0.05s ease, transform 0.05s ease
		&.disabled
			opacity: 0.5
			cursor: not-allowed
			&[aria-label]
				position: relative
				&::after
					content: attr(aria-label)
					position: absolute
					top: calc(100% + 6px)
					right: 0
					transform: translateY(-2px)
					opacity: 0
					pointer-events: none
					background-color: rgba(0, 0, 0, 0.87)
					color: #fff
					padding: 6px 8px
					border-radius: 4px
					font-size: 12px
					line-height: 1.3
					white-space: normal
					width: max-content
					max-width: 280px
					z-index: 1000
				&:hover::after, &:focus-visible::after
					opacity: 1
					transform: translateY(0)
					transition: opacity 0.05s ease, transform 0.05s ease
		&.icon-only.tooltip-align-left[aria-label]
			&::after
				left: 0
				transform: translateY(-2px)
			&:hover::after, &:focus-visible::after
				transform: translateY(0)
		&.icon-only.tooltip-align-right[aria-label]
			&::after
				left: auto
				right: 0
				transform: translateY(-2px)
			&:hover::after, &:focus-visible::after
				transform: translateY(0)
		&.icon-only
			padding: 0 5px
			gap: 3px
		&:hover
			background-color: rgba(0, 0, 0, 0.05)
		&.sessions-toggle.active
			color: var(--pretalx-clr-primary, #3aa57c)
			font-weight: 600
			border-radius: 4px
		.sessions-toggle-label
			margin-left: 4px
			font-size: 13px
			font-weight: 500
		&.recording-btn
			position: relative
		&.recording-btn.active::before
			content: ''
			position: absolute
			right: 2px
			top: 2px
			width: 5px
			height: 5px
			aspect-ratio: 1 / 1
			border-radius: 50%
			background: var(--pretalx-clr-primary, #3aa57c)
			border: 1px solid #fff
			z-index: 2

		&.fav-toggle.icon-only[aria-label]::after
			left: 0
			transform: translateY(-2px)
		&.fav-toggle.icon-only[aria-label]:hover::after, &.fav-toggle.icon-only[aria-label]:focus-visible::after
			transform: translateY(0)
		&.mobile-toggle-btn
			border: 1px solid #d8d8d8
			border-radius: 6px
			padding: 0 6px
			gap: 6px
			.mobile-toggle-label
				font-size: 12px
				font-weight: 600
			.mobile-toggle-badge
				width: 7px
				height: 7px
				border-radius: 50%
				background: var(--pretalx-clr-primary, #3aa57c)
			&.active
				border-color: var(--pretalx-clr-primary, #3aa57c)
				color: var(--pretalx-clr-primary, #3aa57c)
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

@media (min-width: 1025px)
	.c-schedule-toolbar
		.toolbar-row
			display: grid
			grid-template-columns: auto minmax(0, 1fr) auto
			align-items: center
			gap: 8px
		.toolbar-left
			flex: none
			min-width: 0
		.toolbar-center
			flex: none
			justify-content: center
			min-width: 0
			max-width: 100%
		.toolbar-right
			flex: none
			min-width: 0
			justify-self: end

@media (max-width: 1024px)
	.c-schedule-toolbar
		.toolbar-row
			display: grid
			grid-template-columns: minmax(0, 1fr) auto
			grid-template-areas: 'left right' 'center center'
			align-items: center
			height: auto
			min-height: 40px
			padding: 6px 8px
			gap: 6px
			.toolbar-left
				grid-area: left
				position: relative
				flex: none
				min-width: 0
				max-width: 100%
				gap: 4px
				.language-filter-area
					display: inline-flex
				.mobile-toggle-btn
					display: inline-flex
				.toolbar-filters
					display: none
					position: absolute
					left: 0
					top: calc(100% + 8px)
					z-index: 240
					padding: 8px
					background: #fff
					border: 1px solid #e5e5e5
					border-radius: 10px
					box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12)
					width: max-content
					max-width: 94vw
					max-height: 80vh
					flex-wrap: nowrap
					overflow-x: auto
					overflow-y: auto
					-webkit-overflow-scrolling: touch
					align-items: flex-start
					gap: 8px
					&.open
						display: flex
					.filter-dropdown-area,
					.recording-filter-area,
					.sort-area
						position: relative
						display: flex
						flex-direction: column
						align-items: stretch
					.filter-dropdown-menu,
					.recording-dropdown-menu,
					.sort-dropdown-menu
						position: static
						min-width: 100%
						max-height: 350px
						overflow-y: auto
						overflow-x: hidden
						box-shadow: none
						border: 1px solid #e8e8e8
						border-radius: 8px
						background: #fff
						padding: 4px 0
						.filter-dropdown-item,
						.recording-item,
						.sort-item
							padding: 8px 12px
							font-size: 14px
						.filter-checkbox
							width: 14px
							height: 14px
			.toolbar-center
				grid-area: center
				flex: none
				width: 100%
				max-width: 100%
				justify-content: center
				padding-top: 2px
				.day-btn
					padding: 4px 8px
					font-size: 12px
			.day-arrow svg
				width: 16px
				height: 16px
		.toolbar-right
			grid-area: right
			flex: 0 0 auto
			flex-wrap: nowrap
			gap: 4px
			align-items: center
			justify-content: flex-end
			max-width: 100%
			.fullscreen-quick
				display: inline-flex
				order: 98
			.mobile-toggle-btn
				display: inline-flex
				order: 99
				margin-left: 2px
			.toolbar-right-quick
				display: flex
				align-items: center
				gap: 2px
			.toolbar-secondary
				display: none
				position: absolute
				right: 0
				top: calc(100% + 8px)
				z-index: 240
				padding: 8px
				background: #fff
				border: 1px solid #e5e5e5
				border-radius: 10px
				box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12)
				width: max-content
				max-width: 94vw
				max-height: 70vh
				flex-direction: row
				flex-wrap: nowrap
				align-items: center
				overflow-x: auto
				overflow-y: auto
				-webkit-overflow-scrolling: touch
				gap: 6px
				&.open
					display: flex
					align-items: flex-start
				.density-area
					display: flex
					order: -1
				.fullscreen-desktop
					display: none
				> *
					min-width: 0
					flex: 0 0 auto
				.toolbar-btn,
				.version-btn,
				.version-item,
				.density-item,
				.tz-option
					white-space: nowrap
					overflow: hidden
					text-overflow: ellipsis
				.version-dropdown,
				.exporter-dropdown,
				.density-area,
				.timezone-compact
					position: relative
					display: flex
					flex-direction: column
					align-items: stretch
				.version-menu,
				.exporter-menu,
				.density-menu,
				.tz-dropdown-menu
					position: static
					min-width: 100%
					max-height: 300px
					overflow-y: auto
					overflow-x: hidden
					box-shadow: none
					border: 1px solid #e8e8e8
					border-radius: 8px
					background: #fff
					padding: 4px 0
				.sessions-toggle-menu
					display: flex
					justify-content: flex-start

@media (max-width: 600px)
	.c-schedule-toolbar
		.filter-title,
		.filter-title-text,
		.filter-dot,
		.filter-dropdown-label,
		label.filter-dropdown-item,
		button.toolbar-btn,
		button.toolbar-btn span,
		button.toolbar-btn .filter-title,
		button.toolbar-btn .filter-title-text {
			color: #111
		}
		svg.tb-icon,
		svg.chevron-icon {
			stroke: #111
			color: #111
			fill: none
		}
		.language-filter-area svg.tb-icon {
			fill: #111
			color: #111
			stroke: none
		}
		.sessions-toggle-label
			display: none
		.sessions-toggle[aria-label]
			position: relative
			&::after
				content: attr(aria-label)
				position: absolute
				left: 50%
				top: calc(100% + 6px)
				transform: translateX(-50%) translateY(-2px)
				opacity: 0
				pointer-events: none
				background-color: rgba(0, 0, 0, 0.87)
				color: #fff
				padding: 4px 8px
				border-radius: 4px
				font-size: 12px
				line-height: 1.2
				white-space: nowrap
				z-index: 1000
			&:hover::after, &:focus-visible::after
				opacity: 1
				transform: translateX(-50%) translateY(0)
				transition: opacity 0.05s ease, transform 0.05s ease
		.toolbar-right
			.fullscreen-quick
				display: inline-flex
				order: 98
		.toolbar-btn.icon-only[aria-label]::after
			display: none
		.toolbar-row
			padding: 6px
			.toolbar-center
				.day-btn
					font-size: 13px
		.toolbar-right
			.search-area .search-compact .search-input
				width: 130px
				font-size: 13px
			.toolbar-right-quick
				.timezone-label
					display: none
			.toolbar-btn,
			.toolbar-btn.icon-only,
			button.toolbar-btn,
			button.toolbar-btn.icon-only {
				color: #111
			}
		.toolbar-btn
			padding: 0 6px
			height: 30px
			font-size: 13px

		.toolbar-btn.mobile-toggle-btn
			padding: 0 6px
			gap: 4px

@media print
	.c-schedule-toolbar
		display: none
</style>
