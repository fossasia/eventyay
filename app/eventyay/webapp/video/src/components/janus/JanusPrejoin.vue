<template lang="pug">
.c-janus-prejoin
	.prejoin-layout
		.preview-panel
			.video-preview-wrap
				video.preview-video(ref="previewVideo", autoplay, playsinline, muted)
				.preview-avatar(v-if="showCameraPlaceholder")
					.mdi.mdi-account-circle
					span {{ displayName }}
				.preview-overlay
					.preview-status-label(v-if="showCameraPlaceholder")
						.mdi(:class="cameraOn ? 'mdi-video-off-outline' : 'mdi-video-off'")
						span {{ cameraPlaceholderText }}
			.preview-controls
				button.preview-btn(type="button", :class="{ off: !micOn }", :aria-pressed="micOn ? 'true' : 'false'", :title="micOn ? 'Mute microphone' : 'Unmute microphone'", @click="toggleMic", :id="'prejoin-mic-btn'")
					.mdi(:class="micOn ? 'mdi-microphone' : 'mdi-microphone-off'")
					.audio-indicator(v-if="micOn")
						.audio-bar(v-for="i in 5", :key="i", :class="{ active: audioLevel * 5 >= i }")
				button.preview-btn(type="button", :class="{ off: !cameraOn }", :aria-pressed="cameraOn ? 'true' : 'false'", :title="cameraOn ? 'Turn off camera' : 'Turn on camera'", @click="toggleCamera", :id="'prejoin-cam-btn'")
					.mdi(:class="cameraOn ? 'mdi-video' : 'mdi-video-off'")
				button.preview-btn.settings-btn(type="button", :aria-expanded="showSettings ? 'true' : 'false'", :title="'Device settings'", @click="showSettings = !showSettings", :id="'prejoin-settings-btn'")
					.mdi.mdi-cog

		.join-panel
			.room-info
				h2.room-name {{ roomName }}
				p.room-label Ready to join?

			.device-settings(v-if="showSettings")
				h3 Device Settings
				.setting-group
					.mdi.mdi-microphone
					select.device-select(v-model="selectedAudioInput", @change="applyDevices", :id="'prejoin-audio-input'")
						option(value="") Default microphone
						option(v-for="(d, index) in audioInputs", :key="d.deviceId", :value="d.deviceId") {{ d.label || 'Microphone ' + (index + 1) }}
				.setting-group
					.mdi.mdi-video
					select.device-select(v-model="selectedVideoInput", @change="applyDevices", :id="'prejoin-video-input'")
						option(value="") Default camera
						option(v-for="(d, index) in videoInputs", :key="d.deviceId", :value="d.deviceId") {{ d.label || 'Camera ' + (index + 1) }}

			.join-options
				label.join-option
					input.sr-only(type="checkbox", v-model="micOn", @change="handleMicToggle", :id="'prejoin-mic-checkbox'")
					.mdi(:class="micOn ? 'mdi-microphone' : 'mdi-microphone-off'")
					span Join with microphone {{ micOn ? 'on' : 'muted' }}
				label.join-option
					input.sr-only(type="checkbox", v-model="cameraOn", @change="handleCameraToggle", :id="'prejoin-camera-checkbox'")
					.mdi(:class="cameraOn ? 'mdi-video' : 'mdi-video-off'")
					span Join with camera {{ cameraOn ? 'on' : 'off' }}

			.join-actions
				button.btn-join(type="button", @click="join", :disabled="joining", :id="'prejoin-join-btn'")
					bunt-progress-circular(v-if="joining", size="small")
					span(v-else) Join Now
				.join-error(v-if="permissionError")
					.mdi.mdi-alert-circle-outline
					span {{ permissionError }}
</template>

<script>
import { mapState } from 'vuex'
import SoundMeter from 'lib/webrtc/soundmeter'

