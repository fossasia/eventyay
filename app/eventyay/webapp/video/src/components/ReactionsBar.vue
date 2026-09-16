<template lang="pug">
.c-reactions-bar(:class="{expanded}")
	.actions(@click="expand")
		bunt-icon-button(
			v-for="reaction of availableReactions",
			:key="reaction.emoji",
			:tooltip="reaction.label",
			tooltip-placement="top",
			:tooltip-fixed="true",
			@click.stop="react(reaction.emoji)"
		)
			img.emoji(:src="reaction.url", :alt="reaction.label")
</template>
<script>
import { nativeToUrl as nativeEmojiToUrl, getEmojiDataFromNative } from 'lib/emoji'

export default {
	props: {
		expanded: Boolean
	},
	emits: ['expand'],
	computed: {
		availableReactions() {
			return ['👏', '❤️', '👍', '🤣', '😮'].map(emoji => ({
				emoji,
				url: nativeEmojiToUrl(emoji),
				label: getEmojiDataFromNative(emoji).short_names[0],
			}))
		}
	},
	methods: {
		expand() {
			if (this.expanded) return
			this.$emit('expand')
		},
		react(emoji) {
			this.$store.dispatch('addReaction', emoji)
		}
	}
}
</script>
<style lang="stylus">
.c-reactions-bar
	display: flex
	align-items: center
	flex: none
	.actions
		display: flex
		align-items: center
		gap: 0
		background-color: $clr-white
		border: border-separator()
		border-radius: 18px
		padding: 1px
	.bunt-icon-button
		icon-button-style()
		height: 24px !important
		width: 24px !important
		min-width: 24px !important
		padding: 0 !important
		margin: 0 !important
		-webkit-tap-highlight-color: transparent
		outline: none
		&:focus-visible
			outline: 2px solid var(--clr-primary, $clr-primary)
			outline-offset: 2px
	.emoji
		height: 20px
		width: @height
		display: block
	&:not(.expanded)
		.actions:hover
			cursor: pointer
			background-color: $clr-grey-100
		.bunt-icon-button
			pointer-events: none
</style>
