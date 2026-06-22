<template lang="pug">
export-dropdown(v-if="showExport", :options="exportOptions", :qrcodesUrl="qrcodesUrl", :disabled="isWipPreview")
.button-container(v-if="showFav", :class="{ faved }")
	fav-button(@toggleFav="$emit('toggleFav')")
</template>

<script>
import ExportDropdown from './ExportDropdown.vue'
import FavButton from './FavButton.vue'

export default {
	name: 'DetailTopActions',
	components: { ExportDropdown, FavButton },
	emits: ['toggleFav'],
	inject: {
		isWipPreview: { default: false },
	},
	props: {
		exportOptions: {
			type: Array,
			default: () => []
		},
		qrcodesUrl: {
			type: String,
			default: ''
		},
		showFav: {
			type: Boolean,
			default: false
		},
		faved: {
			type: Boolean,
			default: false
		},
	},
	computed: {
		showExport () {
			return this.exportOptions.length > 0 || this.isWipPreview
		},
	},
}
</script>
