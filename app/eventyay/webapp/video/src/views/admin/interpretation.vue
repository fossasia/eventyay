<template lang="pug">
.c-admin-interpretation
	.ui-page-header
		h1 {{ $t('Interpretation') }}
	bunt-progress-circular(size="huge", v-if="!isReady")
	.unauthorized-notice(v-else-if="!hasAccess")
		p {{ $t('You do not have permission to view interpretation settings.') }}
	.unauthorized-notice(v-else-if="!isPluginEnabled")
		p {{ $t('The interpretation plugin is not enabled for this event.') }}
	iframe(v-else, ref="iframe", :src="iframeUrl", class="interpretation-iframe")
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useStore } from 'vuex'
import { interpretationRouting } from 'lib/interpretation-api'

const route = useRoute()
const store = useStore()
const iframe = ref(null)

const isReady = computed(() => Boolean(
	window.eventyay?.hasOrganiserPermissions ||
	store.state.connected
))

const hasAccess = computed(() => Boolean(
	window.eventyay?.hasOrganiserPermissions ||
	store.getters['isAdminMode'] ||
	store.getters['hasPermission']?.('world:update')
))

const isPluginEnabled = computed(() => Boolean(store.getters['isInterpretationEnabled']))

const iframeUrl = computed(() => {
	if (!isPluginEnabled.value) return ''
	let url = window.eventyay?.interpretationUrl || ''
	if (!url) {
		const { organizer, event } = interpretationRouting(store)
		if (organizer && event) {
			url = `/video/plugins/${organizer}/${event}/interpretation/`
		}
	}
	if (url) {
		const queryStr = Object.keys(route.query).map(key => `${key}=${route.query[key]}`).join('&')
		if (queryStr) {
			url += url.includes('?') ? `&${queryStr}` : `?${queryStr}`
		}
		if (route.hash) {
			url += route.hash
		}
	}
	return url
})
</script>

<style scoped>
.c-admin-interpretation {
	display: flex;
	flex-direction: column;
	width: 100%;
	height: 100%;
}
.interpretation-iframe {
	width: 100%;
	height: 100%;
	flex: 1;
	border: none;
}
</style>
