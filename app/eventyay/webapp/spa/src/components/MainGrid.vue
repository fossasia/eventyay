<script setup>
import GridScheduleWrapper from '@/components/raw-components/GridScheduleWrapper.vue';
import { computed} from 'vue';
import moment from 'moment-timezone';

const props = defineProps({
  store: Object,
  currentDay: String
})

const sessions = computed(() => {
    if(!props.store.schedule) return []

    const tz = props.store.schedule.timezone

    return props.store.schedule.talks.map(talk => ({
        ...talk,
        start: moment.tz(talk.start, tz),
        end: moment.tz(talk.end, tz),
        room: props.store.schedule.rooms.find(room => (room.id === talk.room))
    }))
})
</script>

<template>
   <GridScheduleWrapper v-if="props.store.schedule"
   :sessions="sessions"
   :rooms="props.store.schedule.rooms"
   :timezone="props.store.schedule.timezone"
   :locale="'en'"
   :currentDay="props.currentDay"
   :now="moment()"
   :has-am-pm="true"
   :disable-auto-scroll="true"
   :forceScrollDay="0"
   />
</template>