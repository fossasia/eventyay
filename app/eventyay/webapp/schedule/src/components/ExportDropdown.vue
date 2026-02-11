<template lang="pug">
.c-export-dropdown(ref="dropdown")
	button.export-toggle(@click="isOpen = !isOpen")
		| {{ selectedLabel || 'Add to Calendar' }}
	.dropdown-menu(v-if="isOpen")
		.dropdown-item(
			v-for="option in exportOptions",
			:key="option.id",
			@click="selectOption(option)",
			@mouseover="setHovered(option)",
			@mouseleave="clearHovered(option)"
		)
			.item-text {{ option.label }}
			img.qr-thumb(v-if="qrCodes[option.id]", :src="qrCodes[option.id]", alt="QR")
			transition(name="fade")
				.qr-popup(v-if="hoveredOption === option && qrCodes[option.id]")
					img(:src="qrCodes[option.id]", alt="QR Code")
</template>

<script>
const DEFAULT_EXPORT_TYPES = [
	{ id: 'ics', label: 'Session ICal' },
	{ id: 'json', label: 'Session JSON' },
	{ id: 'xcal', label: 'Session XCal' },
	{ id: 'xml', label: 'Session XML' },
	{ id: 'myics', label: 'My \u2B50 Sessions ICal' },
	{ id: 'myjson', label: 'My \u2B50 Sessions JSON' },
	{ id: 'myxcal', label: 'My \u2B50 Sessions XCal' },
	{ id: 'myxml', label: 'My \u2B50 Sessions XML' },
]

const QR_TYPES = ['ics', 'xml', 'myics', 'myxml']

export default {
	name: 'ExportDropdown',
	inject: {
		exportBaseUrl: { default: '' }
	},
	props: {
		options: {
			type: Array,
			default: () => DEFAULT_EXPORT_TYPES
		},
		baseUrl: {
			type: String,
			default: ''
		},
		qrCodeModule: {
			type: Object,
			default: null
		}
	},
	emits: ['export'],
	data() {
		return {
			isOpen: false,
			selectedLabel: null,
			hoveredOption: null,
			qrCodes: {}
		}
	},
	computed: {
		exportOptions() {
			return this.options
		},
		resolvedBaseUrl() {
			return this.baseUrl || this.exportBaseUrl || ''
		}
	},
	created() {
		if (this.resolvedBaseUrl) {
			this.exportOptions.forEach(opt => this.generateQRCode(opt))
		}
	},
	mounted() {
		document.addEventListener('click', this.outsideClick)
	},
	beforeUnmount() {
		document.removeEventListener('click', this.outsideClick)
	},
	methods: {
		selectOption(option) {
			this.selectedLabel = option.label
			this.isOpen = false
			this.$emit('export', option)
		},
		outsideClick(event) {
			if (!this.$refs.dropdown?.contains(event.target)) {
				this.isOpen = false
			}
		},
		async generateQRCode(option) {
			if (!QR_TYPES.includes(option.id)) return
			const url = this.resolvedBaseUrl + option.id
			const QRCode = this.qrCodeModule
			if (!QRCode) return
			try {
				QRCode.toDataURL(url, { scale: 1 }, (err, dataUrl) => {
					if (!err) this.qrCodes[option.id] = dataUrl
				})
			} catch {
				// QR generation failed, skip
			}
		},
		setHovered(option) {
			this.hoveredOption = QR_TYPES.includes(option.id) ? option : null
		},
		clearHovered(option) {
			if (this.hoveredOption === option) this.hoveredOption = null
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
		padding: 0 12px
		&:hover
			background-color: rgba(0, 0, 0, 0.05)
	.dropdown-menu
		position: absolute
		right: 0
		background-color: #f9f9f9
		min-width: 180px
		box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2)
		z-index: 10
	.dropdown-item
		display: flex
		justify-content: space-between
		align-items: center
		padding: 4px 8px
		color: black
		cursor: pointer
		&:hover
			background-color: #f1f1f1
	.qr-thumb
		width: 20px
		height: 20px
	.qr-popup
		position: absolute
		right: 100%
		top: 0
		padding: 10px
		background: white
		border: 1px solid #ccc
		box-shadow: 2px 2px 10px rgba(0, 0, 0, 0.1)
		img
			width: 150px
			height: 150px
	.fade-enter-active, .fade-leave-active
		transition: opacity 0.5s
	.fade-enter-from, .fade-leave-to
		opacity: 0
</style>
