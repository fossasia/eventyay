<template lang="pug">
.c-auditlog
	.ui-page-header
		bunt-icon-button(@click="$router.push({name: 'organizer'})", :tooltip="$t('Back to Overview')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Logs') }}
		.actions
			.search-bar
				bunt-progress-circular.search-spinner(v-if="loading", size="18", role="status", :aria-label="$t('Loading')")
				i.mdi.mdi-magnify.search-icon(v-else)
				input.search-input(
					type="text",
					name="search",
					:placeholder="$t('Search log')",
					v-model="search",
					autocomplete="off",
					:aria-label="$t('Search log')"
				)
				.scope-toggle
					button.btn-scope(
						type="button",
						:class="{active: searchScope === 'all'}",
						:aria-pressed="searchScope === 'all'",
						:title="$t('Search across all records on the server')",
						@click="setSearchScope('all')"
					) {{ $t('All records') }}
					button.btn-scope(
						type="button",
						:class="{active: searchScope === 'page'}",
						:aria-pressed="searchScope === 'page'",
						:title="$t('Filter only records on current page')",
						@click="setSearchScope('page')"
					) {{ $t('Current page') }}
	.auditlog-list
		.header
			button.timestamp.sortable(
				type="button",
				@click="toggleSort",
				:title="$t('Sort by timestamp')",
				:aria-label="order === 'desc' ? $t('Sort ascending') : $t('Sort descending')"
			)
				span {{ $t('Timestamp') }}
				span.sort-indicator {{ order === 'desc' ? '▼' : '▲' }}
			.user {{ $t('User') }}
			.type {{ $t('Action type') }}
			.data {{ $t('Data') }}
		bunt-progress-circular.main-loading(v-if="entries === null", size="huge", :page="true", role="status", :aria-label="$t('Loading')")
		.empty-state(v-else-if="displayedEntries.length === 0")
			p {{ $t('No audit logs found') }}
		RecycleScroller.tbody.bunt-scrollbar(
			v-else,
			:items="displayedEntries",
			:item-size="38",
			key-field="id",
			v-scrollbar.y=""
		)
			template(#default="{item: entry}")
				div.logentry.table-row(
					:key="entry.id",
					tabindex="0",
					role="button",
					:aria-label="`Log entry ${entry.type}`",
					@click.prevent="detailsPrompt = entry",
					@keydown.enter.self.prevent="detailsPrompt = entry",
					@keydown.space.self.prevent="detailsPrompt = entry"
				)
					.timestamp {{ moment(entry.timestamp).format('L LT') }}
					.user
						template(v-if="entry.user")
							avatar.avatar(v-if="entry.user.profile && (entry.user.profile.display_name || entry.user.profile.avatar)", :user="entry.user", :size="22")
							.name {{ entry.user.profile?.display_name || entry.user.id }}
						.name.empty-user(v-else) –
					.type(:title="entry.type") {{ entry.type }}
					.data(:title="formatData(entry.data)") {{ formatData(entry.data) }}
	.pagination-bar(v-if="entries !== null")
		.record-info
			span(v-if="searchScope === 'page' && search.trim()") {{ $t('Showing') }} {{ displayedEntries.length }} {{ $t('matches on this page (of') }} {{ totalRecords }} {{ $t('total)') }}
			span(v-else-if="totalRecords > 0") {{ $t('Showing') }} {{ recordRangeStart }}–{{ recordRangeEnd }} {{ $t('of') }} {{ totalRecords }} {{ $t('records') }}
			span(v-else) {{ $t('0 records') }}
		.pagination-controls
			.page-size-selector
				span.label {{ $t('Per page:') }}
				.select-wrapper
					select.select-page-size(
						v-model.number="pageSize",
						@change="onPageSizeChange",
						:aria-label="$t('Records per page')"
					)
						option(:value="20") 20
						option(:value="50") 50
						option(:value="100") 100
						option(:value="200") 200
					svg.select-arrow(viewBox="0 0 12 12", width="10", height="10", aria-hidden="true")
						path(d="M2.5 4.5L6 8L9.5 4.5", fill="none", stroke="currentColor", stroke-width="1.5", stroke-linecap="round", stroke-linejoin="round")
			.nav-buttons
				button.btn-nav(
					type="button",
					:disabled="currentPage <= 1 || loading",
					@click="goToPage(1)",
					:title="$t('First page')",
					:aria-label="$t('First page')"
				) «
				button.btn-nav(
					type="button",
					:disabled="currentPage <= 1 || loading",
					@click="goToPage(currentPage - 1)",
					:title="$t('Previous page')",
					:aria-label="$t('Previous page')"
				) ‹
				span.page-indicator {{ $t('Page') }} {{ currentPage }} {{ $t('of') }} {{ totalPages }}
				button.btn-nav(
					type="button",
					:disabled="currentPage >= totalPages || loading",
					@click="goToPage(currentPage + 1)",
					:title="$t('Next page')",
					:aria-label="$t('Next page')"
				) ›
				button.btn-nav(
					type="button",
					:disabled="currentPage >= totalPages || loading",
					@click="goToPage(totalPages)",
					:title="$t('Last page')",
					:aria-label="$t('Last page')"
				) »
	teleport(to="body")
		transition(name="prompt")
			prompt.details-prompt(v-if="detailsPrompt != null", @close="detailsPrompt = null")
				.content
					h2 {{ $t('Log Entry') }}
					.detail-meta
						.meta-item
							span.label {{ $t('Timestamp') }}:
							span.value {{ moment(detailsPrompt.timestamp).format('L LTS') }}
						.meta-item(v-if="detailsPrompt.user")
							span.label {{ $t('User') }}:
							span.value {{ detailsPrompt.user.profile?.display_name || detailsPrompt.user.id }}
						.meta-item
							span.label {{ $t('Action') }}:
							span.value.type-badge {{ detailsPrompt.type }}
					.detail-data
						span.label {{ $t('Data Payload') }}:
						pre {{ JSON.stringify(detailsPrompt.data, null, 2) }}
					.actions
						bunt-button#btn-close-details(@click="detailsPrompt = null") {{ $t('Close') }}
</template>
<script>
import api from 'lib/api'
import moment from 'moment'
import Avatar from 'components/Avatar'
import Prompt from 'components/Prompt'
import debounce from 'lodash/debounce'

export default {
	name: 'AuditLog',
	components: { Avatar, Prompt },
	data() {
		return {
			moment,
			detailsPrompt: null,
			entries: null,
			search: '',
			searchScope: 'all',
			currentPage: 1,
			totalPages: 1,
			totalRecords: 0,
			pageSize: 50,
			order: 'desc',
			loading: false,
			debouncedSearch: null,
			currentRequestId: 0
		}
	},
	computed: {
		displayedEntries() {
			if (!this.entries) return []
			if (this.searchScope === 'page' && this.search.trim()) {
				const q = this.search.trim().toLowerCase()
				return this.entries.filter(entry =>
					entry.user?.profile?.display_name?.toLowerCase()?.includes(q) ||
					String(entry.user?.id || '').toLowerCase().includes(q) ||
					entry.type?.toLowerCase()?.includes(q) ||
					JSON.stringify(entry.data)?.toLowerCase()?.includes(q)
				)
			}
			return this.entries
		},
		recordRangeStart() {
			if (this.totalRecords === 0) return 0
			return (this.currentPage - 1) * this.pageSize + 1
		},
		recordRangeEnd() {
			return Math.min(this.currentPage * this.pageSize, this.totalRecords)
		}
	},
	watch: {
		search() {
			if (this.searchScope === 'all') {
				this.debouncedSearch()
			}
		}
	},
	created() {
		this.debouncedSearch = debounce(() => {
			this.currentPage = 1
			this.fetchEntries()
		}, 300)
		this.ensureConnectedAndFetch()
	},
	beforeUnmount() {
		if (this.debouncedSearch) {
			this.debouncedSearch.cancel()
		}
		if (this._unwatchConnected) {
			this._unwatchConnected()
			this._unwatchConnected = null
		}
	},
	methods: {
		formatData(data) {
			if (!data) return ''
			if (typeof data === 'string') return data
			try {
				return JSON.stringify(data)
			} catch (e) {
				return String(data)
			}
		},
		setSearchScope(scope) {
			if (this.searchScope === scope) return
			this.searchScope = scope
			if (this.debouncedSearch) {
				this.debouncedSearch.cancel()
			}
			if (this.search.trim()) {
				this.currentPage = 1
				this.fetchEntries()
			}
		},
		toggleSort() {
			this.order = this.order === 'desc' ? 'asc' : 'desc'
			this.currentPage = 1
			this.fetchEntries()
		},
		onPageSizeChange() {
			this.currentPage = 1
			this.fetchEntries()
		},
		goToPage(page) {
			if (page < 1 || page > this.totalPages || page === this.currentPage) return
			this.currentPage = page
			this.fetchEntries()
		},
		ensureConnectedAndFetch() {
			if (this.$store.state.connected) {
				return this.fetchEntries()
			}
			this._unwatchConnected = this.$store.watch(
				state => state.connected,
				connected => {
					if (connected) {
						if (this._unwatchConnected) this._unwatchConnected()
						this._unwatchConnected = null
						this.fetchEntries()
					}
				}
			)
		},
		async fetchEntries() {
			const requestId = ++this.currentRequestId
			this.loading = true
			try {
				const payload = {
					page: this.currentPage,
					page_size: this.pageSize,
					order: this.order
				}
				if (this.searchScope === 'all' && this.search.trim()) {
					payload.search = this.search.trim()
					payload.search_term = this.search.trim()
				}
				const res = await api.call('event.auditlog.list', payload)
				if (this.currentRequestId !== requestId) return

				const results = res?.results || []
				this.entries = results
				this.totalRecords = Number(res?.total != null ? res.total : results.length)
				const calculatedPages = Math.max(1, Math.ceil((this.totalRecords || 0) / this.pageSize))
				this.totalPages = Number(res?.total_pages != null ? res.total_pages : calculatedPages)
				this.currentPage = Number(res?.page != null ? res.page : this.currentPage)
			} catch (e) {
				if (this.currentRequestId === requestId) {
					console.error('Failed to fetch audit log entries', e)
					this.entries = []
					this.totalRecords = 0
					this.totalPages = 1
				}
			} finally {
				if (this.currentRequestId === requestId) {
					this.loading = false
				}
			}
		}
	}
}
</script>
<style lang="stylus">
@import 'flex-table'

.c-auditlog
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	background-color: $clr-white

	.ui-page-header
		h1
			font-size: 20px
			font-weight: 600
			color: #0f172a
			margin: 0
			flex: 0 0 auto

		.actions
			display: flex
			align-items: center
			margin-left: auto
			flex-wrap: nowrap

			.search-bar
				display: flex
				align-items: center
				width: 380px
				max-width: 100%
				height: 34px
				border: 1px solid #cbd5e1
				border-radius: 6px
				background-color: #ffffff
				box-sizing: border-box
				padding: 2px 2px 2px 8px
				transition: border-color 0.15s ease, box-shadow 0.15s ease

				&:focus-within
					border-color: $clr-primary
					box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.15)

				.search-icon
					font-size: 18px
					color: #94a3b8
					margin-right: 4px
					flex: none
					line-height: 1
					pointer-events: none
					width: 18px
					height: 18px
					display: inline-flex
					align-items: center
					justify-content: center

				.search-spinner
					margin-right: 4px
					flex: none
					width: 18px
					height: 18px

				.search-input
					flex: 1 1 auto
					min-width: 0
					height: 100%
					border: none
					outline: none
					background: transparent
					padding: 0 4px
					font-size: 12.5px
					color: #1e293b

					&::placeholder
						color: #94a3b8

				.scope-toggle
					display: inline-flex
					align-items: center
					background-color: #f1f5f9
					padding: 2px
					border-radius: 4px
					flex: none
					height: 26px
					box-sizing: border-box

					.btn-scope
						border: none
						background: transparent
						padding: 2px 8px
						font-size: 11.5px
						font-weight: 500
						color: #64748b
						cursor: pointer
						border-radius: 3px
						transition: background-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease
						white-space: nowrap
						line-height: 18px
						display: inline-flex
						align-items: center
						justify-content: center

						&:hover:not(.active)
							color: #0f172a
							background-color: rgba(255, 255, 255, 0.6)

						&.active
							background: #ffffff
							color: $clr-primary
							font-weight: 500
							box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08)

	@media (max-width: 560px)
		.ui-page-header
			height: auto
			min-height: 56px
			flex-wrap: wrap
			padding-top: 8px
			padding-bottom: 8px

			.actions
				flex: 1 1 100%
				min-width: 0
				margin-left: 0

				.search-bar
					width: 100%

	.auditlog-list
		flex-table()
		position: relative
		min-height: 0
		flex: 1
		overflow-x: auto
		overflow-y: hidden
		font-size: 12.5px

		> .header, .tbody .table-row
			height: 38px
			line-height: 38px
			width: 100%
			box-sizing: border-box

		> .header > *, .tbody .table-row > *
			padding: 0 10px
			box-sizing: border-box

		.header
			background-color: $clr-grey-50
			border-bottom: 1px solid #e2e8f0

		.tbody
			flex: 1 1 0
			min-height: 0
			height: 100%
			width: 100%
			overflow-y: auto
			.vue-recycle-scroller__item-wrapper
				width: 100%
			.vue-recycle-scroller__item-view
				width: 100%
			.logentry.table-row
				width: 100%
				box-sizing: border-box

		.logentry
			cursor: pointer
			transition: background-color 0.1s ease
			&:focus-visible
				outline: 2px solid $clr-primary
				outline-offset: -2px

		.timestamp
			width: 140px
			flex: 0 0 140px
			ellipsis()

			&.sortable
				cursor: pointer
				user-select: none
				display: flex
				align-items: center
				gap: 4px
				background: transparent
				border: none
				padding: 0 10px
				font-size: inherit
				font-family: inherit
				font-weight: inherit
				color: inherit
				text-align: left

				&:hover
					color: $clr-primary

				&:focus-visible
					outline: 2px solid $clr-primary
					outline-offset: -2px

				.sort-indicator
					font-size: 10px
					opacity: 0.8

		.user
			width: 170px
			flex: 0 0 170px
			display: flex
			align-items: center

			.avatar
				width: 22px
				height: 22px
				flex-shrink: 0
				margin: 0 6px 0 0

			.name
				flex: auto
				ellipsis()

				&.empty-user
					color: #94a3b8

		.type
			width: 190px
			flex: 0 0 190px
			ellipsis()
			font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace
			font-size: 12px
			color: #1e293b

		.data
			flex: 1 1 auto
			min-width: 0
			ellipsis()
			font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace
			font-size: 12px
			color: #475569

		.main-loading
			margin: 40px auto

		.empty-state
			display: flex
			align-items: center
			justify-content: center
			padding: 48px 16px
			color: #64748b
			font-size: 14px

	.pagination-bar
		display: flex
		align-items: center
		justify-content: space-between
		padding: 6px 16px
		border-top: 1px solid #e2e8f0
		background-color: #f8fafc
		font-size: 12.5px
		color: #475569
		flex: none
		flex-wrap: wrap
		gap: 12px

		.record-info
			font-weight: 500

		.pagination-controls
			display: flex
			align-items: center
			gap: 16px
			flex-wrap: wrap

			.page-size-selector
				display: flex
				align-items: center
				gap: 8px

				.label
					color: #64748b
					font-size: 12.5px
					font-weight: 500

				.select-wrapper
					position: relative
					display: inline-flex
					align-items: center

					.select-page-size
						appearance: none
						-webkit-appearance: none
						-moz-appearance: none
						height: 28px
						line-height: 28px
						padding: 0 26px 0 10px
						border: 1px solid #cbd5e1
						border-radius: 4px
						background-color: #ffffff
						font-size: 12.5px
						font-weight: 600
						color: #334155
						cursor: pointer
						outline: none
						transition: border-color 0.15s ease, box-shadow 0.15s ease

						&:hover
							background-color: #f8fafc
							border-color: #94a3b8

						&:focus
							border-color: $clr-primary
							box-shadow: 0 0 0 2px rgba(33, 150, 243, 0.15)

					.select-arrow
						position: absolute
						right: 8px
						pointer-events: none
						color: #64748b

			.nav-buttons
				display: flex
				align-items: center
				gap: 4px

				.btn-nav
					min-width: 28px
					height: 28px
					display: inline-flex
					align-items: center
					justify-content: center
					border: 1px solid #cbd5e1
					border-radius: 4px
					background: #ffffff
					color: #334155
					font-size: 13px
					font-weight: 600
					cursor: pointer
					transition: all 0.15s ease

					&:hover:not(:disabled)
						background: #f1f5f9
						border-color: #94a3b8
						color: #0f172a

					&:disabled
						opacity: 0.35
						cursor: not-allowed

				.page-indicator
					font-size: 12.5px
					font-weight: 500
					color: #475569
					padding: 0 4px
					white-space: nowrap

