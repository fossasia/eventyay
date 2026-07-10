<template lang="pug">
.c-channel-jitsi-settings
	bunt-input(v-model="module.config.room_name", label="Room name", name="jitsi_room_name")
	bunt-input(v-model="module.config.prefer_server", label="Preferred Jitsi server URL", name="jitsi_prefer_server")
	bunt-checkbox(v-model="module.config.start_with_audio_muted", label="Start with audio muted", name="jitsi_audio_muted")
	bunt-checkbox(v-model="module.config.start_with_video_muted", label="Start with video muted", name="jitsi_video_muted")
	sidebar-addons(v-bind="$props")
</template>
<script>
import mixin from './mixin'
import SidebarAddons from './SidebarAddons'

export default {
	components: { SidebarAddons },
	mixins: [mixin],
	computed: {
		module() {
			return this.modules['call.jitsi']
		}
	},
	created() {
		this.module.config = {
			room_name: '',
			prefer_server: '',
			start_with_audio_muted: false,
			start_with_video_muted: false,
			...this.module.config
		}
		delete this.module.config.domain
		delete this.module.config.jwt_enabled
		delete this.module.config.app_id
		delete this.module.config.key_id
		delete this.module.config.app_secret
	}
}
</script>
<style lang="stylus">
</style>
