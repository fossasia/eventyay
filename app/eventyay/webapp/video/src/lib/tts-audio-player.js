import { AudioScheduler } from './audio-scheduler.js'
import { parseTtsFrame } from './tts-parser.js'

export class TtsAudioPlayer {
	constructor(url, {
		maxReconnectAttempts = 5,
		onError = error => console.error('TTS interpretation audio failed', error),
	} = {}) {
		this.url = url
		this.maxReconnectAttempts = maxReconnectAttempts
		this.onError = onError
		this.socket = null
		this.audioContext = null
		this.scheduler = null
		this.reconnectAttempts = 0
		this.reconnectTimer = null
		this.stopped = true
		this.volume = 1
	}

	connect() {
		this.stopped = false
		try {
			this.ensureAudioContext()
			this.openSocket()
		} catch (error) {
			this.disconnect()
			throw error
		}
	}

	ensureAudioContext() {
		if (this.audioContext) return
		const AudioContextClass = window.AudioContext || window.webkitAudioContext
		if (!AudioContextClass) throw new Error('Web Audio API is unavailable')
		this.audioContext = new AudioContextClass()
		this.scheduler = new AudioScheduler(this.audioContext)
		this.scheduler.setVolume(this.volume)
	}

	openSocket() {
		if (this.stopped) return
		const socket = new WebSocket(this.url)
		this.socket = socket
		socket.binaryType = 'arraybuffer'
		socket.addEventListener('open', () => {
			if (this.socket === socket) this.reconnectAttempts = 0
		})
		socket.addEventListener('message', event => {
			if (this.socket !== socket || !(event.data instanceof ArrayBuffer)) return
			try {
				const frame = parseTtsFrame(event.data)
				if (!frame.header.error) this.scheduler?.schedule(frame.audioBytes)
			} catch (error) {
				this.onError(error)
			}
		})
		socket.addEventListener('error', event => this.onError(event))
		socket.addEventListener('close', () => {
			if (this.socket !== socket) return
			this.socket = null
			this.scheduleReconnect()
		})
	}

	scheduleReconnect() {
		if (this.stopped || this.reconnectAttempts >= this.maxReconnectAttempts) return
		const delay = Math.min(1000 * (2 ** this.reconnectAttempts), 10000)
		this.reconnectAttempts += 1
		this.reconnectTimer = window.setTimeout(() => {
			this.reconnectTimer = null
			this.openSocket()
		}, delay)
	}

	setVolume(volume) {
		this.volume = Math.min(1, Math.max(0, Number(volume) || 0))
		this.scheduler?.setVolume(this.volume)
	}

	pause() {
		if (this.audioContext?.state === 'running') {
			this.audioContext.suspend().catch(this.onError)
		}
	}

	resume() {
		if (this.audioContext?.state === 'suspended') {
			this.audioContext.resume().catch(this.onError)
		}
	}

	disconnect() {
		this.stopped = true
		if (this.reconnectTimer !== null) {
			window.clearTimeout(this.reconnectTimer)
			this.reconnectTimer = null
		}
		if (this.socket) {
			const socket = this.socket
			this.socket = null
			socket.close()
		}
		this.scheduler?.destroy()
		this.scheduler = null
		if (this.audioContext && this.audioContext.state !== 'closed') {
			this.audioContext.close().catch(this.onError)
		}
		this.audioContext = null
	}
}
