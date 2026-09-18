/**
 * Language stream list for plugin-driven interpretation rooms.
 * Run: node --test src/interpretation-streams.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { interpretationStreamType, pluginLanguageStreams } from './interpretation-streams.js'

const WHEP = 'https://voxbento.example/demo-12-es/whep'
const TTS = 'wss://voxbento.example/ws/tts/12/de/demo-12-floor'

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
		{ language: 'Spanish', stream_type: 'ai', tts_ws_url: TTS.replace('/de/', '/es/') },
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
