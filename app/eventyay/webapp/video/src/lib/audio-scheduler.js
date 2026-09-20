import { parseTtsFrame, pcm16ToFloat32, TTS_DEFAULT_SAMPLE_RATE } from './tts-parser.js';

// Safety margin when playback re-anchors after the queue ran dry, so small
// network jitter does not immediately cause another gap (same as Voxbento's listener).
const JITTER_BUFFER_SEC = 0.25;
// Same backoff shape as LiveCaptions.vue: 1s, 2s, 4s, ... capped at 10s.
const BASE_RETRY_DELAY_MS = 1000;
const MAX_RETRY_DELAY_MS = 10000;

/**
 * Plays Voxbento AI interpretation audio: owns the TTS WebSocket, decodes
 * each frame and queues it for gapless playback through the Web Audio API.
 */
export class AudioScheduler {
	constructor(wsUrl) {
		this.wsUrl = wsUrl;
		this.ws = null;
		this.audioContext = null;
		this.isConnected = false;
		this.isDisposed = false;
		this.isPaused = false;
		this.retryCount = 0;
		this.maxRetries = 5;
		this.retryDelay = BASE_RETRY_DELAY_MS;
		this.reconnectTimer = null;
		this.nextStartTime = 0;
		this.activeSources = new Set();
		this.volume = 1;
		this.gainNode = null;
	}

	/**
	 * Interpretation volume, shared with the human booth player so both
	 * interpretation sources follow the same slider. Range 0..1.
	 */
	setVolume(volume) {
		const parsed = Number(volume);
		this.volume = Number.isFinite(parsed) ? Math.min(Math.max(parsed, 0), 1) : 1;
		if (this.gainNode) {
			this.gainNode.gain.value = this.volume;
		}
	}

	connect() {
		if (this.isDisposed) return Promise.resolve();
		if (this.isConnected) return Promise.resolve();

		return new Promise((resolve, reject) => {
			let ws;
			try {
				ws = new WebSocket(this.wsUrl);
			} catch (error) {
				reject(error);
				return;
			}
			ws.binaryType = 'arraybuffer';
			this.ws = ws;

			ws.onopen = () => {
				if (this.ws !== ws) return;
				this.isConnected = true;
				this.retryCount = 0;
				resolve();
			};
			ws.onmessage = (event) => {
				if (this.ws !== ws) return;
				this.handleMessage(event.data);
			};
			ws.onerror = (error) => {
				if (this.ws !== ws) return;
				reject(error);
			};
			ws.onclose = () => {
				if (this.ws !== ws) return;
				this.ws = null;
				this.handleClose();
			};
		});
	}

	getRetryDelay(attempt) {
		return Math.min(this.retryDelay * Math.pow(2, attempt), MAX_RETRY_DELAY_MS);
	}

	handleClose() {
		this.isConnected = false;
		if (this.isDisposed) return;
		if (this.retryCount >= this.maxRetries) {
			console.error('TTS interpretation stream: max reconnect attempts reached');
			return;
		}
		const delay = this.getRetryDelay(this.retryCount);
		this.retryCount++;
		this.reconnectTimer = setTimeout(() => {
			this.reconnectTimer = null;
			if (this.isDisposed) return;
			this.connect().catch(error => {
				console.warn('TTS interpretation stream: reconnect failed', error);
			});
		}, delay);
	}

	handleMessage(data) {
		if (this.isDisposed) return;
		if (!(data instanceof ArrayBuffer)) return;

		let frame;
		try {
			frame = parseTtsFrame(data);
		} catch (error) {
			console.warn('TTS interpretation stream: dropping malformed frame', error);
			return;
		}
		if (frame.header?.error || !frame.audioBytes.byteLength) return;
		this.scheduleAudio(frame);
	}

	ensureAudioContext() {
		if (this.audioContext) return this.audioContext;
		const AudioContextClass = window.AudioContext || window.webkitAudioContext;
		this.audioContext = new AudioContextClass();
		this.gainNode = this.audioContext.createGain?.() ?? null;
		if (this.gainNode) {
			this.gainNode.gain.value = this.volume;
			this.gainNode.connect(this.audioContext.destination);
		}
		this.nextStartTime = 0;
		if (this.isPaused) {
			this.audioContext.suspend?.();
		} else if (this.audioContext.state === 'suspended') {
			this.audioContext.resume?.().catch(() => {});
		}
		return this.audioContext;
	}

	scheduleAudio(frame) {
		const samples = pcm16ToFloat32(frame.audioBytes);
		if (!samples.length) return;

		let ctx;
		try {
			ctx = this.ensureAudioContext();
		} catch (error) {
			console.error('TTS interpretation stream: failed to create AudioContext', error);
			return;
		}

		const sampleRate = Number(frame.header?.sample_rate) || TTS_DEFAULT_SAMPLE_RATE;
		const audioBuffer = ctx.createBuffer(1, samples.length, sampleRate);
		audioBuffer.getChannelData(0).set(samples);

		const source = ctx.createBufferSource();
		source.buffer = audioBuffer;
		source.connect(this.gainNode ?? ctx.destination);

		// Queue each segment right after the previous one; if the queue ran dry,
		// re-anchor slightly in the future to absorb jitter.
		const now = ctx.currentTime;
		const startTime = this.nextStartTime > now ? this.nextStartTime : now + JITTER_BUFFER_SEC;
		source.onended = () => this.activeSources.delete(source);
		this.activeSources.add(source);
		source.start(startTime);
		this.nextStartTime = startTime + audioBuffer.duration;
	}

	pause() {
		this.isPaused = true;
		this.audioContext?.suspend?.();
	}

	resume() {
		this.isPaused = false;
		if (this.audioContext?.state === 'suspended') {
			this.audioContext.resume().catch(error => {
				console.warn('TTS interpretation stream: failed to resume audio', error);
			});
		}
	}

	disconnect() {
		this.isDisposed = true;
		this.isConnected = false;

		if (this.reconnectTimer) {
			clearTimeout(this.reconnectTimer);
			this.reconnectTimer = null;
		}

		const ws = this.ws;
		this.ws = null;
		ws?.close();

		// Stop queued segments explicitly so nothing already scheduled keeps playing.
		for (const source of this.activeSources) {
			try {
				source.stop();
			} catch {
				// Already stopped.
			}
		}
		this.activeSources.clear();

		if (this.audioContext) {
			this.audioContext.close?.()?.catch?.(() => {});
			this.audioContext = null;
		}
		this.nextStartTime = 0;
	}
}
