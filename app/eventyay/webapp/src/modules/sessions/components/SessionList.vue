<template lang="pug">
.c-session-list
	linear-schedule(
		v-if="sessions && sessions.length > 0"
		:sessions="sessions" 
		:rooms="rooms"
		:currentDay="currentDay"
		:now="now"
		:favs="[]" 
		@changeDay="changeDay"
	)
	bunt-progress-circular(v-else-if="loading" size="huge" :page="true")
	.empty(v-else) No sessions found.
</template>
<script setup>
import { computed, ref, onMounted } from 'vue'
import { useStore } from 'vuex'
import { useScheduleStore } from '../../sessions/store' // Import from sessions store
import LinearSchedule from 'views/schedule/schedule-components/LinearSchedule'
import moment from 'lib/timetravelMoment'

const props = defineProps(['context'])
const store = useStore()
const scheduleStore = useScheduleStore()

const now = computed(() => store.state.now)
const loading = computed(() => scheduleStore.loading)
const sessions = computed(() => scheduleStore.sessions)
const rooms = computed(() => Object.values(scheduleStore.roomsLookup))

const currentDay = ref(moment().startOf('day'))

function changeDay(day) {
	currentDay.value = day
}

onMounted(() => {
	if (!scheduleStore.schedule) {
	   const url = store.getters['schedule/pretalxScheduleUrl']
	   if (url) scheduleStore.fetchSchedule(url)
	}
})
</script>
