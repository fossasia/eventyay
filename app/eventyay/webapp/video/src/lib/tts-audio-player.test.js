import assert from 'node:assert/strict'
import test from 'node:test'

import { TtsAudioPlayer } from './tts-audio-player.js'

function withEnvironment(callback) {
	const originalWindow = globalThis.window
	const originalWebSocket = globalThis.WebSocket
	const timers = new Map()
	const sockets = []
	const contexts = []
	let timerId = 0
	let throwOnSocket = false

	class AudioContext {
		constructor() {
			this.currentTime = 0
			this.destination = {}
			this.state = 'running'
			this.volume = 1
			contexts.push(this)
		}

		createGain() {
			return {
				gain: {
					setValueAtTime: value => { this.volume = value },
				},
				connect() {},
				disconnect() {},
			}
		}

		suspend() {
			this.state = 'suspended'
			return Promise.resolve()
		}

		resume() {
			this.state = 'running'
			return Promise.resolve()
		}

		close() {
			this.state = 'closed'
			return Promise.resolve()
		}
	}

	class Socket {
		constructor() {
			if (throwOnSocket) throw new Error('Invalid WebSocket URL')
			this.listeners = {}
			sockets.push(this)
		}

		addEventListener(name, callback) {
			this.listeners[name] ||= []
			this.listeners[name].push(callback)
		}

		emit(name, event = {}) {
			for (const callback of this.listeners[name] || []) callback(event)
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
		callback({
			contexts,
			sockets,
			timers,
			nextTimer() {
				const [id, timer] = timers.entries().next().value
				timers.delete(id)
				return timer
			},
			setThrowOnSocket(value) {
				throwOnSocket = value
			},
		})
	} finally {
		globalThis.window = originalWindow
		globalThis.WebSocket = originalWebSocket
	}
}

test('reconnects with backoff, resets attempts, and stops at the limit', () => {
	withEnvironment(({ sockets, timers, nextTimer }) => {
		const player = new TtsAudioPlayer('wss://example.test/tts', { maxReconnectAttempts: 2 })
		player.connect()
		player.reconnectAttempts = 1
		sockets[0].emit('open')
		assert.equal(player.reconnectAttempts, 0)
		sockets[0].emit('close')
		assert.equal(nextTimer().delay, 1000)
		player.openSocket()
		sockets[1].emit('close')
		assert.equal(nextTimer().delay, 2000)
		player.openSocket()
		sockets[2].emit('close')
		assert.equal(timers.size, 0)
		player.disconnect()
		assert.equal(player.audioContext, null)
		assert.equal(player.scheduler, null)
	})
})

test('clamps volume and pauses and resumes its audio context', () => {
	withEnvironment(({ contexts }) => {
		const player = new TtsAudioPlayer('wss://example.test/tts')
		player.connect()
		player.setVolume(4)
		assert.equal(player.volume, 1)
		assert.equal(contexts[0].volume, 1)
		player.setVolume(-1)
		assert.equal(player.volume, 0)
		assert.equal(contexts[0].volume, 0)
		player.pause()
		assert.equal(contexts[0].state, 'suspended')
		player.resume()
		assert.equal(contexts[0].state, 'running')
		player.disconnect()
	})
})

test('ignores stale socket events after disconnect', () => {
	withEnvironment(({ sockets, timers }) => {
		const errors = []
		const player = new TtsAudioPlayer('wss://example.test/tts', { onError: error => errors.push(error) })
		player.connect()
		const staleSocket = sockets[0]
		player.disconnect()
		staleSocket.emit('message', { data: new ArrayBuffer(8) })
		staleSocket.emit('close')
		assert.equal(errors.length, 0)
		assert.equal(timers.size, 0)
	})
})

test('cleans up when opening the WebSocket fails', () => {
	withEnvironment(({ contexts, setThrowOnSocket }) => {
		setThrowOnSocket(true)
		const player = new TtsAudioPlayer('invalid')
		assert.throws(() => player.connect(), /Invalid WebSocket URL/)
		assert.equal(contexts[0].state, 'closed')
		assert.equal(player.stopped, true)
		assert.equal(player.audioContext, null)
		assert.equal(player.scheduler, null)
	})
})
