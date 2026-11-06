import assert from 'node:assert/strict'
import test from 'node:test'

import { TtsAudioPlayer } from './tts-audio-player.js'

test('reconnects with backoff and tears down all resources', () => {
	const originalWindow = globalThis.window
	const originalWebSocket = globalThis.WebSocket
	const timers = new Map()
	const sockets = []
	let timerId = 0

	class AudioContext {
		constructor() {
			this.currentTime = 0
			this.destination = {}
			this.state = 'running'
		}

		createGain() {
			return { gain: { setValueAtTime() {} }, connect() {}, disconnect() {} }
		}

		close() {
			this.state = 'closed'
			return Promise.resolve()
		}
	}

	class Socket {
		constructor() {
			this.listeners = {}
			sockets.push(this)
		}

		addEventListener(name, callback) {
			this.listeners[name] = callback
		}

		emit(name, event = {}) {
			this.listeners[name]?.(event)
		}

		close() {
			this.emit('close')
		}
	}

	globalThis.window = {
		AudioContext,
		setTimeout(callback, delay) {
			timerId += 1
			timers.set(timerId, { callback, delay })
			return timerId
		},
		clearTimeout(id) {
			timers.delete(id)
		},
	}
	globalThis.WebSocket = Socket

	try {
		const player = new TtsAudioPlayer('wss://example.test/tts')
		player.connect()
		assert.equal(sockets.length, 1)
		sockets[0].emit('close')
		assert.equal([...timers.values()][0].delay, 1000)
		const reconnect = [...timers.values()][0]
		timers.clear()
		reconnect.callback()
		assert.equal(sockets.length, 2)
		sockets[1].emit('close')
		assert.equal([...timers.values()][0].delay, 2000)
		player.disconnect()
		assert.equal(timers.size, 0)
		assert.equal(player.audioContext, null)
		assert.equal(player.scheduler, null)
	} finally {
		globalThis.window = originalWindow
		globalThis.WebSocket = originalWebSocket
	}
})
