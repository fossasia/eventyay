import { defineStore } from 'pinia'
import axios from 'axios'
import { eventConfig } from '@/config/config'
import moment from 'moment-timezone'

export const useScheduleStore = defineStore('schedule', {
  state: () => ({
    schedule: null,
    loading: false
  }),

  actions: {
    async fetchSchedule() {
      if(this.schedule) return

      this.loading = true

      try {
        const res = await axios.get(`${eventConfig.eventUrl}/schedule/widget/v2.json`)
        this.schedule = res.data
      } catch (error) {
        console.error("Failed to fetch schedule", error)
      }finally{
        this.loading = false
      }      
    }
  },

  getters: {
    
    days(state){
      if (!state.schedule) return []
      const tz = state.schedule.timezone
  
      const start = moment.tz(state.schedule.event_start, tz)
      const end = moment.tz(state.schedule.event_end, tz).add(1, 'day')

      const result = []
      const current = start.clone()

      while (current.isSameOrBefore(end)) {
        result.push(current.clone())
        current.add(1, 'day')
      }
      return result
    }
  
  }
})
