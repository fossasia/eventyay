<template lang="pug">
.speaker-social-links(v-if="links && links.length", :style="{ justifyContent: alignment }")
	a.speaker-social-link(
		v-for="link in links",
		:key="link.key + link.url",
		:href="link.url",
		:class="'speaker-social-link--' + link.key",
		:style="{ color: link.color || undefined }",
		:aria-label="link.label",
		:title="link.label",
		target="_blank",
		rel="noopener noreferrer")
		span.speaker-social-svg(v-html="getSocialIconHtml(link)")
</template>

<script>
import { getSocialIconHtml } from '../utils'

export default {
	name: 'SpeakerSocialLinks',
	props: {
		links: {
			type: Array,
			default: () => []
		},
		alignment: {
			type: String,
			default: 'center'
		}
	},
	methods: {
		getSocialIconHtml(link) {
			return getSocialIconHtml(link)
		}
	}
}
</script>

<style lang="stylus">
.speaker-social-links
	display: flex
	flex-wrap: wrap
	gap: 8px
	margin-bottom: 4px

.speaker-social-link
	display: inline-flex
	align-items: center
	justify-content: center
	width: 32px
	height: 32px
	border-radius: 6px
	background: rgba(0, 0, 0, 0.06)
	color: inherit
	text-decoration: none
	font-size: 16px
	transition: background-color 0.15s ease, transform 0.15s ease
	&:hover, &:focus-visible
		background: rgba(0, 0, 0, 0.12)
		transform: translateY(-2px)
	&:active
		transform: translateY(0)

.speaker-social-svg
	display: flex
	align-items: center
	justify-content: center
	width: 20px
	height: 20px
	svg
		width: 100%
		height: 100%
		fill: currentColor
</style>
