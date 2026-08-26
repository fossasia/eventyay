<template lang="pug">
.c-mainconfig
	.ui-page-header
		h1 {{ $t('Event Config') }}
	scrollbars(y)
		bunt-progress-circular(size="huge", v-if="!config && !error")
		.error(v-if="error") {{ $t('We could not fetch the current configuration.') }}
		.ui-form-body(v-if="config")
			h2 {{ $t('System details') }}
			bunt-input(v-model="config.connection_limit", :label="$t('Max connections')", name="connection_limit", :hint="$t('Set to 0 to allow unlimited connections per user')", :validation="v$.config.connection_limit")
			template(v-if="$features.enabled('conftool')")
				h2 {{ $t('Conftool') }}
				bunt-input(v-model="config.conftool_url", :label="$t('Conftool REST API URL')", name="conftool_url", :validation="v$.config.conftool_url")
				bunt-input(v-model="config.conftool_password", :label="$t('Conftool REST API Password')", name="conftool_password")
			h2 {{ $t('Tracking and statistics') }}
			bunt-checkbox(v-model="config.track_room_views", :label="$t('Track room views')", name="track_room_views")
			bunt-checkbox(v-model="config.track_world_views", :label="$t('Track world views')", name="track_world_views")
			h2 {{ $t('Settings for newly-created BBB rooms') }}
			bunt-checkbox(v-model="config.bbb_defaults.record", :label="$t('Allow recording')", name="record")
			bunt-checkbox(v-model="config.bbb_defaults.hide_presentation", :label="$t('Hide presentation when users join')", name="hide_presentation")
			bunt-checkbox(v-model="config.bbb_defaults.waiting_room", :label="$t('Put new users in waiting room first (needs to be set before first join)')", name="waiting_room")
			bunt-checkbox(v-model="config.bbb_defaults.auto_microphone", :label="$t('Auto-join users with microphone on (skip dialog asking how to join)')", name="auto_microphone")
			bunt-checkbox(v-model="config.bbb_defaults.auto_camera", :label="$t('Auto-join users with camera on')", name="auto_camera")
			bunt-checkbox(v-model="config.bbb_defaults.bbb_mute_on_start", :label="$t('Auto-mute users')", name="bbb_mute_on_start")
			bunt-checkbox(v-model="config.bbb_defaults.bbb_disable_cam", :label="$t('Disable camera for non-moderators')", name="bbb_disable_cam")
			bunt-checkbox(v-model="config.bbb_defaults.bbb_disable_chat", :label="$t('Disable public chat for non-moderators')", name="bbb_disable_chat")
			h2 {{ $t('Settings for stages') }}
			bunt-input-outline-container(:label="$t('hls.js config')", :class="{error: v$.hlsConfig.$invalid}")
				template(#default="{focus, blur}")
					textarea(@focus="focus", @blur="blur", v-model="hlsConfig")
			.json-error-message {{ v$.hlsConfig.isJson.$message }}
	.ui-form-actions
		bunt-button.btn-save(@click="save", :loading="saving", :error-message="error") {{ $t('Save') }}
		.errors {{ validationErrors.join(', ') }}
</template>
<script setup>
import { ref, computed, onMounted, getCurrentInstance } from 'vue'
import { useVuelidate } from '@vuelidate/core'
import api from 'lib/api'
import i18n from 'i18n'
import { required, integer, isJson, url } from 'lib/validators'

const config = ref(null)
const hlsConfig = ref('')
const saving = ref(false)
const error = ref(null)
const instance = getCurrentInstance()
const features = instance?.proxy?.$features

const validationErrors = computed(() => v$.value.$errors?.map(e => e.$message) || [])

// Validation rules
const rules = {
	config: {
		connection_limit: {
			required: required(i18n.t('Max connections is required')),
			integer: integer(i18n.t('Max connections must be a number'))
		},
		conftool_url: {url: url(i18n.t('Conftool URL must be a URL'))}
	},
	hlsConfig: { isJson: isJson() }
}

const v$ = useVuelidate(rules, { config, hlsConfig })

onMounted(async () => {
	try {
		config.value = await api.call('world.config.get')
		hlsConfig.value = JSON.stringify(config.value.video_player?.['hls.js'] || undefined, null, 2)
	} catch (e) {
		error.value = e.message || e.toString()
		console.log(e)
	}
})

async function save() {
	v$.value.$touch()
	if (v$.value.$invalid) return
	if (!config.value) return
	saving.value = true
	try {
		const patch = {
			connection_limit: config.value.connection_limit,
			bbb_defaults: config.value.bbb_defaults,
			track_room_views: config.value.track_room_views,
			track_world_views: config.value.track_world_views
		}
		if (features?.enabled('conftool')) {
			patch.conftool_url = config.value.conftool_url
			patch.conftool_password = config.value.conftool_password
		}
		if (hlsConfig.value) {
			patch.video_player = { 'hls.js': JSON.parse(hlsConfig.value) }
		} else {
			patch.video_player = null
		}
		await api.call('world.config.patch', patch)
	} catch (e) {
		console.error(e.apiError || e)
		error.value = e.apiError?.code || e.message || e.toString()
	} finally {
		saving.value = false
	}
}
</script>
<style lang="stylus">
.c-mainconfig
	flex: auto
	display: flex
	flex-direction: column
	min-height: 0
	height: 100%
	.ui-page-header
		flex: none
		position: sticky
		top: 0
		z-index: 10
		background-color: $clr-grey-50
	> .c-scrollbars
		flex: auto
		min-height: 0
	.ui-form-actions
		flex: none
		position: sticky
		bottom: 0
		background-color: white
		border-top: border-separator()
		padding: 16px
		z-index: 10
	.bunt-input-outline-container
		margin-top: 16px
		&.error
			label
				color: $clr-danger
			.outline
				stroke: $clr-danger
				stroke-width: 2px
		textarea
			background-color: transparent
			border: none
			outline: none
			resize: vertical
			min-height: 120px
			padding: 0 8px
	.json-error-message
		color: $clr-danger
		margin: 4px
</style>
