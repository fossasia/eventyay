<script setup>
import GridScheduleWrapper from '@/components/raw-components/GridSchedule.vue';
import { useScheduleStore } from '@/stores/scheduleStore';
import { computed , watch, ref} from 'vue';
import moment from 'moment-timezone';
const store  = useScheduleStore()
const currentDay = ref(null)

watch(() => store.days, 
    (d) => { if (d.length && !currentDay.value) {
        currentDay.value = d[0].format("YYYY-MM-DD")
    }},
    {immediately: true}
)

const sessions = computed(() => {
    if(!store.schedule) return []

    const tz = store.schedule.timezone

    return store.schedule.talks.map(talk => ({
        ...talk,
        start: moment.tz(talk.start, tz),
        end: moment.tz(talk.end, tz),
        room: store.schedule.rooms.find(room => (room.id === talk.room))
    }))
})
</script>

<template>
   <GridScheduleWrapper v-if="store.schedule"
   :sessions="sessions"
   :rooms="store.schedule.rooms"
   :timezone="store.schedule.timezone"
   :locale="'en'"
   :current-day="currentDay"
   :now="moment()",
   :has-am-pm="true"
   :disable-auto-scroll="true"
   />
</template>