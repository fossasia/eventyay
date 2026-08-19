<template lang="pug">
.c-channel-loungemesh-settings
	bunt-input(v-model="module.config.url", label="LoungeMesh URL override (optional)", name="loungemesh_url")
	template(v-if="allowedFeatures.length")
		h3 Features
		bunt-checkbox(
			v-for="feature in allowedFeatures",
			:key="feature",
			:name="`loungemesh-${feature}`",
			v-model="module.config.features[feature]",
			:label="featureLabel(feature)"
		)
	p.hint(v-else) No LoungeMesh features are currently allowed by Video Admin.
	sidebar-addons(v-bind="$props")
</template>
<script>
import mixin from './mixin'
import SidebarAddons from './SidebarAddons'

const FEATURE_LABELS = {
	notes: 'Shared notes',
	whiteboard: 'Whiteboard',
	poll: 'Polls',
	chat: 'Chat',
	screenshare: 'Screenshare',
	reactions: 'Reactions',
	lobby: 'Lobby / waiting room',
}

export default {
	components: { SidebarAddons },
	mixins: [mixin],
	computed: {
		module() {
			return this.modules['call.loungemesh']
		},
		allowedFeatures() {
			const fromWorld = this.$store.state.world?.loungemesh_organizer_features
			if (Array.isArray(fromWorld) && fromWorld.length) return fromWorld
			const fromWindow = window.eventyay?.loungemeshOrganizerFeatures
			return Array.isArray(fromWindow) ? fromWindow : []
		}
	},
	created() {
		this.module.config = {
			url: '',
			features: {},
			...this.module.config
		}
		if (!this.module.config.features || typeof this.module.config.features !== 'object') {
			this.module.config.features = {}
		}
		for (const feature of this.allowedFeatures) {
			if (typeof this.module.config.features[feature] !== 'boolean') {
				this.module.config.features[feature] = false
			}
		}
		for (const key of Object.keys(this.module.config.features)) {
			if (!this.allowedFeatures.includes(key)) {
				delete this.module.config.features[key]
			}
		}
	},
	methods: {
		featureLabel(feature) {
			return FEATURE_LABELS[feature] || feature
		}
	}
}
</script>
<style lang="stylus">
.c-channel-loungemesh-settings
	h3
		margin: 16px 0 8px
		font-size: 16px
		font-weight: 500
	.hint
		color: $clr-secondary-text-light
</style>
