<template lang="pug">
.c-schedule-toolbar
	.toolbar-left
		.version-info(v-if="version")
			span.version-label {{ versionLabel }}
			a.changelog-link(v-if="changelogUrl", :href="changelogUrl")
				i.fa.fa-book
				|  Changelog
		.version-warning(v-if="version && !isCurrent")
			slot(name="version-warning")
				small.text-muted Exports and subscriptions below are for this version.
	.toolbar-right
		.exporter-area(v-if="resolvedExporters.length")
			.exporter-dropdown(ref="exportDropdown")
				button.toolbar-btn(@click="exportOpen = !exportOpen")
					i.fa.fa-download
					|  Export
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
							i.fa(v-if="exp.icon.startsWith('fa-')", :class="exp.icon")
							span(v-else) {{ exp.icon }}
						span.exporter-name {{ exp.verbose_name }}
						transition(name="fade")
							.qr-hover(v-if="hoveredExporter === exp && exp.qrcode_svg", v-html="exp.qrcode_svg")
		button.toolbar-btn(v-if="showPrint", @click="printSchedule", title="Print")
			i.fa.fa-print
		button.toolbar-btn(v-if="showFullscreen", @click="toggleFullscreen", :title="isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'")
			i.fa(:class="isFullscreen ? 'fa-compress' : 'fa-expand'")
</template>

<script>
export default {
	name: 'ScheduleToolbar',
	props: {
		version: {
			type: String,
			default: ''
		},
		isCurrent: {
			type: Boolean,
			default: true
		},
		changelogUrl: {
			type: String,
			default: ''
		},
		exporters: {
			type: Array,
			default: () => []
		},
		showFullscreen: {
			type: Boolean,
			default: true
		},
		showPrint: {
			type: Boolean,
			default: true
		},
		fullscreenTarget: {
			type: Object,
			default: null
		},
		versionPrefix: {
			type: String,
			default: 'Version'
		}
	},
	emits: ['fullscreen-change'],
	data() {
		return {
			exportOpen: false,
			hoveredExporter: null,
			isFullscreen: false
		}
	},
	computed: {
		resolvedExporters() {
			return this.exporters || []
		},
		versionLabel() {
			return this.version ? `${this.versionPrefix} ${this.version}` : ''
		}
	},
	mounted() {
		document.addEventListener('click', this.outsideClick)
		document.addEventListener('fullscreenchange', this.onFullscreenChange)
	},
	beforeUnmount() {
		document.removeEventListener('click', this.outsideClick)
		document.removeEventListener('fullscreenchange', this.onFullscreenChange)
	},
	methods: {
		outsideClick(event) {
			if (!this.$refs.exportDropdown?.contains(event.target)) {
				this.exportOpen = false
			}
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
		}
	}
}
</script>

<style lang="stylus">
.c-schedule-toolbar
	display: flex
	align-items: center
	justify-content: space-between
	flex-wrap: wrap
	gap: 8px
	padding: 4px 16px
	font-size: 14px
	.toolbar-left
		display: flex
		align-items: center
		gap: 12px
		.version-info
			display: flex
			align-items: center
			gap: 8px
			.version-label
				font-weight: 600
			.changelog-link
				color: inherit
				text-decoration: none
				&:hover
					text-decoration: underline
		.version-warning
			color: #856404
			background: #fff3cd
			padding: 2px 8px
			border-radius: 4px
			font-size: 12px
	.toolbar-right
		display: flex
		align-items: center
		gap: 4px
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
				min-width: 220px
				box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
				border-radius: 4px
				z-index: 100
				padding: 4px 0
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
					z-index: 110
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
	.fade-enter-active, .fade-leave-active
		transition: opacity 0.3s
	.fade-enter-from, .fade-leave-to
		opacity: 0

@media print
	.c-schedule-toolbar
		display: none
</style>
