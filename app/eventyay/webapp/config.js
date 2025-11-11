/* global ENV_DEVELOPMENT */
import cloneDeep from 'lodash/cloneDeep'
let config
if (ENV_DEVELOPMENT || (!window.venueless && !window.eventyay)) {
	const { protocol, hostname, port, pathname } = window.location
	const wsProtocol = protocol === 'https:' ? 'wss' : 'ws'
	const segments = pathname.split('/').filter(Boolean)
	const videoIndex = segments.lastIndexOf('video')
	const baseSegments = videoIndex > -1 ? segments.slice(0, videoIndex + 1) : []
	let basePath = baseSegments.length ? `/${baseSegments.join('/')}` : '/video'
	if (basePath.length > 1 && basePath.endsWith('/')) {
		basePath = basePath.slice(0, -1)
	}
	// Example mappings:
	//   /video/sample -> eventSlug === 'sample'
	//   /org/acmeconf/video -> eventSlug === 'acmeconf'
	let eventSlug
	if (videoIndex > 0 && segments[videoIndex - 1]) {
		eventSlug = segments[videoIndex - 1]
	} else if (segments[1]) {
		eventSlug = segments[1]
	} else if (segments[0] && segments[0] !== 'video') {
		eventSlug = segments[0]
	} else {
		eventSlug = 'sample'
	}
	const hostPort = port ? `${hostname}:${port}` : hostname
	config = {
		api: {
			base: `${protocol}//${hostPort}/api/v1/events/${eventSlug}/`,
			socket: `${wsProtocol}://${hostPort}/ws/event/${eventSlug}/`,
			upload: `${protocol}//${hostPort}/storage/${eventSlug}/upload/`,
			scheduleImport: `${protocol}//${hostPort}/storage/${eventSlug}/schedule_import/`,
			feedback: `${protocol}//${hostPort}/_feedback/`,
		},
		defaultLocale: 'en',
		locales: ['en', 'de', 'pt_BR', 'ar', 'fr', 'es', 'uk', 'ru'],
		// Mark that there is no theme endpoint so theme.js can skip fetch
		noThemeEndpoint: true,
		features: [],
		theme: {
			logo: {
				url: `${basePath}/eventyay-video-logo.png`,
				fitToWidth: false
			},
			colors: {
				primary: '#2185d0',
				sidebar: '#2185d0',
				bbb_background: '#ffffff',
			}
		},
		basePath
	}
} else {
	// load from index.html as injected config: prefer window.eventyay (new) else fallback to legacy window.venueless
	const injected = window.eventyay || window.venueless
	config = cloneDeep(injected)
	// Normalize features to array for consumer convenience (feature flags object => enabled keys array)
	if (config.features && !Array.isArray(config.features)) {
		config.features = Object.keys(config.features).filter(k => config.features[k])
	}
}
export default config
