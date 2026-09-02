/* global ENV_DEVELOPMENT */

import config from 'config'

const PLATFORM_VIDEO_FLAGS = new Set([
	'chat',
	'question',
	'polls',
	'stream',
	'bbb',
	'jitsi',
	'janus',
])

function isFeatureEnabled(feature) {
	const feats = config.features
	if (Array.isArray(feats)) return feats.includes(feature)
	if (feats && typeof feats === 'object') return Boolean(feats[feature])
	return false
}

export default {
	enabled(feature) {
		if (PLATFORM_VIDEO_FLAGS.has(feature)) {
			return isFeatureEnabled(feature)
		}
		if (ENV_DEVELOPMENT) return true
		return isFeatureEnabled(feature)
	}
}
