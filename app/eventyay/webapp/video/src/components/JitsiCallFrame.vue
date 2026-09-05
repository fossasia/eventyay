<template lang="pug">
.c-jitsi-call-frame(:class="[`size-${size}`]")
	.loading-state(v-if="loading && !error")
		bunt-progress-circular(size="huge", :page="true")
		span.loading-text {{ $t('Connecting to meeting…') }}
	.error-state(v-else-if="error")
		.mdi.mdi-alert-circle-outline.state-icon--error
		p.error-title {{ $t('Could not join meeting room.') }}
		p.error-detail(v-if="errorMsg") {{ errorMsg }}
		bunt-button.retry-btn(@click="joinJitsi") {{ $t('Retry') }}
	.jitsi-container(ref="jitsiContainer", v-show="!error")
</template>

<script>
import api from 'lib/api'

export default {
	name: 'JitsiCallFrame',
	props: {
		room: {
			type: Object,
			required: true
		},
		module: {
			type: Object,
			required: true
		},
		size: {
			type: String,
			default: 'normal'
		}
	},
	emits: ['connected', 'hangup', 'error', 'participants-change'],
	data() {
		return {
			loading: true,
			error: null,
			errorMsg: null,
			jitsiApi: null,
			isDestroyed: false,
			hasJoinedConference: false,
			userLeftConference: false
		}
	},
	async mounted() {
		await this.joinJitsi()
	},
	beforeUnmount() {
		this.isDestroyed = true
		this.cleanupMedia()
	},
	methods: {
		async joinJitsi() {
			this.loading = true
			this.error = null
			this.errorMsg = null
			this.cleanupMedia()
			await this.$nextTick()

			try {
				const config = await api.call('jitsi.room_config', { room: this.room.id })
				if (this.isDestroyed) return

				const isHttp = (config.protocol && config.protocol.startsWith('http:')) || (config.url && config.url.startsWith('http:'))
				const scheme = isHttp ? 'http' : 'https'
				const wsScheme = isHttp ? 'ws' : 'wss'
				const serverUrl = config.url || `${scheme}://${config.domain}`

				// Force SFU scalability defaults (disable P2P, enable layer suspension)
				const configOverwrite = {
					p2p: { enabled: false },
					enableLayerSuspension: true,
					resolution: 720,
					prejoinPageEnabled: false,
					prejoinConfig: { enabled: false },
					enableLobby: false,
					lobby: { enable: false },
					tokenAuthUrl: null,
					securityUi: { hideLobbyButton: true },
					requireDisplayName: false,
					disableDeepLinking: true,
					enableWelcomePage: false,
					welcomePage: { disabled: true },
					...(config.domain && !config.domain.includes('meet.jit.si') ? {
						bosh: `${scheme}://${config.domain}/http-bind`,
						websocket: `${wsScheme}://${config.domain}/xmpp-websocket`
					} : {}),
					...(config.configOverwrite || {})
				}

				const JitsiMeetExternalAPI = await this.loadJitsiExternalApi(config)
				if (this.isDestroyed) return

				await this.$nextTick()
				if (!this.$refs.jitsiContainer) {
					throw new Error('Jitsi container not available')
				}

				const jitsiOptions = {
					roomName: config.roomName,
					parentNode: this.$refs.jitsiContainer,
					serverURL: serverUrl,
					protocol: scheme,
					scheme: scheme,
					noSSL: (scheme === 'http'),
					configOverwrite,
					interfaceConfigOverwrite: config.interfaceConfigOverwrite,
					userInfo: config.userInfo
				}
				if (config.jwt) {
					jitsiOptions.jwt = config.jwt
				}

				this.jitsiApi = new JitsiMeetExternalAPI(config.domain, jitsiOptions)

				// Ensure iframe permissions are fully set
				this.$nextTick(() => {
					const iframe = this.$refs.jitsiContainer?.querySelector('iframe')
					if (iframe) {
						iframe.setAttribute('allow', 'camera *; microphone *; display-capture *; autoplay *; clipboard-write *; screen-wake-lock *; speaker-selection *')
						iframe.setAttribute('allowfullscreen', 'true')
						iframe.setAttribute('allowusermedia', 'true')
					}
				})

				// Once the iframe is mounted, reveal it immediately so the user can interact
				setTimeout(() => {
					if (!this.isDestroyed) {
						this.loading = false
						this.$emit('connected')
					}
				}, 400)

				this.jitsiApi.addListener('videoConferenceJoined', () => {
					this.loading = false
					this.hasJoinedConference = true
					this.$emit('connected')
					if (config.roomDisplayName) {
						try {
							this.jitsiApi.executeCommand('subject', config.roomDisplayName)
						} catch (e) {}
					}
					if (!config.jwt && config.userInfo?.displayName) {
						try {
							this.jitsiApi.executeCommand('displayName', config.userInfo.displayName)
						} catch (e) {}
					}
					if (!config.jwt && config.userInfo?.email) {
						try {
							this.jitsiApi.executeCommand('email', config.userInfo.email)
						} catch (e) {}
					}
					if (config.userInfo?.avatar && typeof config.userInfo.avatar === 'string' && config.userInfo.avatar.trim()) {
						try {
							this.jitsiApi.executeCommand('avatarUrl', config.userInfo.avatar.trim())
						} catch (e) {}
					}
				})

				this.jitsiApi.addListener('videoConferenceLeft', () => {
					this.userLeftConference = true
				})

				this.jitsiApi.addListener('readyToClose', () => {
					if (this.userLeftConference || this.hasJoinedConference) {
						this.hangup()
					} else {
						this.loading = false
						this.error = new Error('Meeting closed unexpectedly')
						this.errorMsg = this.$t('Connection to the meeting was interrupted.')
						this.$emit('error', this.error)
					}
				})

				this.jitsiApi.addListener('participantJoined', (p) => {
					this.$emit('participants-change', p)
				})

				this.jitsiApi.addListener('participantLeft', (p) => {
					this.$emit('participants-change', p)
				})
			} catch (err) {
				this.loading = false
				this.error = err
				if (err?.code === 'jitsi.join.missing_profile') {
					this.errorMsg = this.$t('Please update your display name in your profile to join.')
				} else if (err?.code === 'jitsi.server_unavailable') {
					this.errorMsg = this.$t('No active meeting server available.')
				} else {
					this.errorMsg = this.$t('Could not establish connection with meeting server.')
				}
				this.$emit('error', err)
			}
		},
		toggleMic() {
			if (this.jitsiApi) {
				this.jitsiApi.executeCommand('toggleAudio')
			}
		},
		toggleCamera() {
			if (this.jitsiApi) {
				this.jitsiApi.executeCommand('toggleVideo')
			}
		},
		cleanupMedia() {
			if (this.jitsiApi) {
				try {
					this.jitsiApi.dispose()
				} catch (e) {}
				this.jitsiApi = null
			}
			if (this.$refs.jitsiContainer) {
				this.$refs.jitsiContainer.innerHTML = ''
			}
		},
		hangup() {
			this.userLeftConference = true
			if (this.jitsiApi) {
				try {
					this.jitsiApi.executeCommand('hangup')
				} catch (e) {}
			}
			this.cleanupMedia()
			this.$emit('hangup')
		},
		async loadJitsiExternalApi(config) {
			if (window.JitsiMeetExternalAPI && window.JitsiMeetExternalAPI._patchedForHttp) {
				return window.JitsiMeetExternalAPI
			}
			const baseUrl = config.url || (String(config.protocol).startsWith('http:') ? `http://${config.domain}` : `https://${config.domain}`)
			const scriptUrl = `${baseUrl.replace(/\/+$/, '')}/external_api.js`

			try {
				const resp = await fetch(scriptUrl)
				let code = await resp.text()
				const target = 'url:`https://${t}/#jitsi_meet_external_api_id=${j}`'
				const replacement = 'url:`${(e&&e.protocol)?(e.protocol.endsWith(":")?e.protocol:e.protocol+":"):(typeof location!=="undefined"?location.protocol:"https:")}//${t}/#jitsi_meet_external_api_id=${j}`'
				if (code.includes(target)) {
					code = code.replace(target, replacement)
				}
				const fn = new Function(code)
				fn()
				if (window.JitsiMeetExternalAPI) {
					window.JitsiMeetExternalAPI._patchedForHttp = true
					return window.JitsiMeetExternalAPI
				}
			} catch (e) {
				console.warn('Could not fetch and patch external_api.js dynamically, falling back to script tag:', e)
			}

			return new Promise((resolve, reject) => {
				const script = document.createElement('script')
				script.src = scriptUrl
				script.async = true
				script.onload = () => {
					if (window.JitsiMeetExternalAPI) {
						resolve(window.JitsiMeetExternalAPI)
					} else {
						reject(new Error('JitsiMeetExternalAPI missing on window'))
					}
				}
				script.onerror = () => reject(new Error(`Failed to load script: ${scriptUrl}`))
				document.head.appendChild(script)
			})
		}
	}
}
</script>

<style lang="stylus">
.c-jitsi-call-frame
	flex: auto
	height: 100%
	width: 100%
	display: flex
	flex-direction: column
	position: relative
	overflow: hidden
	background-color: #111827

	.loading-state
		position: absolute
		inset: 0
		z-index: 10
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		background-color: #111827
		color: #f1f5f9
		gap: 16px
		padding: 24px

		.loading-text
			font-size: 16px
			color: #94a3b8
			font-weight: 500

	.error-state
		flex: auto
		display: flex
		flex-direction: column
		align-items: center
		justify-content: center
		color: #f1f5f9
		gap: 16px
		padding: 24px

		.state-icon--error
			font-size: 48px
			color: #ef4444

		.error-title
			font-size: 18px
			font-weight: 600
			color: #f8fafc
			margin: 0

		.error-detail
			font-size: 14px
			color: #94a3b8
			margin: 0

		.retry-btn
			background-color: #2185d0
			color: #ffffff
			border-radius: 6px

	.jitsi-container
		flex: auto
		width: 100%
		height: 100%
		position: relative

		iframe
			border: none
			width: 100%
			height: 100%
			display: block

	&.size-tiny
		.loading-state, .error-state
			display: none
</style>
