import moment from 'lib/timetravelMoment'
import config from '../../config'

// Thin adapter: loads schedule data and provides enriched sessions.
// Filtering/export/timezone are handled by the shared ScheduleView/ScheduleToolbar.
// Favs use localStorage with event-scoped key to stay in sync with the agenda side.

function getFavStorageKey () {
	const slug = window.eventyay?.eventSlug
	if (slug) return `${slug}_favs`
	// Fallback: extract event slug from basePath (e.g. /org/event/video)
	const basePath = window.eventyay?.basePath || ''
	const segments = basePath.split('/').filter(s => s.length > 0 && s !== 'video')
	const eventSlug = segments[segments.length - 1] || ''
	return eventSlug ? `${eventSlug}_favs` : 'schedule_favs'
}

function loadFavsFromStorage () {
	try {
		return JSON.parse(localStorage.getItem(getFavStorageKey())) || []
	} catch {
		return []
	}
}

function saveFavsToStorage (favs) {
	localStorage.setItem(getFavStorageKey(), JSON.stringify(favs))
}

function getCsrfToken () {
	const match = document.cookie.match(/eventyay_csrftoken=([^;]+)/)
	return match ? match[1] : null
}

function getApiBase () {
	return config?.api?.base || ''
}

export default {
	namespaced: true,
	state: {
		schedule: null,
		scheduleMeta: null,
		errorLoading: null,
		now: moment(),
		currentLanguage: localStorage.getItem('userLanguage') || 'en',
		favs: loadFavsFromStorage()
	},
	getters: {
		favs (state) {
			return state.favs
		},
		rooms (state, getters, rootState) {
			if (!state.schedule) return
			return state.schedule.rooms.map(room => rootState.rooms.find(r => r.pretalx_id === room.id) || room)
		},
		roomsLookup (state, getters) {
			if (!state.schedule) return {}
			return getters.rooms.reduce((acc, room) => {
				acc[room.pretalx_id || room.id] = room
				return acc
			}, {})
		},
		tracksLookup (state) {
			if (!state.schedule) return {}
			return state.schedule.tracks.reduce((acc, t) => { acc[t.id] = t; return acc }, {})
		},
		speakersLookup (state) {
			if (!state.schedule) return {}
			return state.schedule.speakers.reduce((acc, s) => { acc[s.code] = s; return acc }, {})
		},
		sessions (state, getters, rootState) {
			if (!state.schedule) return
			const sessions = []
			for (const session of state.schedule.talks) {
				sessions.push({
					id: session.code ? session.code.toString() : null,
					title: session.title,
					abstract: session.abstract,
					description: session.description,
					do_not_record: session.do_not_record,
					url: session.url,
					start: moment.tz(session.start, rootState.userTimezone),
					end: moment.tz(session.end, rootState.userTimezone),
					speakers: session.speakers?.map(s => getters.speakersLookup[s]),
					track: getters.tracksLookup[session.track],
					room: getters.roomsLookup[session.room],
					fav_count: session.fav_count,
					tags: session.tags,
					session_type: session.session_type,
					resources: session.resources,
					answers: session.answers,
					exporters: session.exporters,
					recording_iframe: session.recording_iframe
				})
			}
			sessions.sort((a, b) => (
				a.start.diff(b.start) ||
				(state.schedule.rooms.findIndex((r) => r.id === a.room?.id) - state.schedule.rooms.findIndex((r) => r.id === b.room?.id))
			))
			return sessions
		},
		sessionsLookup (state, getters) {
			if (!state.schedule) return {}
			return getters.sessions.reduce((acc, s) => { acc[s.id] = s; return acc }, {})
		},
		days (state, getters) {
			if (!getters.sessions) return
			const days = []
			for (const session of getters.sessions) {
				if (days[days.length - 1] && days[days.length - 1].isSame(session.start, 'day')) continue
				days.push(session.start.clone().startOf('day'))
			}
			return days
		},
		sessionsScheduledNow (state, getters, rootState) {
			if (!getters.sessions) return
			const sessions = []
			for (const session of getters.sessions) {
				if (session.end.isBefore(rootState.now) || session.start.isAfter(rootState.now)) continue
				sessions.push(session)
			}
			return sessions
		},
		currentSessionPerRoom (state, getters, rootState) {
			if (!getters.sessions) return
			const rooms = {}
			for (const room of rootState.rooms) {
				if (room.schedule_data?.computeSession) {
					rooms[room.id] = {
						session: getters.sessionsScheduledNow.find(session => session.room === room)
					}
				} else if (room.schedule_data?.session) {
					rooms[room.id] = {
						session: getters.sessions?.find(session => session.id === room.schedule_data.session)
					}
				}
			}
			return rooms
		},
		schedule (state) {
			return state.schedule
		},
		exporters (state) {
			return state.scheduleMeta?.exporters || []
		},
		scheduleMetaData (state) {
			return state.scheduleMeta || {}
		},
		getSessionType: (state) => (item) => {
			if (typeof item?.session_type === 'string') {
				return item.session_type
			} else if (typeof item?.session_type === 'object') {
				const keys = Object.keys(item.session_type)
				const keyLanguage = keys.find(k => k === state.currentLanguage) ||
					keys.find(k => k === 'en') ||
					keys[0]
				return item.session_type[keyLanguage]
			}
			return null
		},
		getSelectedName: (state) => (item) => {
			if (typeof item?.name === 'string') {
				return item.name
			} else if (typeof item?.name === 'object') {
				const keys = Object.keys(item.name)
				const keyLanguage = keys.find(k => k === state.currentLanguage) ||
					keys.find(k => k === 'en') ||
					keys[0]
				return item.name[keyLanguage]
			}
			return null
		}
	},
	actions: {
		async fetch ({ state }) {
			try {
				state.errorLoading = null
				if (window.eventyay?.schedule) {
					state.schedule = window.eventyay.schedule
				}
				if (window.eventyay?.scheduleMeta) {
					state.scheduleMeta = window.eventyay.scheduleMeta
				}
			} catch (error) {
				state.errorLoading = error
			}
		},
		async fav ({ state, rootState }, id) {
			if (!state.favs.includes(id)) {
				state.favs.push(id)
				saveFavsToStorage(state.favs)
			}
			const apiBase = getApiBase()
			if (apiBase && rootState.user) {
				try {
					const headers = { 'Content-Type': 'application/json' }
					const csrf = getCsrfToken()
					if (csrf) headers['X-CSRFToken'] = csrf
					await fetch(`${apiBase}submissions/${id}/favourite/`, {
						method: 'POST',
						headers,
						credentials: 'same-origin'
					})
				} catch (error) {
					console.error('Failed to save favourite: %s', error)
				}
			}
		},
		async unfav ({ state, rootState }, id) {
			state.favs = state.favs.filter(fav => fav !== id)
			saveFavsToStorage(state.favs)
			const apiBase = getApiBase()
			if (apiBase && rootState.user) {
				try {
					const headers = { 'Content-Type': 'application/json' }
					const csrf = getCsrfToken()
					if (csrf) headers['X-CSRFToken'] = csrf
					await fetch(`${apiBase}submissions/${id}/favourite/`, {
						method: 'DELETE',
						headers,
						credentials: 'same-origin'
					})
				} catch (error) {
					console.error('Failed to remove favourite: %s', error)
				}
			}
		},
		async loadFavs ({ state, rootState }) {
			const localFavs = loadFavsFromStorage()
			state.favs = localFavs
			const apiBase = getApiBase()
			if (apiBase && rootState.user) {
				try {
					const headers = { 'Content-Type': 'application/json' }
					const csrf = getCsrfToken()
					if (csrf) headers['X-CSRFToken'] = csrf
					const response = await fetch(`${apiBase}submissions/favourites/merge/`, {
						method: 'POST',
						headers,
						body: JSON.stringify(localFavs),
						credentials: 'same-origin'
					})
					if (response.ok) {
						const merged = await response.json()
						if (Array.isArray(merged)) {
							state.favs = merged
							saveFavsToStorage(merged)
						}
					}
				} catch (error) {
					console.error('Failed to merge favourites: %s', error)
				}
			}
		},
		setCurrentLanguage ({ commit }, language) {
			commit('setCurrentLanguage', language)
		}
	},
	mutations: {
		setCurrentLanguage (state, language) {
			state.currentLanguage = language
		}
	}
}
