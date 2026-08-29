<template lang="pug">
.c-standalone-viewers(:class="[mode, {empty: !hasViewers}]")
	template(v-if="hasViewers")
		h1.viewers-heading {{ viewersHeading }}
		.viewers-list
			.viewer(v-for="viewer in visibleViewers", :key="viewer.id || viewerName(viewer)")
				avatar(:user="viewer", :size="mode === 'compact' ? 36 : 48")
				.viewer-meta
					.viewer-name {{ viewerName(viewer) }}
	.empty-card(v-else)
		i.mdi.mdi-account-group-outline
		h2 {{ $t('No viewers yet') }}
		p {{ $t('People currently in this room will be listed here.') }}
</template>
<script>
import { mapState } from 'vuex'
import Avatar from 'components/Avatar'

export default {
	components: { Avatar },
	props: {
		room: Object,
		mode: {
			type: String,
			default: 'focus'
		}
	},
	computed: {
		...mapState(['roomViewers', 'user']),
		visibleViewers() {
			if (!Array.isArray(this.roomViewers)) return []
			const selfId = this.user?.id
			return this.roomViewers.filter(viewer => {
				if (!viewer || viewer.deleted) return false
				// Hide the kiosk/display account itself from the audience list.
				if (selfId && String(viewer.id) === String(selfId)) return false
				return true
			})
		},
		hasViewers() {
			return this.visibleViewers.length > 0
		},
		viewersHeading() {
			const count = this.visibleViewers.length
			if (count === 1) {
				return this.$t('1 viewer')
			}
			return this.$t('{{count}} viewers', {count})
		},
	},
	methods: {
		viewerName(viewer) {
			return viewer?.profile?.display_name || viewer?.name || this.$t('Anonymous')
		}
	}
}
</script>
<style lang="stylus">
.c-standalone-viewers
	display: flex
	flex-direction: column
	justify-content: flex-start
	width: 100%
	max-width: none
	height: 100%
	margin: 0
	padding: 16px 20px
	box-sizing: border-box
	color: #1e2327
	overflow: auto

	&.compact
		padding: 4px
		.viewers-heading
			font-size: 14px
			margin-bottom: 10px
			text-align: left
		.viewer
			padding: 6px 8px
		.empty-card
			i.mdi
				font-size: 36px
				margin-bottom: 8px
			h2
				font-size: 16px
			p
				font-size: 12px

	.viewers-heading
		margin: 0 0 16px
		font-size: 20px
		font-weight: 700
		text-align: left
		color: #1e2327

	.viewers-list
		display: flex
		flex-direction: column
		gap: 8px
		width: 100%
		overflow: auto

	.viewer
		display: flex
		align-items: center
		gap: 12px
		width: 100%
		padding: 10px 12px
		border: 1px solid #e5e7eb
		border-radius: 8px
		background: #ffffff
		box-sizing: border-box

		.viewer-meta
			min-width: 0
			flex: 1 1 auto

		.viewer-name
			font-size: 15px
			font-weight: 600
			color: #1e2327
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap

	.empty-card
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		text-align: center
		flex: 1
		color: #4b5563
		i.mdi
			font-size: 56px
			margin-bottom: 16px
			color: var(--clr-primary, #2185d0)
		h2
			margin: 0 0 8px
			font-size: 22px
			font-weight: 700
			color: #1e2327
		p
			margin: 0
			max-width: 360px
			font-size: 15px
</style>
