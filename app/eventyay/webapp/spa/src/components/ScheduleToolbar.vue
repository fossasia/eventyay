<script setup>

import { onMounted, ref, defineProps } from 'vue'
import Toolbar from './raw-components/Toolbar.vue'


const props = defineProps({
  store: Object,
  currentDay: String
})

const emit = defineEmits(['selectDay'])

const selectDay = (day) => {
  console.log("selected day", day)
  emit('selectDay', day)
}

const scheduleContainer = ref(null)
const currentTimezone = ref(Intl.DateTimeFormat().resolvedOptions().timeZone)
const sessionsMode = ref(false)
const searchQuery = ref("")
const filterGroups = ref([])
const userTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone
onMounted(async () => {
  await props.store.fetchSchedule()

  currentTimezone.value = props.store.schedule.timezone

  filterGroups.value = [
    {
      refKey: "tracks",
      title: "Tracks",
      data: props.store.schedule.tracks.map(track => ({
        label: track.name?.de || track.name,
        value: track.id,
        color: track.color,
        selected: false
      }))
    },
    {
      refKey: "rooms",
      title: "Rooms",
      data: props.store.schedule.rooms.map(room => ({
        label: room.name?.en || room.name,
        value: room.id,
        selected: false
      }))
    }
  ]
})
  

const toggleSessionsMode = () => {
  sessionsMode.value = !sessionsMode.value
}


</script>

<template>
    <Toolbar
        v-if="props.store.schedule"
        :inEventTimezone="false"
        :version="props.store.schedule.version"
        :scheduleTimezone="props.store.schedule.timezone"
        :userTimezone="userTimezone"
        :filterGroups="filterGroups"
        :days="props.store.days"
        :currentDay="props.currentDay"
        :fullscreenTarget="scheduleContainer?.value"
        :sessionsMode="sessionsMode"
        v-model:currentTimezone="currentTimezone"
        v-model:searchQuery="searchQuery"
        :showRecordingFilter="true"
        @selectDay="selectDay"
        @toggleSessionsMode="toggleSessionsMode"
    />
</template> 

<style lang="stylus">

</style>