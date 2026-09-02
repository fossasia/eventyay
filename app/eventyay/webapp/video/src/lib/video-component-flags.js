export const MODULE_FEATURE_FLAGS = {
	'livestream.native': 'stream',
	'livestream.youtube': 'stream',
	'livestream.iframe': 'stream',
	'call.bigbluebutton': 'bbb',
	'call.jitsi': 'jitsi',
	'call.janus': 'janus',
	'chat.native': 'chat',
	question: 'question',
	poll: 'polls',
}

const PRIMARY_MEDIA_MODULES = [
	'livestream.native',
	'livestream.youtube',
	'livestream.iframe',
	'call.bigbluebutton',
	'call.jitsi',
	'call.janus',
	'call.zoom',
]

const SIDEBAR_ADDON_MODULES = {
	'chat.native': 'chat',
	question: 'question',
	poll: 'polls',
}

export function isModuleFeatureEnabled(moduleType, isFeatureEnabled) {
	const featureFlag = MODULE_FEATURE_FLAGS[moduleType]
	if (!featureFlag) return true
	return Boolean(isFeatureEnabled(featureFlag))
}

export function isSidebarAddonModule(moduleType) {
	return Object.prototype.hasOwnProperty.call(SIDEBAR_ADDON_MODULES, moduleType)
}

export function hasAnySidebarAddonFeature(isFeatureEnabled) {
	return Object.values(SIDEBAR_ADDON_MODULES).some(flag => isFeatureEnabled(flag))
}

export function stripDisabledSidebarModules(moduleConfig, isFeatureEnabled) {
	if (!Array.isArray(moduleConfig)) return moduleConfig
	return moduleConfig.filter(module => {
		if (!module || typeof module !== 'object') return true
		const featureFlag = SIDEBAR_ADDON_MODULES[module.type]
		if (!featureFlag) return true
		return isFeatureEnabled(featureFlag)
	})
}

export function getDisabledModuleLabel(moduleType, t) {
	const labels = {
		'livestream.native': t('Streaming'),
		'livestream.youtube': t('Streaming'),
		'livestream.iframe': t('Streaming'),
		'call.bigbluebutton': t('BigBlueButton'),
		'call.jitsi': t('Jitsi'),
		'call.janus': t('Janus'),
		'chat.native': t('Chat'),
		question: t('Q&A'),
		poll: t('Polls'),
	}
	return labels[moduleType] || moduleType
}

export function getDisabledPrimaryModule(modules, isFeatureEnabled, moduleCount = 0) {
	for (const moduleType of PRIMARY_MEDIA_MODULES) {
		if (modules?.[moduleType] && !isModuleFeatureEnabled(moduleType, isFeatureEnabled)) {
			return moduleType
		}
	}

	const isStandaloneChat = modules?.['chat.native'] && moduleCount === 1
	if (isStandaloneChat && !isModuleFeatureEnabled('chat.native', isFeatureEnabled)) {
		return 'chat.native'
	}

	return null
}

export function roomHasEnabledMediaModule(room, isFeatureEnabled) {
	if (!room?.modules) return false
	return room.modules.some(module =>
		PRIMARY_MEDIA_MODULES.includes(module.type) &&
		isModuleFeatureEnabled(module.type, isFeatureEnabled)
	)
}
