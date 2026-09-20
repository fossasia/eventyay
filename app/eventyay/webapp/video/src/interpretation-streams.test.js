/**
 * Language stream list for plugin-driven interpretation rooms.
 * Run: node --test src/interpretation-streams.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretationStreamType, pluginLanguageStreams, withListenerToken } from './interpretation-streams.js'

const WHEP = 'https://voxbento.example/demo-12-es/whep'
const TTS = 'wss://voxbento.example/ws/tts/demo-12-ai-de'

function room(streams) {
	return { interpretation_use_plugin_streams: true, interpretation_language_streams: streams }
}

test('classifies AI, human and YouTube entries', () => {
	assert.equal(interpretationStreamType({ language: 'German', tts_ws_url: TTS }), 'ai')
	assert.equal(interpretationStreamType({ language: 'German', stream_type: 'ai', tts_ws_url: TTS }), 'ai')
	assert.equal(interpretationStreamType({ language: 'Spanish', whep_url: WHEP }), 'human')
	// Shape the interpretation plugin actually sends: the WHEP URL lives in youtube_id.
	assert.equal(interpretationStreamType({ language: 'Spanish', youtube_id: WHEP }), 'human')
	assert.equal(interpretationStreamType({ language: 'French', youtube_id: 'dQw4w9WgXcQ' }), null)
	assert.equal(interpretationStreamType({ language: 'French', youtube_id: 'https://youtu.be/dQw4w9WgXcQ' }), null)
	assert.equal(interpretationStreamType({ language: 'Original' }), null)
	assert.equal(interpretationStreamType(null), null)
})

test('offers each language once and keeps the human booth', () => {
	const languages = pluginLanguageStreams(room([
		{ language: 'Spanish', stream_type: 'ai', tts_ws_url: TTS.replace('-ai-de', '-ai-es') },
		{ language: 'Spanish', youtube_id: WHEP },
		{ language: 'German', stream_type: 'ai', tts_ws_url: TTS },
	]))

	assert.deepEqual(languages.map(entry => entry.language), ['Original', 'Spanish', 'German'])
	assert.equal(languages[1].youtube_id, WHEP)
	assert.equal(languages[2].tts_ws_url, TTS)
})

test('keeps the first entry when neither duplicate is a human booth', () => {
	const languages = pluginLanguageStreams(room([
		{ language: 'German', tts_ws_url: TTS },
		{ language: 'German', tts_ws_url: `${TTS}-2` },
	]))

	assert.equal(languages.length, 2)
	assert.equal(languages[1].tts_ws_url, TTS)
})

test('drops entries without a playable source and ignores non-plugin rooms', () => {
	const languages = pluginLanguageStreams(room([
		{ language: 'Italian', youtube_id: '' },
		{ language: 'German', tts_ws_url: TTS },
	]))
	assert.deepEqual(languages.map(entry => entry.language), ['Original', 'German'])
	assert.deepEqual(pluginLanguageStreams({ interpretation_language_streams: [{ language: 'German', tts_ws_url: TTS }] }), [])
})

test('matches duplicates by language code, not spelling', () => {
	const languages = pluginLanguageStreams(room([
		{ language: 'German', language_code: 'de', stream_type: 'ai', tts_ws_url: TTS },
		{ language: 'german ', language_code: 'de', youtube_id: WHEP },
	]))

	assert.equal(languages.length, 2)
	assert.equal(languages[1].youtube_id, WHEP)
})

test('adds the listener token to WebSocket URLs', () => {
	assert.equal(withListenerToken(TTS, 'a.b.c'), `${TTS}?token=a.b.c`)
	assert.equal(withListenerToken(`${TTS}?x=1`, 'a b'), `${TTS}?x=1&token=a%20b`)
	assert.equal(withListenerToken(TTS, null), TTS)
	assert.equal(withListenerToken(null, 'a.b.c'), null)
})

test('keeps caption-only rows but never lets one hide a stream with audio', () => {
	const captionsOnly = pluginLanguageStreams(room([
		{ language: 'Spanish', language_code: 'es', caption_ws_url: 'ws://voxbento.test/ws/captions/es' },
	]))
	assert.deepEqual(captionsOnly.map(entry => entry.language), ['Original', 'Spanish'])

	const mixed = pluginLanguageStreams(room([
		{ language: 'German', language_code: 'de', caption_ws_url: 'ws://voxbento.test/ws/captions/de' },
		{ language: 'German', language_code: 'de', stream_type: 'ai', tts_ws_url: TTS },
	]))
	assert.equal(mixed.length, 2)
	assert.equal(mixed[1].tts_ws_url, TTS, 'the AI voice wins over the caption-only row')
})
