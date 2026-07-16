import features from 'features'

export const PLAYBACK_MODE_SCHEDULE_DRIVEN = 'schedule_driven'
export const PLAYBACK_MODE_ALWAYS_ON = 'always_on'
export const STREAM_TYPE_HLS = 'hls'
export const STREAM_TYPE_IFRAME = 'iframe'
export const STREAM_TYPE_VIMEO = 'vimeo'
export const STREAM_TYPE_YOUTUBE = 'youtube'
export const IFRAME_PROVIDER_HELP_TEXT = 'Use an autoplaying, responsive embed/player URL. Supports YouTube, Vimeo, Dailymotion, Twitch, PeerTube, or any provider that allows iframe embedding.'

export const PLAYBACK_MODE_OPTIONS = [
	{
		id: PLAYBACK_MODE_ALWAYS_ON,
		label: 'Always-on stage',
		description: 'Configure a default stream source directly on this stage.'
	},
	{
		id: PLAYBACK_MODE_SCHEDULE_DRIVEN,
		label: 'Schedule-driven stage',
		description: 'Use only the active stream schedule as the playback source.'
	}
]

const PLAYBACK_MODES = new Set([PLAYBACK_MODE_ALWAYS_ON, PLAYBACK_MODE_SCHEDULE_DRIVEN])
const STAGE_MODULE_TYPES = new Set([
	'livestream.native',
	'livestream.youtube',
	'livestream.iframe',
])

export const STREAM_SOURCE_OPTIONS = [
	{ id: STREAM_TYPE_HLS, label: 'HLS', module: 'livestream.native' },
	{ id: STREAM_TYPE_YOUTUBE, label: 'YouTube', module: 'livestream.youtube' },
]

export function getStreamSourceOptions() {
	const options = [...STREAM_SOURCE_OPTIONS]
	if (features.enabled('iframe-player')) {
		options.push({ id: STREAM_TYPE_IFRAME, label: 'Iframe player', module: 'livestream.iframe' })
	}
	return options
}

export function getStagePlaybackMode(module) {
	if (!module) return PLAYBACK_MODE_ALWAYS_ON
	if (!STAGE_MODULE_TYPES.has(module.type)) return PLAYBACK_MODE_ALWAYS_ON

	const config = module.config || {}
	if (PLAYBACK_MODES.has(config.playback_mode)) return config.playback_mode

	const hasDefaultStreamSource = ['hls_url', 'ytid', 'url'].some(key =>
		Object.prototype.hasOwnProperty.call(config, key)
	)
	if (hasDefaultStreamSource) return PLAYBACK_MODE_ALWAYS_ON

	return PLAYBACK_MODE_SCHEDULE_DRIVEN
}
