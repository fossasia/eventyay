<template lang="pug">
.c-channel-janus-settings
	bunt-checkbox(name="waiting-room-enabled", v-model="module.config.waiting_room_enabled", label="Put new users in waiting room first")
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
			return this.modules['call.janus']
		}
	}
}
</script>
<style lang="stylus">
</style>
