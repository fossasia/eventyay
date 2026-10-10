/**
 * Voxbento TTS frame parsing and AudioScheduler playback/teardown behaviour.
 * Run: node --test src/lib/audio-scheduler.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { AudioScheduler } from './audio-scheduler.js'
import { parseTtsFrame, pcm16ToFloat32 } from './tts-parser.js'

// Mirrors Voxbento's server: struct.pack('>BI', 1, len(header)) + header + audio
function encodeFrame(header, samples = [1000, -1000]) {
	const headerBytes = new TextEncoder().encode(JSON.stringify(header))
	const audio = new Uint8Array(samples.length * 2)
	const audioView = new DataView(audio.buffer)
	samples.forEach((sample, i) => audioView.setInt16(i * 2, sample, true))
	const frame = new Uint8Array(5 + headerBytes.length + audio.length)
	frame[0] = 1
	new DataView(frame.buffer).setUint32(1, headerBytes.length, false)
	frame.set(headerBytes, 5)
	frame.set(audio, 5 + headerBytes.length)
	return frame.buffer
}

let audioContextsCreated = 0
let startedSources = []
let stoppedSources = 0
let createdGainNodes = []

class FakeAudioContext {
	constructor() {
		audioContextsCreated++
		this.sampleRate = 48000
		this.currentTime = 0
		this.state = 'running'
		this.destination = {}
	}

	createBuffer(channels, length, sampleRate) {
		const channelData = new Float32Array(length)
		return {
			sampleRate,
			duration: length / sampleRate,
			getChannelData: () => channelData
		}
	}

	createGain() {
		const node = {
			gain: { value: 1 },
			connect(target) {
				node.connectedTo = target
			}
		}
		createdGainNodes.push(node)
		return node
	}

	createBufferSource() {
		const source = {
			buffer: null,
			connect(target) {
				source.connectedTo = target
			},
			start(when) {
				startedSources.push({ when, buffer: source.buffer, connectedTo: source.connectedTo })
			},
			stop() {
				stoppedSources++
			}
		}
		return source
	}

	close() {
		this.state = 'closed'
		return Promise.resolve()
	}

	suspend() {
		this.state = 'suspended'
		return Promise.resolve()
	}

	resume() {
		this.state = 'running'
		return Promise.resolve()
	}
}

// The scheduler runs against browser globals, so stand them up for the duration
// of a test and put whatever was there back afterwards.
async function withBrowserStubs(run) {
	const sockets = []
	const originalWebSocket = globalThis.WebSocket
	const originalWindow = globalThis.window
	const originalConsole = { log: console.log, warn: console.warn, error: console.error }

	globalThis.WebSocket = class {
		constructor(url) {
			this.url = url
			sockets.push(this)
		}

		close() {
			if (this.onclose) this.onclose()
		}
	}
	globalThis.window = { AudioContext: FakeAudioContext }
	console.log = () => {}
	console.warn = () => {}
	console.error = () => {}
	audioContextsCreated = 0
	startedSources = []
	stoppedSources = 0
	createdGainNodes = []

	try {
		await run(sockets)
	} finally {
		globalThis.WebSocket = originalWebSocket
		if (originalWindow === undefined) {
			delete globalThis.window
		} else {
			globalThis.window = originalWindow
		}
		Object.assign(console, originalConsole)
	}
}

async function connectedScheduler(sockets) {
	const scheduler = new AudioScheduler('wss://voxbento.invalid/ws/tts/1/de/booth')
	const connecting = scheduler.connect()
	sockets[0].onopen()
	await connecting
	return scheduler
}

test('parses a frame whose length field is the JSON header length', () => {
	const { header, audioBytes } = parseTtsFrame(encodeFrame({ seq: 7, caption: 'Hallo' }, [1, 2, 3]))
	assert.deepEqual(header, { seq: 7, caption: 'Hallo' })
	assert.equal(audioBytes.byteLength, 6, 'every byte after the header is audio')
})

test('rejects frames with an unknown version or a truncated header', () => {
	const badVersion = new Uint8Array(encodeFrame({ seq: 1 }))
	badVersion[0] = 2
	assert.throws(() => parseTtsFrame(badVersion.buffer), /version/)

	const truncated = encodeFrame({ seq: 1 }, []).slice(0, 8)
	assert.throws(() => parseTtsFrame(truncated), /truncated/)
	assert.throws(() => parseTtsFrame(new ArrayBuffer(3)), /too short/)
})

test('decodes 16-bit little-endian PCM into float samples', () => {
	const bytes = new Uint8Array(encodeFrame({}, [0, 16384, -32768, 32767])).slice(7)
	const samples = pcm16ToFloat32(bytes)
	assert.deepEqual(Array.from(samples), [0, 0.5, -1, 32767 / 32768])
	assert.equal(pcm16ToFloat32(new Uint8Array([1, 2, 3])).length, 1, 'a dangling odd byte is ignored')
})

test('plays frames at 24 kHz, queued back to back without overlap', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onmessage({ data: encodeFrame({ seq: 1 }, new Array(2400).fill(100)) })
		sockets[0].onmessage({ data: encodeFrame({ seq: 2 }, new Array(4800).fill(100)) })

		assert.equal(audioContextsCreated, 1)
		assert.equal(startedSources.length, 2)
		assert.equal(startedSources[0].buffer.sampleRate, 24000)
		assert.equal(startedSources[0].when, 0.25, 'first segment starts after the jitter buffer')
		assert.equal(startedSources[1].when, 0.35, 'second segment starts when the first (0.1s) ends')
		scheduler.disconnect()
	})
})

test('plays through a gain node so the interpretation volume slider applies', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)
		scheduler.setVolume(0.4)

		sockets[0].onmessage({ data: encodeFrame({ seq: 1 }, new Array(2400).fill(100)) })

		assert.equal(createdGainNodes.length, 1)
		assert.equal(createdGainNodes[0].gain.value, 0.4, 'volume set before playback is applied')
		assert.equal(startedSources[0].connectedTo, createdGainNodes[0], 'audio is routed through the gain node')

		scheduler.setVolume(0.9)
		assert.equal(createdGainNodes[0].gain.value, 0.9, 'later changes reach the live gain node')
		scheduler.setVolume(5)
		assert.equal(createdGainNodes[0].gain.value, 1, 'out-of-range values are clamped')
		scheduler.disconnect()
	})
})

test('ignores error frames, empty audio and malformed messages', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onmessage({ data: encodeFrame({ seq: 1, error: 'tts failed' }) })
		sockets[0].onmessage({ data: encodeFrame({ seq: 2 }, []) })
		sockets[0].onmessage({ data: new ArrayBuffer(2) })
		sockets[0].onmessage({ data: 'not binary' })

		assert.equal(startedSources.length, 0)
		scheduler.disconnect()
	})
})

test('disconnect stops queued audio and drops messages that arrive afterwards', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)
		const socket = sockets[0]

		socket.onmessage({ data: encodeFrame({ seq: 1 }) })
		assert.equal(startedSources.length, 1)

		scheduler.disconnect()
		assert.equal(stoppedSources, 1, 'already-scheduled audio is stopped')

		// close() does not detach the handler, so a frame already in flight when the
		// listener switched languages still gets delivered to this callback.
		socket.onmessage({ data: encodeFrame({ seq: 2 }) })

		assert.equal(audioContextsCreated, 1, 'no AudioContext is recreated after teardown')
		assert.equal(startedSources.length, 1, 'no audio is scheduled after teardown')
		assert.equal(scheduler.audioContext, null, 'teardown leaves no audio context behind')
		assert.equal(sockets.length, 1, 'no replacement socket is opened')
	})
})

test('pausing before the first frame keeps the new AudioContext suspended', async () => {
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)
		scheduler.pause()
		sockets[0].onmessage({ data: encodeFrame({ seq: 1 }) })
		assert.equal(scheduler.audioContext.state, 'suspended')
		scheduler.resume()
		assert.equal(scheduler.audioContext.state, 'running')
		scheduler.disconnect()
	})
})

test('retries a dropped connection on an exponential backoff capped at 10s', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)
		scheduler.maxRetries = 10

		sockets[0].onclose()
		assert.equal(sockets.length, 1, 'the retry is deferred rather than immediate')
		t.mock.timers.tick(999)
		assert.equal(sockets.length, 1, 'nothing reconnects before the first delay elapses')
		t.mock.timers.tick(1)
		assert.equal(sockets.length, 2, 'the first retry reconnects after 1s')

		sockets[1].onclose()
		t.mock.timers.tick(1999)
		assert.equal(sockets.length, 2, 'the second delay is longer than the first')
		t.mock.timers.tick(1)
		assert.equal(sockets.length, 3, 'the second retry reconnects after 2s')

		assert.equal(scheduler.getRetryDelay(8), 10000, 'the delay never exceeds 10s')
		scheduler.disconnect()
	})
})

test('gives up once the retry limit is reached', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		for (let attempt = 0; attempt < scheduler.maxRetries; attempt++) {
			sockets[sockets.length - 1].onclose()
			t.mock.timers.tick(scheduler.getRetryDelay(attempt))
		}
		assert.equal(sockets.length, scheduler.maxRetries + 1, 'the original socket plus one per retry')

		sockets[sockets.length - 1].onclose()
		t.mock.timers.tick(60000)
		assert.equal(sockets.length, scheduler.maxRetries + 1, 'no further sockets once the limit is reached')

		scheduler.disconnect()
	})
})

test('a successful reconnect resets the backoff', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onclose()
		t.mock.timers.tick(scheduler.retryDelay)
		assert.equal(sockets.length, 2)
		sockets[1].onopen()
		assert.equal(scheduler.retryCount, 0, 'reconnecting clears the accumulated backoff')

		sockets[1].onclose()
		t.mock.timers.tick(scheduler.retryDelay)
		assert.equal(sockets.length, 3, 'the next drop retries at the base delay again')

		scheduler.disconnect()
	})
})

test('a failed first connect still retries until disconnected', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = new AudioScheduler('wss://voxbento.invalid/ws/tts/1/de/booth')
		const connecting = scheduler.connect()
		sockets[0].onerror(new Error('refused'))
		sockets[0].onclose()
		await assert.rejects(connecting)

		t.mock.timers.tick(scheduler.retryDelay)
		assert.equal(sockets.length, 2, 'the scheduler keeps trying after the first failure')

		scheduler.disconnect()
		sockets[1].onclose()
		t.mock.timers.tick(60000)
		assert.equal(sockets.length, 2, 'nothing reconnects after teardown')
	})
})

test('disconnect cancels a retry that is already pending', async (t) => {
	t.mock.timers.enable({ apis: ['setTimeout'] })
	await withBrowserStubs(async (sockets) => {
		const scheduler = await connectedScheduler(sockets)

		sockets[0].onclose()
		assert.notEqual(scheduler.reconnectTimer, null, 'a retry is pending')

		scheduler.disconnect()
		assert.equal(scheduler.reconnectTimer, null, 'the pending retry is cleared')

		t.mock.timers.tick(60000)
		assert.equal(sockets.length, 1, 'the cancelled retry never opens a socket')
	})
})