export default {
	name: 'JanusPrejoin',
	props: {
		roomName: {
			type: String,
			default: 'Meeting Room',
		},
	},
	emits: ['join'],
	data() {
		return {
			micOn: localStorage.micMuted === 'false',
			cameraOn: localStorage.videoRequested !== 'false',
			showSettings: false,
			joining: false,
			permissionError: null,
			hasCameraStream: false,
			// Devices
			audioInputs: [],
			videoInputs: [],
			selectedAudioInput: localStorage.audioInput || '',
			selectedVideoInput: localStorage.videoInput || '',
			// Preview streams
			cameraStream: null,
			audioStream: null,
			soundMeter: null,
			audioContext: null,
			audioLevel: 0,
			audioLevelInterval: null,
		}
	},
	computed: {
		...mapState(['user']),
		displayName() {
			return this.user?.profile?.display_name || 'You'
		},
		showCameraPlaceholder() {
			return !this.cameraOn || !this.hasCameraStream
		},
		cameraPlaceholderText() {
			return this.cameraOn ? 'Camera unavailable' : 'Camera is off'
		},
	},
	async mounted() {
		await this.enumerateDevices()
		await this.startPreview()
		this.audioLevelInterval = window.setInterval(this.updateAudioLevel, 100)
	},
	beforeUnmount() {
		this.stopPreview()
		if (this.audioLevelInterval) window.clearInterval(this.audioLevelInterval)
	},
	methods: {
		async enumerateDevices() {
			try {
				const devices = await navigator.mediaDevices.enumerateDevices()
				this.audioInputs = devices.filter(d => d.kind === 'audioinput')
				this.videoInputs = devices.filter(d => d.kind === 'videoinput')
			} catch (e) {
				console.warn('enumerateDevices failed', e)
			}
		},
		async startPreview() {
			this.permissionError = null
			await this.startCameraPreview()
			await this.startMicPreview()
		},
		async startCameraPreview() {
			if (this.cameraStream) {
				this.cameraStream.getTracks().forEach(t => t.stop())
				this.cameraStream = null
			}
			if (this.$refs.previewVideo) {
				this.$refs.previewVideo.srcObject = null
			}
			this.hasCameraStream = false
			if (!this.cameraOn) return
			try {
				const constraints = {
					video: this.selectedVideoInput ? { deviceId: { exact: this.selectedVideoInput } } : true,
				}
				this.cameraStream = await navigator.mediaDevices.getUserMedia(constraints)
				this.hasCameraStream = true
				await this.enumerateDevices()
				await this.$nextTick()
				if (this.$refs.previewVideo) {
					this.$refs.previewVideo.srcObject = this.cameraStream
				}
			} catch (e) {
				this.hasCameraStream = false
				if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
					this.permissionError = 'Camera access was denied. Please allow camera access in your browser.'
				}
			}
		},
		async startMicPreview() {
			if (this.audioStream) {
				this.audioStream.getTracks().forEach(t => t.stop())
				this.audioStream = null
			}
			if (this.soundMeter) {
				this.soundMeter.stop()
				this.soundMeter = null
			}
			if (this.audioContext) {
				this.audioContext.close().catch(() => {})
				this.audioContext = null
			}
			if (!this.micOn) return
			try {
				const constraints = {
					audio: this.selectedAudioInput ? { deviceId: { exact: this.selectedAudioInput } } : true,
				}
				this.audioStream = await navigator.mediaDevices.getUserMedia(constraints)
				this.audioContext = new AudioContext()
				this.soundMeter = new SoundMeter(this.audioContext)
				this.soundMeter.connectToSource(this.audioStream, (e) => {
					if (e) console.warn('SoundMeter error', e)
				})
				await this.enumerateDevices()
			} catch (e) {
				if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
					this.permissionError = 'Microphone access was denied. Please allow microphone access in your browser.'
				}
			}
		},
		stopPreview() {
			this.cameraStream?.getTracks().forEach(t => t.stop())
			this.audioStream?.getTracks().forEach(t => t.stop())
			this.soundMeter?.stop()
			this.audioContext?.close().catch(() => {})
			if (this.$refs.previewVideo) {
				this.$refs.previewVideo.srcObject = null
			}
			this.cameraStream = null
			this.audioStream = null
			this.soundMeter = null
			this.audioContext = null
		},
		updateAudioLevel() {
			if (this.soundMeter && this.micOn) {
				this.audioLevel = Math.min(1, this.soundMeter.instant * 10)
			} else {
				this.audioLevel = 0
			}
		},
		async toggleMic() {
			this.micOn = !this.micOn
			await this.startMicPreview()
		},
		async toggleCamera() {
			this.cameraOn = !this.cameraOn
			await this.startCameraPreview()
		},
		async handleMicToggle() {
			await this.startMicPreview()
		},
		async handleCameraToggle() {
			await this.startCameraPreview()
		},
		async applyDevices() {
			localStorage.audioInput = this.selectedAudioInput
			localStorage.videoInput = this.selectedVideoInput
			await this.startPreview()
		},
		join() {
			// Save preferences to localStorage before joining
			localStorage.micMuted = !this.micOn
			localStorage.videoRequested = this.cameraOn
			localStorage.audioInput = this.selectedAudioInput
			localStorage.videoInput = this.selectedVideoInput

			this.joining = true
			// Stop preview streams; JanusVideoroom will acquire them.
			this.stopPreview()
			if (this.audioLevelInterval) window.clearInterval(this.audioLevelInterval)

			this.$emit('join', {
				micMuted: !this.micOn,
				cameraEnabled: this.cameraOn,
				audioInput: this.selectedAudioInput,
				videoInput: this.selectedVideoInput,
			})
		},
	},
}
</script>

