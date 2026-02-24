<template lang="pug">
dialog.pretalx-modal#filter-modal(ref="modal", @click.stop="close()")
	.dialog-inner(@click.stop="")
		button.close-button(@click="close()") ✕
		h3 {{ t.tracks }}
		.checkbox-line(v-for="track in tracks", :key="track.value", :style="{'--track-color': track.color}")
			.checkbox-row
				bunt-checkbox(type="checkbox", :label="track.label", :name="track.value + track.label", v-model="track.selected", :value="track.value", @input="$emit('trackToggled')")
				span.track-color-dot(v-if="track.color", :style="{backgroundColor: track.color}")
			.track-description(v-if="getLocalizedString(track.description).length") {{ getLocalizedString(track.description) }}
</template>

<script>
import { getLocalizedString } from '../utils'

export default {
	name: 'FilterModal',
	inject: {
		translationMessages: { default: () => ({}) }
	},
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
	computed: {
		t() {
			const m = this.translationMessages || {}
			return {
				tracks: m.tracks || 'Tracks',
			}
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
		.checkbox-row
			display: flex
			align-items: center
			gap: 6px
		.bunt-checkbox.checked .bunt-checkbox-box
			background-color: var(--track-color)
			border-color: var(--track-color)
		.track-color-dot
			width: 10px
			height: 10px
			border-radius: 50%
			flex-shrink: 0
		.track-description
			color: $clr-grey-600
			margin-left: 32px
</style>