export class AudioScheduler {
	constructor(audioContext, { jitterBufferSeconds = 0.25, sampleRate = 24000 } = {}) {
		this.audioContext = audioContext
		this.jitterBufferSeconds = jitterBufferSeconds
		this.sampleRate = sampleRate
		this.nextStartTime = 0
		this.sources = new Set()
		this.gain = audioContext.createGain()
		this.gain.connect(audioContext.destination)
	}

	setVolume(volume) {
		const safeVolume = Math.min(1, Math.max(0, Number(volume) || 0))
		this.gain.gain.setValueAtTime(safeVolume, this.audioContext.currentTime)
	}

	schedule(audioBytes) {
		if (!audioBytes?.byteLength) return null
		if (audioBytes.byteLength % 2 !== 0) {
			console.warn('Ignoring malformed TTS PCM chunk', {
				byteLength: audioBytes.byteLength,
				sampleRate: this.sampleRate,
			})
			return null
		}

		const view = new DataView(audioBytes.buffer, audioBytes.byteOffset, audioBytes.byteLength)
		const samples = new Float32Array(audioBytes.byteLength / 2)
		for (let index = 0; index < samples.length; index += 1) {
			samples[index] = view.getInt16(index * 2, true) / 32768
		}

		const buffer = this.audioContext.createBuffer(1, samples.length, this.sampleRate)
		buffer.copyToChannel(samples, 0)
		const source = this.audioContext.createBufferSource()
		source.buffer = buffer
		source.connect(this.gain)
		const now = this.audioContext.currentTime
		const startTime = this.nextStartTime > now
			? this.nextStartTime
			: now + this.jitterBufferSeconds
		this.nextStartTime = startTime + buffer.duration
		this.sources.add(source)
		source.addEventListener('ended', () => this.sources.delete(source), { once: true })
		source.start(startTime)
		return { startTime, endTime: this.nextStartTime }
	}

	reset() {
		for (const source of this.sources) {
			try {
				source.stop()
			} catch (error) {
				if (error.name !== 'InvalidStateError') throw error
			}
		}
		this.sources.clear()
		this.nextStartTime = 0
	}

	destroy() {
		this.reset()
		this.gain.disconnect()
	}
}