<style lang="stylus">
.c-janus-prejoin
	--prejoin-bg: #111315
	--prejoin-surface: #1a1f24
	--prejoin-surface-raised: #22282f
	--prejoin-surface-hover: #2a323b
	--prejoin-border: #343d47
	--prejoin-text: #edf1f5
	--prejoin-muted: #9aa6b2
	--prejoin-subtle: #6f7a86
	--prejoin-accent: #2f80ed
	--prejoin-accent-hover: #1f6fd1
	--prejoin-danger: #c83d3d
	--prejoin-danger-hover: #a93232
	--prejoin-success: #39a46a
	display: flex
	align-items: center
	justify-content: center
	flex: auto
	background: var(--prejoin-bg)
	min-height: 0

	.prejoin-layout
		display: flex
		gap: 48px
		align-items: center
		padding: 40px
		max-width: 960px
		width: 100%

		@media (max-width: 700px)
			flex-direction: column
			gap: 24px
			padding: 20px

	// Camera preview
	.preview-panel
		flex: 1 1 400px
		min-width: 0
		display: flex
		flex-direction: column
		gap: 16px

	.video-preview-wrap
		position: relative
		background: #070809
		border: 1px solid var(--prejoin-border)
		border-radius: 8px
		overflow: hidden
		aspect-ratio: 16 / 9
		box-shadow: 0 18px 44px rgba(0,0,0,0.36)

	.preview-video
		width: 100%
		height: 100%
		object-fit: cover
		transform: scaleX(-1) // Mirror like Zoom
		display: block
		border-radius: 8px

	.preview-avatar
		position: absolute
		inset: 0
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		gap: 12px
		background: var(--prejoin-surface)
		.mdi
			font-size: 80px
			color: var(--prejoin-subtle)
		span
			color: var(--prejoin-muted)
			font-size: 16px
			font-weight: 500

	.preview-overlay
		position: absolute
		inset: 0
		pointer-events: none

	.preview-status-label
		position: absolute
		bottom: 16px
		left: 50%
		transform: translateX(-50%)
		background: rgba(17,19,21,0.84)
		color: var(--prejoin-text)
		border: 1px solid rgba(255,255,255,0.12)
		border-radius: 6px
		padding: 6px 14px
		font-size: 13px
		display: flex
		align-items: center
		gap: 6px
		.mdi
			font-size: 16px

	.preview-controls
		display: flex
		align-items: center
		justify-content: center
		gap: 12px

	.preview-btn
		width: 52px
		height: 52px
		border-radius: 50%
		border: 1px solid var(--prejoin-border)
		background: var(--prejoin-surface-raised)
		color: var(--prejoin-text)
		cursor: pointer
		display: flex
		align-items: center
		justify-content: center
		flex-direction: column
		gap: 2px
		transition: background 0.2s, transform 0.1s
		position: relative
		&:hover, &:focus-visible
			background: var(--prejoin-surface-hover)
			outline: none
			transform: scale(1.05)
		&:focus-visible
			box-shadow: 0 0 0 3px rgba(47,128,237,0.35)
		&.off
			background: var(--prejoin-danger)
			border-color: var(--prejoin-danger)
			color: #fff
			&:hover, &:focus-visible
				background: var(--prejoin-danger-hover)
		.mdi
			font-size: 22px
		&.settings-btn
			background: var(--prejoin-surface-raised)
			&:hover
				background: var(--prejoin-surface-hover)

	.audio-indicator
		display: flex
		gap: 2px
		align-items: flex-end
		height: 10px
		position: absolute
		bottom: 4px

	.audio-bar
		width: 3px
		background: var(--prejoin-border)
		border-radius: 2px
		transition: height 0.1s, background 0.1s
		&:nth-child(1) { height: 4px }
		&:nth-child(2) { height: 6px }
		&:nth-child(3) { height: 8px }
		&:nth-child(4) { height: 6px }
		&:nth-child(5) { height: 4px }
		&.active
			background: var(--prejoin-success)

	// Join controls
	.join-panel
		flex: 0 0 280px
		display: flex
		flex-direction: column
		gap: 24px

	.room-info
		text-align: center
		display: flex
		flex-direction: column
		align-items: center
		gap: 12px

	.room-name
		color: var(--prejoin-text)
		font-size: 22px
		font-weight: 600
		margin: 0

	.room-label
		color: var(--prejoin-subtle)
		font-size: 14px
		margin: 0

	.device-settings
		background: var(--prejoin-surface)
		border: 1px solid var(--prejoin-border)
		border-radius: 8px
		padding: 16px
		display: flex
		flex-direction: column
		gap: 12px
		h3
			color: var(--prejoin-muted)
			font-size: 13px
			font-weight: 600
			text-transform: uppercase
			letter-spacing: 0
			margin: 0

	.setting-group
		display: flex
		align-items: center
		gap: 10px
		.mdi
			color: var(--prejoin-subtle)
			font-size: 18px
			flex-shrink: 0

	.device-select
		flex: auto
		background: var(--prejoin-surface-raised)
		color: var(--prejoin-text)
		border: 1px solid var(--prejoin-border)
		border-radius: 6px
		padding: 8px 10px
		font-size: 13px
		cursor: pointer
		&:focus, &:focus-visible
			outline: none
			border-color: var(--prejoin-accent)
			box-shadow: 0 0 0 3px rgba(47,128,237,0.24)

	.join-options
		display: flex
		flex-direction: column
		gap: 10px

	.join-option
		display: flex
		align-items: center
		gap: 12px
		color: var(--prejoin-muted)
		font-size: 14px
		cursor: pointer
		padding: 10px 14px
		border-radius: 8px
		background: var(--prejoin-surface)
		border: 1px solid var(--prejoin-border)
		transition: background 0.15s, border-color 0.15s, box-shadow 0.15s
		&:hover
			background: var(--prejoin-surface-hover)
		.sr-only
			position: absolute
			width: 1px
			height: 1px
			padding: 0
			margin: -1px
			overflow: hidden
			clip: rect(0, 0, 0, 0)
			white-space: nowrap
			border: 0
			&:focus-visible ~ .mdi
				box-shadow: 0 0 0 3px rgba(47,128,237,0.35)
				border-radius: 6px
		.mdi
			font-size: 20px
			color: var(--prejoin-accent)
			width: 24px
			text-align: center

	.join-actions
		display: flex
		flex-direction: column
		gap: 12px

	.btn-join
		width: 100%
		height: 52px
		border-radius: 8px
		border: none
		background: var(--prejoin-accent)
		color: #fff
		font-size: 16px
		font-weight: 600
		cursor: pointer
		display: flex
		align-items: center
		justify-content: center
		gap: 10px
		transition: opacity 0.2s, transform 0.1s, box-shadow 0.2s
		box-shadow: 0 8px 22px rgba(47,128,237,0.28)
		&:hover:not(:disabled)
			background: var(--prejoin-accent-hover)
			transform: translateY(-1px)
			box-shadow: 0 10px 26px rgba(47,128,237,0.34)
		&:focus-visible
			outline: none
			box-shadow: 0 0 0 3px rgba(47,128,237,0.35), 0 8px 22px rgba(47,128,237,0.28)
		&:disabled
			opacity: 0.6
			cursor: not-allowed

	.join-error
		display: flex
		align-items: flex-start
		gap: 8px
		color: #ffb3b3
		font-size: 13px
		background: rgba(200,61,61,0.16)
		border: 1px solid rgba(200,61,61,0.34)
		border-radius: 8px
		padding: 10px 12px
		.mdi
			font-size: 16px
			flex-shrink: 0
			margin-top: 1px
</style>
