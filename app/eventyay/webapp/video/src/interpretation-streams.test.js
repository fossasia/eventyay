import assert from 'node:assert/strict'
import test from 'node:test'

import { interpretationAudioSource, interpretationStreamIdentity } from './interpretation-streams.js'

test('uses the first valid interpretation source', () => {
	const stream = {
		language: 'Spanish',
		tts_ws_url: 'invalid',
		whep_url: 'https://example.test/whep/spanish',
	}
	assert.equal(interpretationAudioSource(stream), stream.whep_url)
})

test('keeps Human and AI streams for one language distinct', () => {
	const human = {
		language: 'Spanish',
		whep_url: 'https://example.test/whep/spanish',
	}
	const ai = {
		language: 'Spanish',
		tts_ws_url: 'wss://example.test/tts/spanish',
	}
	assert.notEqual(interpretationStreamIdentity(human), interpretationStreamIdentity(ai))
})
