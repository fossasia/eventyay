export const PLAYBACK_MODE_SCHEDULE_DRIVEN = 'schedule_driven'
export const PLAYBACK_MODE_ALWAYS_ON = 'always_on'
export const STREAM_TYPE_HLS = 'hls'
export const STREAM_TYPE_VIMEO = 'vimeo'
export const STREAM_TYPE_YOUTUBE = 'youtube'

export function translatePlaybackModeOptions(t) {
	return [
		{
			id: PLAYBACK_MODE_ALWAYS_ON,
			label: t('Always-on stage'),
			description: t('Configure a default stream source directly on this stage.')
		},
		{
			id: PLAYBACK_MODE_SCHEDULE_DRIVEN,
			label: t('Schedule-driven stage'),
			description: t('Use only the active stream schedule as the playback source.')
		}
	]
}

export function translateStreamSourceOptions(t, options = STREAM_SOURCE_OPTIONS) {
	const labels = {
		[STREAM_TYPE_HLS]: t('HLS'),
		[STREAM_TYPE_YOUTUBE]: t('YouTube'),
		[STREAM_TYPE_VIMEO]: t('Vimeo'),
	}
	return options.map(option => ({
		...option,
		label: labels[option.id] || option.label
	}))
}

const PLAYBACK_MODES = new Set([PLAYBACK_MODE_ALWAYS_ON, PLAYBACK_MODE_SCHEDULE_DRIVEN])
const STAGE_MODULE_TYPES = new Set([
	'livestream.native',
	'livestream.youtube',
])

export const STREAM_SOURCE_OPTIONS = [
	{ id: STREAM_TYPE_YOUTUBE, label: 'YouTube', module: 'livestream.youtube', icon: 'youtube' },
	{ id: STREAM_TYPE_HLS, label: 'HLS', module: 'livestream.native', icon: 'video-outline' },
]

export function getStagePlaybackMode(module) {
	if (!module) return PLAYBACK_MODE_ALWAYS_ON
	if (!STAGE_MODULE_TYPES.has(module.type)) return PLAYBACK_MODE_ALWAYS_ON

	const config = module.config || {}
	if (PLAYBACK_MODES.has(config.playback_mode)) return config.playback_mode

	const hasDefaultStreamSource = ['hls_url', 'ytid'].some(key =>
		Object.prototype.hasOwnProperty.call(config, key)
	)
	if (hasDefaultStreamSource) return PLAYBACK_MODE_ALWAYS_ON

	return PLAYBACK_MODE_SCHEDULE_DRIVEN
}

export function inferPlaybackModeFromStreams(streams = []) {
	if (!Array.isArray(streams) || streams.length === 0) return PLAYBACK_MODE_ALWAYS_ON
	if (streams.length > 1) return PLAYBACK_MODE_SCHEDULE_DRIVEN
	const first = streams[0]
	if (first && (first.start_time || first.end_time)) {
		return PLAYBACK_MODE_SCHEDULE_DRIVEN
	}
	return PLAYBACK_MODE_ALWAYS_ON
}

let uidCounter = 0
export function createDefaultStream(streamType = STREAM_TYPE_YOUTUBE) {
	return {
		uid: `stream-${Date.now()}-${++uidCounter}`,
		id: null,
		stream_type: streamType,
		url: '',
		start_time: null,
		end_time: null,
		config: {},
		showAdvanced: false,
	}
}
