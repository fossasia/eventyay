<template lang="pug">
.c-admin-interpretation
	.ui-page-header
		bunt-icon-button(@click="goBack", :tooltip="$t('Back')", tooltip-placement="bottom-start", :tooltip-fixed="true") arrow-left
		h1 {{ $t('Interpretation') }}
	iframe(ref="iframe", :src="iframeUrl", class="interpretation-iframe")
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const iframe = ref(null)

const iframeUrl = computed(() => {
        let url = window.eventyay?.interpretationUrl || ''
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

function goBack() {
	try {
		const iframeWindow = iframe.value.contentWindow
		const currentPath = iframeWindow.location.pathname
		const baseUrl = new URL(iframeUrl.value, window.location.origin).pathname
		
		if (currentPath && currentPath !== baseUrl && currentPath + '/' !== baseUrl && currentPath !== baseUrl + '/' && iframeWindow.history.length > 1) {
			iframeWindow.history.back()
		} else {
			router.push({name: 'organizer'})
		}
	} catch (e) {
		router.push({name: 'organizer'})
	}
}
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
