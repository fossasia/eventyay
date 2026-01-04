<template lang="pug">
.c-schedule-speaker
	bunt-progress-circular(v-if="!speaker" size="huge" :page="true")
	scrollbars(v-else y="")
		.profile
			img.avatar(v-if="speaker.avatar || speaker.avatar_url" :src="speaker.avatar || speaker.avatar_url")
			identicon(v-else :user="{id: speaker.code, profile: {display_name: speaker.name || 'Speaker'}}")
			.content
				h1(:class="{'no-name': !speaker.name}") {{ speaker.name || 'Speaker name not provided' }}
				markdown-content.biography(:markdown="speaker.biography")
		.sessions
			h2 {{ $t('schedule/speakers/item:sessions:header') }}
			session(
				v-for="session of speakerSessions"
				:key="session.id"
				:session="session"
				:now="now"
				:faved="false"
			)
</template>
<script setup>
import { computed, watch, ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useSpeakerStore } from '../store'
import Identicon from 'components/Identicon'
import MarkdownContent from 'components/MarkdownContent'
import Session from 'views/schedule/schedule-components/Session.vue'

const props = defineProps(['speakerId', 'context'])

const store = useStore()
const speakerStore = useSpeakerStore()

const now = computed(() => store.state.now)
const schedule = computed(() => speakerStore.schedule)
const speaker = ref(null)

const speakerSessions = computed(() => {
	if (!speaker.value || !speakerStore.sessions) return []
	return speakerStore.sessions.filter(session => 
		session.speakers && session.speakers.some(s => s && s.code === speaker.value.code)
	)
})

watch(() => [schedule.value, props.speakerId], () => {
    if (schedule.value && props.speakerId) {
        // speakersLookup is in store getters
        speaker.value = speakerStore.speakersLookup[props.speakerId] || 
                        Object.values(speakerStore.speakersLookup).find(s => s.id === props.speakerId)
    }
}, { immediate: true })

onMounted(() => {
	if (!speakerStore.schedule) {
	   const url = store.getters['schedule/pretalxScheduleUrl']
	   if (url) speakerStore.fetchSchedule(url)
	}
})
</script>
<style lang="stylus">
.c-schedule-speaker
	display: flex
	background-color: $clr-white
	flex-direction: column
	min-height: 0
	.c-scrollbars
		.scroll-content
			display: flex
			flex-direction: column
			align-items: center
			> *
				width: @css{min(920px, 100%)}
	.speaker
		display: flex
		flex-direction: column
	.profile
		display: flex
		gap: 16px
		img
			border-radius: 50%
			height: 256px
			width: @height
			object-fit: cover
			padding: 16px
		h1
			margin: 24px 0 16px
			&.no-name
				color: $clr-secondary-text-light
				font-style: italic
		.content
			flex: auto
			margin-right: 16px
	.sessions
		h2
			margin: 16px
	+below('s')
		.profile
			flex-direction: column
			align-items: center
		.content
			margin: 0 16px
</style>
