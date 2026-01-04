<template lang="pug">
.c-schedule-talk(v-scrollbar.y="")
	.talk-wrapper(v-if="talk")
		.talk
			h1 {{ talk.title }}
			.info {{ datetime }} {{ roomName }}
			markdown-content.abstract(:markdown="talk.abstract")
			markdown-content.description(:markdown="talk.description")
			.downloads(v-if="talk.resources && talk.resources.length > 0")
				h2 {{ $t("schedule/talks:downloads-headline:text") }}
				a.download(v-for="{resource, description} of talk.resources", :href="getAbsoluteResourceUrl(resource)", target="_blank")
					.mdi(:class="`mdi-${getIconByFileEnding(resource)}`")
					.filename {{ description }}
			
			// Context: Video - Show detailed actions
			template(v-if="context === 'video'")
				bunt-link-button.btn-create.router-link.stage(v-if="getRoomIdByName(roomName)", :to="{name: 'room', params: {roomId: getRoomIdByName(roomName)}}") Join room
			
			// Context: Talk - Maybe simpler view or specific actions (currently similar)
			template(v-else)
				// Informational specific items if any

		.speakers(v-if="talk.speakers && talk.speakers.length > 0")
			.header {{ $t('schedule/talks/item:speakers:header', {count: talk.speakers.length})}}
			.speakers-list
				.speaker(v-for="speaker of talk.speakers")
					router-link.speaker-link(:to="{name: 'schedule:speaker', params: {speakerId: speaker.code}}")
						img.avatar-circle(v-if="speaker.avatar || speaker.avatar_url", :src="speaker.avatar || speaker.avatar_url")
						identicon.avatar-circle(v-else, :user="{id: speaker.code, profile: {display_name: speaker.name || 'Speaker'}}")
						.name(:class="{'no-name': !speaker.name}") {{ speaker.name || 'Speaker name not provided' }}
					markdown-content.biography(:markdown="speaker.biography")
	bunt-progress-circular(v-else, size="huge", :page="true")
</template>
<script setup>
import { computed, watch, ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useRoute } from 'vue-router'
import moment from 'lib/timetravelMoment'
import MarkdownContent from 'components/MarkdownContent'
import Identicon from 'components/Identicon'
import { getIconByFileEnding } from 'lib/filetypes'
import { useScheduleStore } from '../store'

const props = defineProps({
	talkId: String,
	context: {
		type: String,
		default: 'talk' // 'talk' or 'video'
	}
})

const store = useStore() // Vuex store access
const scheduleStore = useScheduleStore() // Pinia store

const talk = ref(null)

// Computed
const rooms = computed(() => store.state.rooms || [])
const pretalxApiBaseUrl = computed(() => store.getters['schedule/pretalxApiBaseUrl']) // Reusing getter logic might be tricky without duplicating, using vuex getter for now if available

const datetime = computed(() => {
	if (!talk.value) { return '' }
	return moment(talk.value.start).format('L LT') + ' - ' + moment(talk.value.end).format('LT')
})

const roomName = computed(() => {
	if (!talk.value) { return '' }
	// Assuming $localize is global, otherwise need import
	// In setup, globalProperties are not directly available. 
	// We might need a helper, or just use the name if string.
	// For now, assume simple string or object.
	const r = talk.value.room?.name || talk.value.room
	if (typeof r === 'object') return r.en || Object.values(r)[0]
	return r
})

// Access filtered sessions from Pinia
const sessions = computed(() => scheduleStore.sessions)

watch(sessions, () => {
	if (!sessions.value) return
	// If already loaded
	updateTalk()
}, { immediate: true })

watch(() => props.talkId, () => {
	updateTalk()
})

function updateTalk() {
	if (!sessions.value) return
	const id = props.talkId
	// Use the store helper to get formatted session
	talk.value = scheduleStore.getFormattedSession(id) 
}

// Methods
function getAbsoluteResourceUrl(resource) {
	if (!pretalxApiBaseUrl.value) return resource
	try {
		const base = (new URL(pretalxApiBaseUrl.value)).origin
		return new URL(resource, base)
	} catch (e) {
		return resource
	}
}

function getRoomIdByName(name) {
	const room = rooms.value.find(r => r.name === name)
	return room ? room.id : null
}

onMounted(() => {
    // Ideally the parent view triggers fetch, or we check if loaded
    if (!scheduleStore.schedule) {
       // We need the URL. store.getters['schedule/pretalxScheduleUrl']
       const url = store.getters['schedule/pretalxScheduleUrl']
       if (url) {
           scheduleStore.fetchSchedule(url)
       }
    }
})
</script>
<style lang="stylus">
// Copied styles from item.vue
.c-schedule-talk
	display: flex
	flex-direction: column
	background-color: $clr-white
	.talk-wrapper
		flex: auto
		display: flex
		justify-content: center
	.talk
		flex: none
		margin: 16px 0 16px 16px
		max-width: 720px
		h1
			margin-bottom: 0
		.info
			font-size: 18px
			color: $clr-secondary-text-light
		.abstract
			margin: 16px 0 0 0
			font-size: 16px
			font-weight: 600
	.downloads
		border: border-separator()
		border-radius: 4px
		display: flex
		flex-direction: column
		margin-top: 16px
		h2
			margin: 4px 8px
		.download
			display: flex
			align-items: center
			height: 56px
			font-weight: 600
			font-size: 16px
			border-top: border-separator()
			&:hover
				background-color: $clr-grey-100
				text-decoration: underline
			.mdi
				font-size: 36px
				margin: 0 4px
	.btn-create
		themed-button-primary()
	.speakers
		width: 280px
		margin: 32px 16px
		display: flex
		flex-direction: column
		border: border-separator()
		border-radius: 4px
		align-self: flex-start
		.header
			border-bottom: border-separator()
			padding: 8px
		.speaker
			padding: 8px
			display: flex
			flex-direction: column
			.speaker-link
				display: flex
				align-items: center
				gap: 8px
				text-decoration: none
				color: $clr-primary-text-light
				&:hover
					.name
						color: var(--clr-primary)
						text-decoration: underline
			.avatar-circle
				border-radius: 50%
				height: 32px
				width: 32px
				flex-shrink: 0
				object-fit: cover
			.name
				font-weight: 600
				&.no-name
					color: $clr-secondary-text-light
					font-style: italic
	+below('m')
		.talk-wrapper
			display: block
		.speakers
			width: auto
		.talk
			max-width: 100%
			margin: 16px
</style>
