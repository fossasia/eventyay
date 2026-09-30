<template lang="pug">
.c-reactions-overlay(:class="[direction]")
</template>
<script>
import { mapState } from 'vuex'
import { shuffle } from 'lodash'
import { nativeToStyle as nativeEmojiToStyle } from 'lib/emoji'

const MAX_PARTICLE_POOL = 70 // TODO derive from width to have consistent density
const SERVER_REACTIONS_INTERVAL = 1000

export default {
	components: {},
	props: {
		showReactionBar: Boolean,
	},
	data() {
		return {
			particlePool: [],
			freeParticles: []
		}
	},
	computed: {
		...mapState(['mediaSourcePlaceholderRect', 'reactions', 'stageStreamCollapsed', 'reactionBurst']),
		direction() {
			return this.stageStreamCollapsed ? 'horizontal' : 'vertical'
		}
	},
	watch: {
		reactionBurst(burst) {
			if (!burst?.emoji) return
			this.renderReaction(burst.emoji)
		},
		reactions() {
			if (!this.reactions) return
			// put all reactions in a queue and randomize to get rough averages toghether with the particle pool
			// cap at MAX_PARTICLE_POOL and round up
			let reactions = []
			const totalReactions = Object.values(this.reactions).reduce((acc, count) => acc + count, 0)
			const reactionMultiplier = Math.min(1, MAX_PARTICLE_POOL / totalReactions)
			for (const [reaction, count] of Object.entries(this.reactions)) {
				reactions.push(...Array(Math.ceil(count * reactionMultiplier)).fill(reaction))
			}
			reactions = shuffle(reactions)
			const finalLength = reactions.length
			const distribute = () => {
				if (reactions.length === 0) return
				this.renderReaction(reactions.pop())
				setTimeout(distribute, SERVER_REACTIONS_INTERVAL / finalLength)
			}
			distribute()
		},
		direction() {
			// reset reactions on direction change
			for (const element of this.particlePool) {
				element.style.left = null
				element.style.top = null
			}
		}
	},
	methods: {
		renderReaction(emoji) {
			let element = this.freeParticles.pop()
			if (!element) {
				if (this.particlePool.length < MAX_PARTICLE_POOL) {
					element = document.createElement('div')
					element.classList.add('reaction')
					this.$el.appendChild(element)
					this.particlePool.push(element)
				} else {
					return
				}
			}

			const rect = this.mediaSourcePlaceholderRect
			const overlaySize = this.direction === 'vertical'
				? (rect?.height || this.$el?.clientHeight || 200)
				: (rect?.width || this.$el?.clientWidth || 200)

			const startingPosition = Math.random()
			const targetPosition = (this.direction === 'vertical' ? 0.5 : 1) * Math.max(0.7, Math.random()) * overlaySize
			element.style['background-image'] = nativeEmojiToStyle(emoji)['background-image']
			element.style[this.direction === 'vertical' ? 'left' : 'top'] = `calc(${startingPosition * 100}% - 28px)`
			const axis = this.direction === 'vertical' ? 'Y' : 'X'
			const animation = element.animate([
				{opacity: 1, transform: `translate${axis}(0px)`},
				{opacity: 0, transform: `translate${axis}(-${targetPosition}px)`}
			], {
				duration: 1200 + 500 * Math.random()
			})
			animation.onfinish = () => {
				// onfinish seems to get called twice sometimes?
				if (this.freeParticles.includes(element)) return
				this.freeParticles.push(element)
			}
		}
	}
}
</script>
<style lang="stylus">
.c-reactions-overlay
	position: fixed
	top: var(--mediasource-placeholder-top, 0px)
	left: var(--mediasource-placeholder-left, 0px)
	width: var(--mediasource-placeholder-width, 100%)
	height: var(--mediasource-placeholder-height, 100%)
	pointer-events: none
	overflow: hidden
	z-index: 80
	.reaction
		position: absolute
		height: 56px
		width: @height
		display: inline-block
		background-repeat: no-repeat
		background-position: center
		background-size: contain
	&.vertical
		.reaction
			bottom: -60px
	&.horizontal
		.reaction
			right: -60px
</style>
