import { isUsableAudioTranslationEntry } from 'lib/validators'

export function roomUsesPluginLanguageStreams(room) {
	return Boolean(room?.interpretation_use_plugin_streams)
}

export function pluginLanguageStreams(room) {
	if (!roomUsesPluginLanguageStreams(room)) {
		return null
	}
	const streams = room?.interpretation_language_streams
	if (!Array.isArray(streams)) {
		return []
	}
	return streams.filter(entry => isUsableAudioTranslationEntry(entry))
}

export function initializeLanguageList({ room, modules, coreInitializer }) {
	if (roomUsesPluginLanguageStreams(room)) {
		return pluginLanguageStreams(room)
	}
	return coreInitializer({ room, modules })
}
