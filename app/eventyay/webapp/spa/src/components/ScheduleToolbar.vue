<script setup>

import moment from 'moment-timezone'
import { computed, onMounted, ref, watch } from 'vue'
import Toolbar from './raw-components/Toolbar.vue'
import { useScheduleStore } from '@/stores/scheduleStore'

const store = useScheduleStore()

const scheduleContainer = ref(null)
const currentTimezone = ref(Intl.DateTimeFormat().resolvedOptions().timeZone)
const sessionsMode = ref(false)
const searchQuery = ref("")
const currentDay = ref(null)
const filterGroups = ref([])

onMounted(async () => {
  await store.fetchSchedule()

  currentTimezone.value = store.schedule.timezone

  filterGroups.value = [
    {
      refKey: "tracks",
      title: "Tracks",
      data: store.schedule.tracks.map(track => ({
        label: track.name?.de || track.name,
        value: track.id,
        color: track.color,
        selected: false
      }))
    },
    {
      refKey: "rooms",
      title: "Rooms",
      data: store.schedule.rooms.map(room => ({
        label: room.name?.en || room.name,
        value: room.id,
        selected: false
      }))
    }
  ]
})
  
watch(() => store.days, 
(d) => {
  if (d.length && !currentDay.value) {
    currentDay.value = d[0].format("YYYY-MM-DD")
  }}
  ,{immediately: true})

const selectDay = (day) => {
  currentDay.value = day
}

const toggleSessionsMode = () => {
  sessionsMode.value = !sessionsMode.value
}

</script>

<template>
    <Toolbar
        v-if="store.schedule"
        :inEventTimezone="false"
        :version="store.schedule.version"
        :scheduleTimezone="store.schedule.timezone"
        :userTimezone="Intl.DateTimeFormat().resolvedOptions().timeZone"
        :filterGroups="filterGroups"
        :days="store.days"
        :currentDay="currentDay"
        :fullscreenTarget="scheduleContainer?.value"
        :sessionsMode="sessionsMode"
        v-model:currentTimezone="currentTimezone"
        v-model:searchQuery="searchQuery"
        @selectDay="selectDay"
        @toggleSessionsMode="toggleSessionsMode"
    />
</template> 

<style lang="stylus">

</style>