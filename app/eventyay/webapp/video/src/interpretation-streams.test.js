import test from 'node:test'
import assert from 'node:assert/strict'
import {
	roomUsesPluginLanguageStreams,
	pluginLanguageStreams,
	firstCaptionLanguage,
} from './interpretation-streams.js'
import {
	isUsableAudioTranslationEntry,
	normalizeAudioTranslationSource,
	normalizeYoutubeVideoId,
} from './lib/validators.js'

test('roomUsesPluginLanguageStreams returns true when room has interpretation_use_plugin_streams', () => {
	assert.equal(roomUsesPluginLanguageStreams({ interpretation_use_plugin_streams: true }), true)
})

test('roomUsesPluginLanguageStreams returns true when active stream schedule defines language_streams', () => {
	const room = {
		interpretation_use_plugin_streams: false,
		currentStream: {
			config: {
				language_streams: [
					{ language: 'German', url: 'https://example.com/live/de/whep', use_video: false },
				],
			},
		},
	}
	assert.equal(roomUsesPluginLanguageStreams(room), true)
})

test('roomUsesPluginLanguageStreams returns true when active stream schedule defines legacy languageUrls', () => {
	const room = {
		interpretation_use_plugin_streams: false,
		currentStream: {
			config: {
				languageUrls: [
					{ language: 'Spanish', url: 'https://example.com/live/es/whep' },
				],
			},
		},
	}
	assert.equal(roomUsesPluginLanguageStreams(room), true)
})

test('roomUsesPluginLanguageStreams returns false when neither room flag nor schedule channels exist', () => {
	assert.equal(roomUsesPluginLanguageStreams(null), false)
	assert.equal(roomUsesPluginLanguageStreams({}), false)
	assert.equal(roomUsesPluginLanguageStreams({
		interpretation_use_plugin_streams: false,
		currentStream: { config: { language_streams: [] } },
	}), false)
})

test('pluginLanguageStreams returns empty array if room does not use plugin streams', () => {
	assert.deepEqual(pluginLanguageStreams({}), [])
})

test('pluginLanguageStreams prioritizes active schedule language streams over room-level streams', () => {
	const room = {
		interpretation_use_plugin_streams: true,
		interpretation_language_streams: [
			{ language: 'RoomFrench', url: 'https://example.com/room-fr' },
		],
		currentStream: {
			config: {
				language_streams: [
					{ language: 'ScheduleSpanish', url: 'https://example.com/sched-es/whep' },
				],
			},
		},
	}
	const streams = pluginLanguageStreams(room)
	assert.equal(streams[0].language, 'Original')
	assert.equal(streams[1].language, 'ScheduleSpanish')
	assert.equal(streams.some(s => s.language === 'RoomFrench'), false)
})

test('pluginLanguageStreams falls back to room interpretation_language_streams when schedule has none', () => {
	const room = {
		interpretation_use_plugin_streams: true,
		interpretation_language_streams: [
			{ language: 'RoomGerman', url: 'https://example.com/room-de/whep' },
		],
		currentStream: {
			config: {
				language_streams: [],
			},
		},
	}
	const streams = pluginLanguageStreams(room)
	assert.equal(streams[0].language, 'Original')
	assert.equal(streams[1].language, 'RoomGerman')
})

test('pluginLanguageStreams preserves caption-only entries without audio URL', () => {
	const room = {
		interpretation_use_plugin_streams: true,
		interpretation_language_streams: [
			{ language: 'English Captions', caption_ws_url: 'wss://example.com/ws/captions' },
		],
	}
	const streams = pluginLanguageStreams(room)
	assert.equal(streams.some(s => s.language === 'English Captions'), true)
})

test('firstCaptionLanguage returns non-original caption language when available', () => {
	const languages = [
		{ language: 'Original', caption_ws_url: 'wss://example.com/orig' },
		{ language: 'Spanish', caption_ws_url: 'wss://example.com/es' },
	]
	assert.equal(firstCaptionLanguage(languages), 'Spanish')
})

test('isUsableAudioTranslationEntry recognizes WHEP, WHIP, and YouTube endpoints', () => {
	assert.equal(isUsableAudioTranslationEntry({ language: 'Spanish', url: 'https://live.example.com/whep' }), true)
	assert.equal(isUsableAudioTranslationEntry({ language: 'Spanish', url: 'https://live.example.com/whip' }), true)
	assert.equal(isUsableAudioTranslationEntry({ language: 'Spanish', youtube_id: 'dQw4w9WgXcQ' }), true)
	assert.equal(isUsableAudioTranslationEntry({ language: 'Spanish', url: 'invalid-url-string' }), false)
	assert.equal(isUsableAudioTranslationEntry({ language: '', url: 'https://live.example.com/whep' }), false)
})

test('normalizeAudioTranslationSource returns normalized URL or YouTube ID', () => {
	assert.equal(normalizeAudioTranslationSource('https://live.example.com/whep'), 'https://live.example.com/whep')
	assert.equal(normalizeAudioTranslationSource('https://live.example.com/whip'), 'https://live.example.com/whip')
	assert.equal(normalizeAudioTranslationSource('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
	assert.equal(normalizeAudioTranslationSource('dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
	assert.equal(normalizeAudioTranslationSource('not-a-source'), null)
})
