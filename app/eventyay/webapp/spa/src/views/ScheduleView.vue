<script setup>
import { useScheduleStore } from '@/stores/scheduleStore';
import { ref,watch } from 'vue';
import MainGrid from '@/components/MainGrid.vue';
import ScheduleToolbar from '@/components/ScheduleToolbar.vue';

const store  = useScheduleStore()
const currentDay = ref(null)
watch(() => store.days, 
(d) => {
  if (d.length && !currentDay.value) {
    console.log("parent currentDay updated:", d)
    currentDay.value = d[0].format("YYYY-MM-DD")
  }}
  ,{immediate: true})
   
</script>

<template>
    <ScheduleToolbar :store="store" :current-day="currentDay"
    @select-day="currentDay = $event"/>
    <MainGrid :store="store" :current-day="currentDay"/>
</template>
