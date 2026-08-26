<template lang="pug">
.c-channel-zoom-settings
	bunt-input(v-model="module.config.meeting_number", :label="$t('Meeting ID')", name="meeting_number")
	bunt-input(v-model="module.config.password", :label="$t('Password')", name="password")
	bunt-checkbox(v-model="module.config.disable_chat", :label="$t('Disable chat')", name="zoom_disable_chat")
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
			return this.modules['call.zoom']
		}
	}
}
</script>
<style lang="stylus">
</style>
