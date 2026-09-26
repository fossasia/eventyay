<template lang="pug">
.c-reactions-bar
	.actions
		bunt-icon-button(
			v-for="reaction of availableReactions",
			:key="reaction.emoji",
			:tooltip-options="{ text: reaction.label, placement: 'top', fixed: true, boundariesElement: 'window' }",
			@click.stop="react(reaction.emoji)"
		)
			img.emoji(:src="reaction.url", :alt="reaction.label")
</template>
<script>
import { nativeToUrl as nativeEmojiToUrl, getEmojiDataFromNative } from 'lib/emoji'

export default {
	props: {
		expanded: Boolean,
		large: Boolean
	},
	emits: ['expand'],
	computed: {
		availableReactions() {
			return ['👏', '❤️', '🎉', '👍', '🔥', '😂', '😮', '😢', '🙌', '💯', '🤔', '👎'].map(emoji => {
				let label = getEmojiDataFromNative(emoji).short_names[0]
				label = label.replace(/_/g, ' ')
				if (label === '+1') label = 'thumbs up'
				else if (label === '-1') label = 'thumbs down'
				return {
					emoji,
					url: nativeEmojiToUrl(emoji),
					label,
				}
			})
		}
	},
	methods: {
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
		display: grid
		grid-template-columns: repeat(6, 28px)
		grid-auto-rows: 28px
		gap: 2px
		background: var(--clr-surface, #ffffff)
		border: 1px solid var(--clr-grey-200, #e2e8f0)
		border-radius: 12px
		padding: 4px
		overflow: visible
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04)
		transition: border-color 0.15s ease, box-shadow 0.15s ease
		&:hover
			border-color: var(--clr-grey-300, #cbd5e1)
			box-shadow: 0 2px 6px rgba(0, 0, 0, 0.08)
	.bunt-icon-button
		icon-button-style()
		height: 28px !important
		width: 28px !important
		min-width: 28px !important
		padding: 0 !important
		margin: 0 !important
		-webkit-tap-highlight-color: transparent
		outline: none
		border-radius: 50%
		transition: transform 0.15s cubic-bezier(0.34, 1.56, 0.64, 1), background-color 0.12s ease
		&:hover
			transform: scale(1.25) translateY(-2px)
			background-color: var(--clr-primary-alpha-18, rgba(33, 133, 208, 0.12))
		&:active
			transform: scale(0.92)
		&:focus-visible
			outline: 2px solid var(--clr-primary, #2185d0)
			outline-offset: 1px
	.emoji
		height: 18px
		width: @height
		display: block
</style>
