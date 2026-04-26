<template lang="pug">
.c-export-dropdown(ref="dropdown")
	button.export-toggle(@click="toggle")
		svg.export-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2")
			path(d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4")
			polyline(points="7 10 12 15 17 10")
			line(x1="12", y1="15", x2="12", y2="3")
		|  {{ t.exports }}
	.exporter-menu(v-if="isOpen", :style="menuStyle")
		template(v-for="(option, idx) in exportOptions", :key="option.divider ? `div-${idx}` : option.id")
			.exporter-divider(v-if="option.divider")
			a.exporter-item(
				v-else,
				:href="option.url",
				target="_blank",
				@mouseover="onItemHover($event, option)",
				@mouseleave="hoveredOption = null"
			)
				span.exporter-icon(v-if="option.icon")
					svg.tb-icon(viewBox="0 0 24 24", fill="none", stroke="currentColor", stroke-width="2", v-html="faIconSvg(option.icon)")
				span.exporter-name {{ option.label }}
	.qr-hover(v-if="hoveredOption && hoveredOption.qrcode_svg", :style="qrStyle", v-html="hoveredOption.qrcode_svg")
</template>

<script>
const FA_SVG_MAP = {
	'fa-calendar': '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>',
	'fa-code': '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
	'fa-google': '<circle cx="12" cy="12" r="10"/><path d="M12 8v8"/><path d="M8 12h8"/>',
	'fa-star': '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
}

export default {
	name: 'ExportDropdown',
	inject: {
		translationMessages: { default: () => ({}) }
	},
	props: {
		options: {
			type: Array,
			default: () => []
		}
	},
	emits: ['export'],
	data() {
		return {
			isOpen: false,
			hoveredOption: null,
			menuStyle: {},
			qrStyle: {}
		}
	},
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				exports: m.exports || 'Exports',
			}
		},
		exportOptions() {
			return this.options
		}
	},
	mounted() {
		document.addEventListener('click', this.outsideClick)
	},
	beforeUnmount() {
		document.removeEventListener('click', this.outsideClick)
	},
	methods: {
		faIconSvg(icon) {
			if (!icon) return ''
			return FA_SVG_MAP[icon] || '<circle cx="12" cy="12" r="10"/>'
		},
		toggle() {
			this.isOpen = !this.isOpen
			if (this.isOpen) {
				this.$nextTick(() => this.positionMenu())
			} else {
				this.hoveredOption = null
			}
		},
		positionMenu() {
			const el = this.$refs.dropdown
			if (!el) return
			const rect = el.getBoundingClientRect()
			this.menuStyle = {
				position: 'fixed',
				top: `${rect.bottom + 2}px`,
				right: `${window.innerWidth - rect.right}px`
			}
		},
		onItemHover(event, option) {
			this.hoveredOption = option
			if (!option.qrcode_svg) return
			const itemEl = event.currentTarget
			const rect = itemEl.getBoundingClientRect()
			// Position QR to the left of the menu item using fixed positioning
			// QR box is ~144px wide (128px + 16px padding)
			const qrWidth = 148
			let left = rect.left - qrWidth - 4
			// If it would go off the left edge, show to the right instead
			if (left < 0) {
				left = rect.right + 4
			}
			this.qrStyle = {
				position: 'fixed',
				top: `${rect.top}px`,
				left: `${left}px`
			}
		},
		outsideClick(event) {
			const path = event.composedPath()
			if (!path.includes(this.$refs.dropdown)) {
				this.isOpen = false
			}
		}
	}
}
</script>

<style lang="stylus">
.c-export-dropdown
	position: relative
	display: inline-block
	z-index: 100
	.export-toggle
		border: none
		height: 32px
		border-radius: 2px
		cursor: pointer
		background: transparent
		padding: 0 10px
		font-size: 14px
		display: flex
		align-items: center
		gap: 4px
		&:hover
			background-color: rgba(0, 0, 0, 0.05)
	.export-icon
		width: 16px
		height: 16px
	.exporter-menu
		position: fixed
		background: #fff
		min-width: 280px
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15)
		border-radius: 4px
		z-index: 10000
		padding: 4px 0
		white-space: nowrap
	.exporter-divider
		height: 1px
		background: #e0e0e0
		margin: 4px 0
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
			.tb-icon
				width: 16px
				height: 16px
	.qr-hover
		position: fixed
		padding: 8px
		background: #fff
		border: 1px solid #ddd
		border-radius: 4px
		box-shadow: 2px 2px 8px rgba(0, 0, 0, 0.1)
		z-index: 10001
		pointer-events: none
		svg
			width: 128px
			height: 128px
			display: block
	.fade-enter-active, .fade-leave-active
		transition: opacity 0.3s
	.fade-enter-from, .fade-leave-to
		opacity: 0
</style>
