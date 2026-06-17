import features from 'features'

export const PLAYBACK_MODE_SCHEDULE_DRIVEN = 'schedule_driven'
export const PLAYBACK_MODE_ALWAYS_ON = 'always_on'

export const PLAYBACK_MODE_OPTIONS = [
	{
		id: PLAYBACK_MODE_SCHEDULE_DRIVEN,
		label: 'Schedule-driven stage',
		description: 'Use only the active stream schedule as the playback source.'
	},
	{
		id: PLAYBACK_MODE_ALWAYS_ON,
		label: 'Always-on stage',
		description: 'Configure a default stream source directly on this stage.'
	}
]

export const STREAM_SOURCE_OPTIONS = [
	{ id: 'hls', label: 'HLS', module: 'livestream.native' },
	{ id: 'youtube', label: 'YouTube', module: 'livestream.youtube' },
]

export function getStreamSourceOptions() {
	const options = [...STREAM_SOURCE_OPTIONS]
	if (features.enabled('iframe-player')) {
		options.push({ id: 'iframe', label: 'Iframe player', module: 'livestream.iframe' })
	}
	return options
}

export function getStagePlaybackMode(module) {
	return module?.config?.playback_mode || PLAYBACK_MODE_ALWAYS_ON
}
