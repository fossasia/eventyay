import assert from 'node:assert/strict'
import test from 'node:test'

import { AudioScheduler } from './audio-scheduler.js'

function audioContext() {
	const sources = []
	const gain = {
		gain: {
			value: 1,
			setValueAtTime(value) {
				this.value = value
			},
		},
		connect() {},
		disconnect() {},
	}
	return {
		currentTime: 2,
		destination: {},
		sources,
		gain,
		createGain: () => gain,
		createBuffer(_channels, length, sampleRate) {
			return { duration: length / sampleRate, copyToChannel() {} }
		},
		createBufferSource() {
			const source = {
				connect() {},
				addEventListener() {},
				start(time) { this.startTime = time },
				stop() { this.stopped = true },
			}
			sources.push(source)
			return source
		},
	}
}

test('schedules PCM chunks without a gap and resets active sources', () => {
	const context = audioContext()
	const scheduler = new AudioScheduler(context)
	const first = scheduler.schedule(new Uint8Array(48000))
	const second = scheduler.schedule(new Uint8Array(24000))
	assert.equal(first.startTime, 2.25)
	assert.equal(first.endTime, 3.25)
	assert.equal(second.startTime, 3.25)
	assert.equal(second.endTime, 3.75)
	scheduler.reset()
	assert.equal(context.sources.every(source => source.stopped), true)
})

test('clamps interpretation volume', () => {
	const context = audioContext()
	const scheduler = new AudioScheduler(context)
	scheduler.setVolume(4)
	assert.equal(context.gain.gain.value, 1)
	scheduler.setVolume(-1)
	assert.equal(context.gain.gain.value, 0)
})

test('reports malformed PCM chunks', () => {
	const context = audioContext()
	const scheduler = new AudioScheduler(context)
	const originalWarn = console.warn
	const warnings = []
	console.warn = (...args) => warnings.push(args)
	try {
		assert.equal(scheduler.schedule(new Uint8Array(3)), null)
		assert.equal(warnings.length, 1)
		assert.deepEqual(warnings[0][1], { byteLength: 3, sampleRate: 24000 })
	} finally {
		console.warn = originalWarn
	}
})
