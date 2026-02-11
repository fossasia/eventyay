/**
 * Thin Vuex→props adapter components that connect the video store
 * to shared schedule components. No UI logic lives here — it's all
 * in the shared module at @schedule/components/.
 */
import { defineComponent, h, computed, provide } from 'vue'
import { useStore } from 'vuex'
import { useRouter } from 'vue-router'
import moment from 'lib/timetravelMoment'
import TalkDetail from '@schedule/components/TalkDetail'
import SpeakersList from '@schedule/components/SpeakersList'
import SpeakerDetail from '@schedule/components/SpeakerDetail'

export const VideoTalk = defineComponent({
	name: 'VideoTalk',
	props: { talkId: String },
	setup(props) {
		const store = useStore()
		const router = useRouter()
		const sessions = computed(() => store.getters['schedule/sessions'])
		const rooms = computed(() => store.state.rooms)

		const talk = computed(() => {
			if (!sessions.value) return null
			return sessions.value.find(s => s.id === props.talkId) || null
		})

		const joinRoomId = computed(() => {
			if (!talk.value?.room || !rooms.value) return null
			const room = rooms.value.find(r => r.name === roomName.value || r.id === talk.value.room.id)
			return room?.id || null
		})

		const roomName = computed(() => {
			if (!talk.value?.room) return ''
			const name = talk.value.room?.name || talk.value.room
			if (typeof name === 'object') return name.en || Object.values(name)[0] || ''
			return name
		})

		provide('generateSpeakerLinkUrl', ({speaker}) => {
			return router.resolve({name: 'schedule:speaker', params: {speakerId: speaker.code}}).href
		})
		provide('onSpeakerLinkClick', async (event, speaker) => {
			event.preventDefault()
			await router.push({name: 'schedule:speaker', params: {speakerId: speaker.code}})
		})

		return () => h(TalkDetail, {
			talk: talk.value,
			showJoinRoom: !!joinRoomId.value,
			joinRoomLink: joinRoomId.value
				? router.resolve({name: 'room', params: {roomId: joinRoomId.value}}).href
				: '',
			onJoinRoom: (event) => {
				if (joinRoomId.value) {
					event.preventDefault()
					router.push({name: 'room', params: {roomId: joinRoomId.value}})
				}
			}
		})
	}
})

export const VideoSpeakers = defineComponent({
	name: 'VideoSpeakers',
	setup() {
		const store = useStore()
		const router = useRouter()
		const schedule = computed(() => store.state.schedule.schedule)
		const sessions = computed(() => store.getters['schedule/sessions'])

		const speakers = computed(() => {
			if (!schedule.value?.speakers) return []
			return schedule.value.speakers.map(speaker => ({
				...speaker,
				sessions: (sessions.value || []).filter(session =>
					session.speakers?.some(s => s.code === speaker.code)
				)
			}))
		})

		provide('generateSpeakerLinkUrl', ({speaker}) => {
			return router.resolve({name: 'schedule:speaker', params: {speakerId: speaker.code}}).href
		})
		provide('onSpeakerLinkClick', async (event, speaker) => {
			event.preventDefault()
			await router.push({name: 'schedule:speaker', params: {speakerId: speaker.code}})
		})

		return () => h(SpeakersList, {
			speakers: speakers.value
		})
	}
})

export const VideoSpeaker = defineComponent({
	name: 'VideoSpeaker',
	props: { speakerId: String },
	setup(props) {
		const store = useStore()
		const router = useRouter()
		const sessions = computed(() => store.getters['schedule/sessions'])
		const favs = computed(() => store.getters['schedule/favs'] || [])
		const now = computed(() => store.state.now)
		const timezone = computed(() => {
			return localStorage.getItem('userTimezone') || moment.tz.guess()
		})
		const hasAmPm = new Intl.DateTimeFormat(undefined, {hour: 'numeric'}).resolvedOptions().hour12

		const speaker = computed(() => {
			if (!sessions.value) return null
			for (const session of sessions.value) {
				if (!session.speakers) continue
				const found = session.speakers.find(s => s.code === props.speakerId)
				if (found) return found
			}
			return null
		})

		const speakerSessions = computed(() => {
			if (!sessions.value) return []
			return sessions.value.filter(s =>
				s.speakers?.some(sp => sp.code === props.speakerId)
			)
		})

		provide('generateSessionLinkUrl', ({session}) => {
			return router.resolve({name: 'schedule:talk', params: {talkId: session.id}}).href
		})
		provide('onSessionLinkClick', async (event, session) => {
			event.preventDefault()
			await router.push({name: 'schedule:talk', params: {talkId: session.id}})
		})

		return () => h(SpeakerDetail, {
			speaker: speaker.value,
			sessions: speakerSessions.value,
			now: now.value,
			timezone: timezone.value,
			hasAmPm,
			favs: favs.value,
			onFav: (id) => store.dispatch('schedule/fav', id),
			onUnfav: (id) => store.dispatch('schedule/unfav', id)
		})
	}
})
