<template lang="pug">
dialog.pretalx-modal#filter-modal(ref="modal", @click.stop="close()")
	.dialog-inner(@click.stop="")
		button.close-button(@click="close()") ✕
		h3 Tracks
		.checkbox-line(v-for="track in tracks", :key="track.value", :style="{'--track-color': track.color}")
			bunt-checkbox(type="checkbox", :label="track.label", :name="track.value + track.label", v-model="track.selected", :value="track.value", @input="$emit('trackToggled')")
			.track-description(v-if="getLocalizedString(track.description).length") {{ getLocalizedString(track.description) }}
</template>

<script>
import { getLocalizedString } from '~/utils'

export default {
	name: 'FilterModal',
	props: {
		tracks: {
			type: Array,
			default: () => []
		}
	},
	emits: ['trackToggled'],
	data () {
		return {
			getLocalizedString
		}
	},
	methods: {
		showModal () {
			this.$refs.modal?.showModal()
		},
		close () {
			this.$refs.modal?.close()
		}
	}
}
</script>

<style lang="stylus">
#filter-modal
	.checkbox-line
		margin: 16px 8px
		.bunt-checkbox.checked .bunt-checkbox-box
			background-color: var(--track-color)
			border-color: var(--track-color)
		.track-description
			color: $clr-grey-600
			margin-left: 32px
</style>