.details-prompt
	.prompt-wrapper
		width: 640px !important
		max-width: min(640px, 94vw) !important
		max-height: calc(100vh - 48px) !important
		display: flex
		flex-direction: column
		border-radius: 8px
		overflow: hidden

	.content
		display: flex
		flex-direction: column
		padding: 24px 28px !important
		gap: 16px
		overflow-y: auto
		min-height: 0
		flex: 1 1 auto
		box-sizing: border-box

		h2
			margin: 0
			font-size: 18px
			font-weight: 600
			color: #1e293b

		.detail-meta
			display: flex
			flex-direction: column
			gap: 8px
			background-color: #f8fafc
			padding: 14px 16px
			border-radius: 6px
			border: 1px solid #e2e8f0
			flex-shrink: 0

			.meta-item
				display: flex
				align-items: center
				gap: 10px
				font-size: 13.5px

				.label
					font-weight: 600
					color: #64748b
					min-width: 90px

				.value
					color: #1e293b
					word-break: break-all

				.type-badge
					background-color: #e0f2fe
					color: #0369a1
					padding: 2px 8px
					border-radius: 4px
					font-family: monospace
					font-size: 12px
					font-weight: 600

		.detail-data
			display: flex
			flex-direction: column
			gap: 8px
			min-height: 0
			flex: 1 1 auto

			.label
				font-weight: 600
				font-size: 13.5px
				color: #64748b

			pre
				margin: 0
				padding: 14px
				background-color: #0f172a
				color: #e2e8f0
				border-radius: 6px
				font-size: 12.5px
				line-height: 1.5
				max-height: 300px
				overflow-y: auto
				overflow-x: auto
				box-sizing: border-box
				word-break: normal
				white-space: pre

		.actions
			display: flex
			justify-content: flex-end
			margin-top: 8px
			flex-shrink: 0

			#btn-close-details
				min-width: 90px
</style>
