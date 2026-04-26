<template lang="pug">
.c-iframe-blocker
	iframe(v-if="showIframe", :src="src", v-bind="$attrs")
	.consent-blocker(v-else)
		.warning This content is hosted by a third party on
		.domain {{ domain }}
		.toc(v-if="config.policy_url") By showing this external content you accept their #[a(:href="config.policy_url") terms and conditions].
		bunt-button#btn-show(@click="showOnce") Show external content
		bunt-checkbox(name="remember", v-model="remember") Remember my choice
</template>
<script>
import store from 'store'
import { getUrlDomain, getBlockerConfig, isDomainBlocked } from 'lib/iframeConsent'
import { normalizeIframeConsentDomain } from 'lib/iframeConsentDomain'
export default {
	inheritAttrs: false,
	props: {
		src: String
	},
	data() {
		return {
			showingOnce: false,
			remember: false
		}
	},
	computed: {
		domain() {
			return getUrlDomain(this.src)
		},
		config() {
			return getBlockerConfig(this.domain)
		},
		showIframe() {
			if (!this.domain) return true
			return this.showingOnce || !isDomainBlocked(this.domain)
		}
	},
	async created() {},
	async mounted() {
		await this.$nextTick()
	},
	emits: ['consent-given'],
	methods: {
		showOnce() {
			if (this.remember) {
				const domain = normalizeIframeConsentDomain(this.domain)
				if (domain) {
					store.dispatch('unblockIframeDomain', domain)
				}
			}
			this.showingOnce = true
			// Pass `this.remember` so the parent knows whether this is persistent
			// consent (handled by the Vuex watcher) or show-once consent (needs an
			// explicit initializeIframe call).
			this.$emit('consent-given', this.remember)
		}
	}
}
</script>
<style lang="stylus">
.c-iframe-blocker
	flex: auto
	display: flex
	iframe
		height: 100%
		width: 100%
		position: absolute
		top: 0
		left: 0
		border: none
		flex: auto // because safari
	.consent-blocker
		flex: auto
		display: flex
		flex-direction: column
		justify-content: center
		align-items: center
		gap: 16px
		background-color: $clr-grey-800
		color: $clr-primary-text-dark
		.warning
			font-size: 20px
		.domain
			font-family: monospace
			font-size: 24px
		.toc
			font-size: 16px
			a
				color: $clr-primary-text-dark
				text-decoration: underline
				&:hover
					color: $clr-secondary-text-dark
		.bunt-checkbox
			label
				font-size: 20px
			&:not(.checked) .bunt-checkbox-box
				border-color: $clr-primary-text-dark
		+above('s')
			#btn-show
				margin-top: 24px
				themed-button-primary(size: large)
		+below('s')
			gap: 8px
			.warning, .domain
				font-size: 12px
			.toc
				font-size: 10px
			#btn-show
				margin-top: 8px
				themed-button-primary()
			.bunt-checkbox
				label
					font-size: 16px
</style>
