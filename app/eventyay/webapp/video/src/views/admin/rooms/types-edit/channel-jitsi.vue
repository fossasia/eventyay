<template lang="pug">
.c-channel-jitsi-settings
	bunt-input(v-model="module.config.domain", label="Jitsi domain", name="jitsi_domain")
	bunt-input(v-model="module.config.room_name", label="Room name", name="jitsi_room_name")
	bunt-checkbox(v-model="module.config.jwt_enabled", label="Use JWT authentication", name="jitsi_jwt_enabled")
	template(v-if="module.config.jwt_enabled")
		bunt-input(v-model="module.config.app_id", label="App ID", name="jitsi_app_id")
		bunt-input(v-model="module.config.key_id", label="Key ID", name="jitsi_key_id")
		bunt-input(v-model="module.config.app_secret", label="App secret (leave blank to keep saved secret)", name="jitsi_app_secret", type="password")
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
			domain: '',
			room_name: '',
			jwt_enabled: true,
			app_id: '',
			key_id: '',
			app_secret: '',
			start_with_audio_muted: false,
			start_with_video_muted: false,
			...this.module.config
		}
	}
}
</script>
<style lang="stylus">
</style>
