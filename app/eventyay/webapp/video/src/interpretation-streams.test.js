import test from 'node:test'
import assert from 'node:assert/strict'
import {
	roomUsesPluginLanguageStreams,
	pluginLanguageStreams,
	firstCaptionLanguage,
	isUsableLanguageStreamEntry,
} from './interpretation-streams.js'
import {
	isUsableAudioTranslationEntry,
	normalizeAudioTranslationSource,
} from './lib/validators.js'
import { normalizeWhepEndpoint } from './lib/webrtc/whep.js'

test('roomUsesPluginLanguageStreams returns true when room has interpretation_use_plugin_streams', () => {
	assert.equal(roomUsesPluginLanguageStreams({ interpretation_use_plugin_streams: true }), true)
})

test('roomUsesPluginLanguageStreams honors disabled room flag when active stream schedule defines language_streams', () => {
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
	assert.equal(roomUsesPluginLanguageStreams(room), false)
	assert.deepEqual(pluginLanguageStreams(room), [])
})

test('roomUsesPluginLanguageStreams honors disabled room flag when active stream schedule defines legacy languageUrls', () => {
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
	assert.equal(roomUsesPluginLanguageStreams(room), false)
	assert.deepEqual(pluginLanguageStreams(room), [])
})

test('roomUsesPluginLanguageStreams returns false when schedule only has empty/incomplete entries and room flag is off', () => {
	const room = {
		interpretation_use_plugin_streams: false,
		currentStream: {
			config: {
				language_streams: [
					{ language: '', url: '' },
					{ language: 'Incomplete', url: 'not-a-valid-url' },
				],
			},
		},
	}
	assert.equal(roomUsesPluginLanguageStreams(room), false)
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

test('pluginLanguageStreams falls back to room interpretation_language_streams when schedule has empty channels', () => {
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

test('pluginLanguageStreams falls back to room interpretation_language_streams when schedule only has unusable rows', () => {
	const room = {
		interpretation_use_plugin_streams: true,
		interpretation_language_streams: [
			{ language: 'RoomGerman', url: 'https://example.com/room-de/whep' },
		],
		currentStream: {
			config: {
				language_streams: [
					{ language: '', url: '' },
					{ language: 'BadUrl', url: 'not-valid' },
				],
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

test('isUsableLanguageStreamEntry validates languages with audio or caption endpoints', () => {
	assert.equal(isUsableLanguageStreamEntry({ language: 'Spanish', url: 'https://live.example.com/whep' }), true)
	assert.equal(isUsableLanguageStreamEntry({ language: 'Original', caption_ws_url: 'wss://live.example.com/ws' }), true)
	assert.equal(isUsableLanguageStreamEntry({ language: '', url: 'https://live.example.com/whep' }), false)
	assert.equal(isUsableLanguageStreamEntry({ language: 'Spanish', url: 'invalid' }), false)
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

test('normalizeWhepEndpoint rewrites /whip endpoints to /whep while preserving query strings and trailing slashes', () => {
	assert.equal(normalizeWhepEndpoint('https://live.example.com/whip'), 'https://live.example.com/whep')
	assert.equal(normalizeWhepEndpoint('https://live.example.com/whip/'), 'https://live.example.com/whep')
	assert.equal(normalizeWhepEndpoint('https://live.example.com/whip?token=secret123'), 'https://live.example.com/whep?token=secret123')
	assert.equal(normalizeWhepEndpoint('https://live.example.com/whip/?token=secret123'), 'https://live.example.com/whep?token=secret123')
	assert.equal(normalizeWhepEndpoint('https://live.example.com/channel/whip?flow=wispr'), 'https://live.example.com/channel/whep?flow=wispr')
	assert.equal(normalizeWhepEndpoint('https://live.example.com/channel/whep?flow=wispr'), 'https://live.example.com/channel/whep?flow=wispr')
	assert.equal(normalizeWhepEndpoint('/relative/whip?token=123'), '/relative/whep?token=123')
})

for (const field of ['language_streams', 'languageUrls']) {
	test(`pluginLanguageStreams resolves enabled schedule config.${field}`, () => {
		const channel = { language: 'German', url: 'https://example.com/de/whep' }
		const streams = pluginLanguageStreams({
			interpretation_use_plugin_streams: true,
			currentStream: { config: { [field]: [channel] } },
		})
		assert.deepEqual(streams.slice(1), [channel])
	})
}

test('pluginLanguageStreams preserves room caption sockets for schedule audio and injected Original', () => {
	const audio = { language: 'German', url: 'https://example.com/slot/de/whep' }
	const room = {
		interpretation_use_plugin_streams: true,
		interpretation_language_streams: [
			{ language: 'Original', caption_ws_url: 'wss://example.com/floor' },
			{ language: 'German', url: 'https://example.com/room/de/whep', caption_ws_url: 'wss://example.com/de' },
			{ language: 'French', url: 'https://example.com/room/fr/whep' },
		],
		currentStream: { config: { language_streams: [audio] } },
	}
	const before = structuredClone(room)
	const streams = pluginLanguageStreams(room)
	assert.equal(streams.length, 2)
	assert.equal(streams[0].language, 'Original')
	assert.equal(streams[0].caption_ws_url, 'wss://example.com/floor')
	assert.deepEqual(streams[1], { ...audio, caption_ws_url: 'wss://example.com/de' })
	assert.deepEqual(room, before)
})

test('pluginLanguageStreams inherits captions on explicit Original and keeps schedule caption overrides', () => {
	const streams = pluginLanguageStreams({
		interpretation_use_plugin_streams: true,
		interpretation_language_streams: [
			{ language: 'Original', caption_ws_url: 'wss://example.com/floor' },
			{ language: 'German', caption_ws_url: 'wss://example.com/room/de' },
		],
		currentStream: { config: { language_streams: [
			{ language: 'Original' },
			{ language: 'German', url: 'https://example.com/de/whep', caption_ws_url: 'wss://example.com/slot/de' },
		] } },
	})
	assert.equal(streams.length, 2)
	assert.equal(streams[0].caption_ws_url, 'wss://example.com/floor')
	assert.equal(streams[1].caption_ws_url, 'wss://example.com/slot/de')
})

test('normalizeWhepEndpoint rewrites a WHIP path segment before a stream ID', () => {
	assert.equal(normalizeWhepEndpoint('https://live.example.com/whip/stream-id'), 'https://live.example.com/whep/stream-id')
	assert.equal(normalizeWhepEndpoint('https://live.example.com/whip/stream-id/?token=123#track'), 'https://live.example.com/whep/stream-id/?token=123#track')
	assert.equal(normalizeWhepEndpoint('/whip/stream-id?token=123'), '/whep/stream-id?token=123')
})

test('normalizeWhepEndpoint leaves query values and non-WHIP path segments unchanged', () => {
	for (const url of [
		'https://live.example.com/whipping/stream-id',
		'https://live.example.com/whep/stream-id?next=/whip/other',
		'/whep/stream-id?next=/whip/other',
		'/whep/?token=123',
		'', null, undefined,
	]) {
		assert.equal(normalizeWhepEndpoint(url), url)
	}
})
