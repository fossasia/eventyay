import assert from 'node:assert/strict'
import test from 'node:test'

import { parseTtsFrame } from './tts-parser.js'

function frame(header, audio = new Uint8Array()) {
	const headerBytes = new TextEncoder().encode(JSON.stringify(header))
	const buffer = new ArrayBuffer(5 + headerBytes.byteLength + audio.byteLength)
	const view = new DataView(buffer)
	view.setUint8(0, 1)
	view.setUint32(1, headerBytes.byteLength, false)
	const bytes = new Uint8Array(buffer)
	bytes.set(headerBytes, 5)
	bytes.set(audio, 5 + headerBytes.byteLength)
	return buffer
}

test('parses the header and audio from a TTS frame', () => {
	const audio = new Uint8Array([1, 2, 3, 4])
	const parsed = parseTtsFrame(frame({ seq: 7, translation: 'Hallo' }, audio))
	assert.deepEqual(parsed.header, { seq: 7, translation: 'Hallo' })
	assert.deepEqual(parsed.audioBytes, audio)
})

test('rejects malformed TTS frames', () => {
	assert.throws(() => parseTtsFrame(new ArrayBuffer(4)), /too short/)
	const unsupported = frame({})
	new DataView(unsupported).setUint8(0, 2)
	assert.throws(() => parseTtsFrame(unsupported), /Unsupported/)
	const truncated = frame({})
	new DataView(truncated).setUint32(1, truncated.byteLength, false)
	assert.throws(() => parseTtsFrame(truncated), /truncated/)
})
