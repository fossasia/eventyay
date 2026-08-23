import { isRoomTypeAvailable } from './room-type-permissions.js'

export const VIDEO_CREATE_PROVIDERS = [
	{
		id: 'stream',
		roomTypeId: 'stage',
		label: 'Stream (YT, HLS)',
		roomKind: 'Stage',
		shortLabel: 'Stream',
		icon: 'theater',
		description: 'Present a live HLS or YouTube stream, optionally with chat and Q&A.',
		featureFlag: null
	},
	{
		id: 'bbb',
		roomTypeId: 'channel-bbb',
		label: 'BBB',
		roomKind: 'Video Channel',
		shortLabel: 'BBB',
		icon: 'webcam',
		description: 'Connect attendees in real time for workshops or panels powered by BigBlueButton.',
		featureFlag: null
	},
	{
		id: 'jitsi',
		roomTypeId: 'channel-jitsi',
		label: 'Jitsi',
		roomKind: 'Video Channel',
		shortLabel: 'Jitsi',
		icon: 'webcam',
		description: 'Connect attendees through a Jitsi meeting.',
		featureFlag: 'jitsi'
	},
	{
		id: 'janus',
		roomTypeId: 'channel-janus',
		label: 'Janus',
		roomKind: 'Video Channel',
		shortLabel: 'Janus',
		icon: 'webcam',
		description: 'Connect attendees in real time for workshops or panels powered by Janus.',
		featureFlag: 'janus'
	}
]

export function isVideoProviderEnabled(provider, isFeatureEnabled) {
	return !provider.featureFlag || Boolean(isFeatureEnabled(provider.featureFlag))
}

export function isVideoProviderPermitted(provider, hasPermission, isAdminMode = false) {
	if (hasPermission('room:update')) return true
	if (provider.roomTypeId === 'channel-jitsi') {
		return hasPermission('world:rooms.create.jitsi')
	}
	return isRoomTypeAvailable(provider.roomTypeId, hasPermission, isAdminMode)
}

export function getAvailableVideoProviders(hasPermission, isAdminMode, isFeatureEnabled) {
	return VIDEO_CREATE_PROVIDERS.filter(provider =>
		isVideoProviderEnabled(provider, isFeatureEnabled) &&
		isVideoProviderPermitted(provider, hasPermission, isAdminMode)
	)
}

export function getVideoProviderByRoomTypeId(roomTypeId) {
	return VIDEO_CREATE_PROVIDERS.find(provider => provider.roomTypeId === roomTypeId) || null
}

export function getConfiguredRoomLabel(type) {
	if (!type) return ''
	const provider = getVideoProviderByRoomTypeId(type.id)
	if (provider) return `${provider.roomKind}: ${provider.shortLabel}`
	if (type.id === 'channel-zoom') return 'Video Channel: Zoom'
	return type.name
}

export function getVideoProviderStartingConfig(type) {
	if (type?.id === 'stage') {
		return { playback_mode: 'always_on' }
	}
	return {}
}

export function applyVideoProviderToConfig(config, type) {
	if (!config || !type) return false
	config.module_config = [{
		type: type.startingModule,
		config: getVideoProviderStartingConfig(type)
	}]
	return true
}

export function canManageVideoRooms(hasPermission) {
	return hasPermission('room:update')
}
