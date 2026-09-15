<template lang="pug">
.c-channel-loungemesh-settings
	base-channel-form(
		providerId="loungemesh",
		:title="$t('LoungeMesh Spatial Lounge')",
		:subtitle="$t('Spatial proximity networking and workshop lounge powered by LoungeMesh.')",
		providerIcon="mdi-account-group",
		v-bind="$props"
	)
		bunt-checkbox(name="enable_notes", v-model="module.config.enable_notes", :label="$t('Enable shared collaborative notes')")
		bunt-checkbox(name="enable_whiteboard", v-model="module.config.enable_whiteboard", :label="$t('Enable shared interactive whiteboard')")
		bunt-checkbox(name="enable_spatial_chat", v-model="module.config.enable_spatial_chat", :label="$t('Enable spatial chat')")
		bunt-input(name="prefer_server", v-model="module.config.prefer_server", :label="$t('Preferred LoungeMesh server URL or ID')")
</template>
<script>
import BaseChannelForm from './BaseChannelForm'
import mixin from './mixin'

export default {
	components: { BaseChannelForm },
	mixins: [mixin],
	computed: {
		module() {
			if (!this.modules['call.loungemesh']) {
				this.addModule('call.loungemesh', {
					prefer_server: '',
					enable_notes: true,
					enable_whiteboard: true,
					enable_spatial_chat: true
				})
			}
			return this.modules['call.loungemesh']
		}
	},
	created() {
		if (this.module) {
			const cfg = this.module.config || {}
			const features = cfg.features || {}
			const notes = typeof cfg.enable_notes === 'boolean' ? cfg.enable_notes : (typeof features.notes === 'boolean' ? features.notes : true)
			const whiteboard = typeof cfg.enable_whiteboard === 'boolean' ? cfg.enable_whiteboard : (typeof features.whiteboard === 'boolean' ? features.whiteboard : true)
			const spatialChat = typeof cfg.enable_spatial_chat === 'boolean' ? cfg.enable_spatial_chat : (typeof features.spatial_chat === 'boolean' ? features.spatial_chat : true)

			this.module.config = {
				prefer_server: '',
				enable_notes: notes,
				enable_whiteboard: whiteboard,
				enable_spatial_chat: spatialChat,
				...cfg,
				features: {
					notes,
					whiteboard,
					spatial_chat: spatialChat,
					...features,
				}
			}
		}
	},
	methods: {
		beforeSave() {
			if (this.module?.config) {
				const cfg = this.module.config
				cfg.features = {
					...(cfg.features || {}),
					notes: Boolean(cfg.enable_notes),
					whiteboard: Boolean(cfg.enable_whiteboard),
					spatial_chat: Boolean(cfg.enable_spatial_chat),
				}
			}
		}
	}
}
</script>
<style lang="stylus">
</style>
