<template lang="pug">
.c-speaker-list(v-scrollbar.y="")
	.wrapper
		h1 {{ $t('schedule/speakers:header') }}
		.speaker-grid(v-if="speakers && speakers.length > 0")
			router-link.speaker-card(v-for="speaker in speakers" :key="speaker.code" :to="{name: 'schedule:speaker', params: {speakerId: speaker.code}}")
				img.avatar(v-if="speaker.avatar || speaker.avatar_url" :src="speaker.avatar || speaker.avatar_url")
				identicon.avatar(v-else :user="{id: speaker.code, profile: {display_name: speaker.name || 'Speaker'}}")
				.name {{ speaker.name }}
		bunt-progress-circular(v-else-if="loading" size="huge" :page="true")
		.empty(v-else) No speakers found.
</template>
<script setup>
import { computed, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useSpeakerStore } from '../store'
import Identicon from 'components/Identicon'

const store = useStore()
const speakerStore = useSpeakerStore()

const loading = computed(() => speakerStore.loading)
const speakers = computed(() => speakerStore.speakersLookup ? Object.values(speakerStore.speakersLookup).sort((a,b) => a.name.localeCompare(b.name)) : [])

onMounted(() => {
	if (!speakerStore.schedule) {
	   const url = store.getters['schedule/pretalxScheduleUrl']
	   if (url) speakerStore.fetchSchedule(url)
	}
})
</script>
<style lang="stylus">
.c-speaker-list
	display: flex
	flex-direction: column
	background-color: $clr-white
	.wrapper
		max-width: 1200px
		margin: 0 auto
		width: 100%
		padding: 16px
	.speaker-grid
		display: grid
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr))
		gap: 16px
		margin-top: 16px
	.speaker-card
		display: flex
		flex-direction: column
		align-items: center
		text-decoration: none
		color: $clr-primary-text-light
		padding: 16px
		border-radius: 8px
		&:hover
			background-color: $clr-grey-100
		.avatar
			width: 128px
			height: 128px
			border-radius: 50%
			object-fit: cover
			margin-bottom: 8px
		.name
			font-weight: 600
			text-align: center
</style>
