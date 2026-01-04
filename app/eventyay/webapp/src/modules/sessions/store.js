import { defineStore } from 'pinia'
import moment from 'lib/timetravelMoment'
import sessionService from './service'

export const useScheduleStore = defineStore('unifiedSchedule', {
    state: () => ({
        schedule: null,
        loading: false,
        error: null,
        currentLanguage: localStorage.getItem('userLanguage') || 'en'
    }),
    getters: {
        sessions(state) {
            if (!state.schedule) return []
            return state.schedule.talks.map(session => ({
                ...session,
                id: session.code ? session.code.toString() : null,
                start: moment(session.start),
                end: moment(session.end),
                // format speakers/rooms if needed, or do it in component
            }))
        },
        speakersLookup(state) {
            if (!state.schedule) return {}
            return state.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
        },
        roomsLookup(state) {
            if (!state.schedule) return {}
            return state.schedule.rooms.reduce((acc, r) => { acc[r.id] = r; return acc }, {})
        },
        tracksLookup(state) {
            if (!state.schedule) return {}
            return state.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
        }
    },
    actions: {
        async fetchSchedule(url) {
            // Use existing data if available globally
            if (window.eventyay?.schedule) {
                this.schedule = window.eventyay.schedule
                return
            }

            this.loading = true
            try {
                this.schedule = await sessionService.fetchSchedule(url)
            } catch (err) {
                this.error = err
                console.error('Failed to load schedule', err)
            } finally {
                this.loading = false
            }
        },
        getFormattedSession(id) {
            const session = this.sessions.find(s => s.id === id)
            if (!session) return null

            // Enrich with speaker objects
            const speakers = (session.speakers || []).map(code => this.speakersLookup[code])
            // Enrich with room object
            const room = this.roomsLookup[session.room]
            // Enrich with track object
            const track = this.tracksLookup[session.track]

            return {
                ...session,
                speakers,
                room,
                track
            }
        }
    }
})
