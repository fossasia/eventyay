<template lang="pug">
.c-media-source(:class="{'in-background': background, 'in-room-manager': inRoomManager}")
	transition(name="background-room")
		router-link.background-room(v-if="background", :to="room ? {name: 'room', params: {roomId: room.id}}: {name: 'channel', params: {channelId: call.channel}}")
			.description
				.hint {{ $t('MediaSource:room:hint') }}
				.room-name(v-if="room") {{ room.name }}
				.room-name(v-else-if="call") {{ $t('MediaSource:call:label') }}
			.global-placeholder
			bunt-icon-button(@click.prevent.stop="$emit('close')") close
	Livestream(v-if="room && shouldUseLivestream", ref="livestream", :room="room", :module="module", :size="background ? 'tiny' : 'normal'", :key="`livestream-${room.id}`")
	JanusCall(v-else-if="room && module.type === 'call.janus'", ref="janus", :room="room", :module="module", :background="background", :size="background ? 'tiny' : 'normal'", :key="`janus-${room.id}`")
	JanusChannelCall(v-else-if="call", ref="janus", :call="call", :background="background", :size="background ? 'tiny' : 'normal'", :key="`call-${call.id}`", @close="$emit('close')")
	.iframe-consent-gate(v-if="consentBlockedUrl && !background")
		iframe-blocker(:src="consentBlockedUrl", allow="camera *; autoplay *; microphone *; fullscreen *; display-capture *", allowfullscreen, @consent-given="onConsentGiven")
	.iframe-error(v-if="!iframeEl && !consentBlockedUrl && (iframeError || iframeOffline)", :class="{background: background, 'size-tiny': background}")
		.offline-message(v-if="iframeOffline") {{ $t('Livestream:offline-message:text') }}
		.offline-message(v-else) {{ $t('MediaSource:iframe-error:text') }}
	iframe#video-player-translation(v-if="languageIframeUrl", :src="languageIframeUrl", style="position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none;", frameborder="0", gesture="media", allow="autoplay; encrypted-media", referrerpolicy="strict-origin-when-cross-origin")
	audio(ref="whepAudioEl", autoplay, style="display: none;")
</template>
<script setup>
// TODO functional component?
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useRoute } from 'vue-router';
import { useStore } from 'vuex';
import { isEqual } from 'lodash';
import api from 'lib/api';
import { normalizeYoutubeVideoId } from 'lib/validators';
import { isDomainBlocked, getUrlDomain } from 'lib/iframeConsent';
import IframeBlocker from 'components/IframeBlocker';
import JanusCall from 'components/JanusCall';
import JanusChannelCall from 'components/JanusChannelCall';
import Livestream from 'components/Livestream';
import { WhepClient } from 'lib/webrtc/whep';

const jitsiScriptLoads = new Map();

// Props & Emits
defineOptions({
	components: { Livestream, JanusCall, JanusChannelCall, IframeBlocker },
});
const props = defineProps({
	room: Object,
	call: Object,
	background: {
		type: Boolean,
		default: false,
	},
});
const emit = defineEmits(['close']);

const store = useStore();
const route = useRoute();

const iframeError = ref(null);
const iframeEl = ref(null);
const languageIframeUrl = ref(null);
const isUnmounted = ref(false);
const consentBlockedUrl = ref(null);
// Prevents overlapping initializeIframe runs (e.g. store watcher + consent handler)
// from both passing the iframeEl guard before the first await.
let iframeInitInProgress = false;
let jitsiApi = null;

// WHEP audio client
const whepAudioEl = ref(null);
let whepClient = null;

// Template refs
const livestream = ref(null);
const janus = ref(null);

// Mapped state/getters
const streamingRoom = computed(() => store.state.streamingRoom);
const youtubeTransUrl = computed(() => store.state.youtubeTransUrl);
const autoplay = computed(() => store.getters.autoplay);

const module = computed(() => {
	if (!props.room) return null;
	return props.room.modules.find((m) =>
		[
			'livestream.native',
			'livestream.youtube',
			'livestream.iframe',
			'call.bigbluebutton',
			'call.janus',
			'call.zoom',
			'call.jitsi',
		].includes(m.type)
	);
});

const shouldUseLivestream = computed(() => {
	if (!props.room || !module.value) return false;
	if (module.value.type !== 'livestream.native') return false;
	const streamType = props.room?.currentStream?.stream_type;
	if (streamType && streamType !== 'hls') {
		return false;
	}
	return true;
});

// When stream schedules are enabled, the backend returns 404 (mapped to null) if
// no stream is currently active. For iframe-based streams we show a full-size
// offline placeholder (same frame size as the player) instead of showing nothing.
//
// Important: If the module has a configured default URL/ytid, we still render it
// even when there is no active schedule.
const iframeOffline = computed(() => {
	if (!props.room || !module.value) return false;
	if (shouldUseLivestream.value) return false;

	const streamType = props.room?.currentStream?.stream_type;
	const moduleType = module.value.type;
	const isIFrame = streamType === 'iframe' || moduleType === 'livestream.iframe';
	const isYouTube = streamType === 'youtube' || moduleType === 'livestream.youtube';
	const isVimeo = streamType === 'vimeo';

	if (!isIFrame && !isYouTube && !isVimeo) return false;

	// Prefer schedule-provided stream URL when present.
	const scheduleUrl = props.room?.currentStream?.url || null;
	if (isYouTube) {
		if (scheduleUrl && normalizeYoutubeVideoId(scheduleUrl)) return false;
		const ytid = module.value.config?.ytid || null;
		if (ytid && normalizeYoutubeVideoId(ytid)) return false;
		return true;
	}

	if (scheduleUrl) return false;
	const moduleUrl = module.value.config?.url || null;
	return !moduleUrl;
});

const inRoomManager = computed(() => route.name === 'room:manage');

watch(
	() => props.background,
	(value) => {
		if (value && consentBlockedUrl.value && !iframeEl.value) {
			emit('close')
			return
		}
		if (!iframeEl.value) return;
		if (value) {
			iframeEl.value.classList.add('background');
			iframeEl.value.classList.add('size-tiny');
		} else {
			iframeEl.value.classList.remove('background');
			iframeEl.value.classList.remove('size-tiny');
		}
	}
);

watch(module, (value, oldValue) => {
	if (isEqual(value, oldValue)) return;
	destroyIframe();
	if (shouldUseLivestream.value) return;
	initializeIframe(false);
});

watch(shouldUseLivestream, (shouldUse, oldShouldUse) => {
	if (shouldUse === oldShouldUse) return;
	if (shouldUse) {
		destroyIframe();
	} else {
		initializeIframe(false);
	}
});

watch(
	() => props.room?.currentStream,
	(newStream, oldStream) => {
		if (!isEqual(newStream, oldStream) && module.value) {
			if (shouldUseLivestream.value) {
				return;
			}
			destroyIframe();
			initializeIframe(false);
		}
	},
	{ deep: true }
);

watch(
	() => store.state.unblockedIframeDomains,
	() => {
		if (iframeEl.value) return
		if (!consentBlockedUrl.value) return // gate not active; nothing to reconcile
		const domain = getUrlDomain(consentBlockedUrl.value)
		if (domain && !isDomainBlocked(domain)) {
			consentBlockedUrl.value = null
			// Covers store-only unblocks (e.g. consent changed elsewhere) while the
			// gate URL is still set. Persistent "Remember" relies on this path only;
			// onConsentGiven skips initializeIframe for that case to avoid a double init race.
			initializeIframe(false)
		}
	}
)

watch(youtubeTransUrl, async (audioSource) => {
	if (!props.room) return;
	const streamType = props.room?.currentStream?.stream_type;
	const isYouTube = streamType === 'youtube' || module.value?.type === 'livestream.youtube';
	if (!isYouTube) return;

	// Teardown previous whep client
	if (whepClient) {
		whepClient.disconnect();
		whepClient = null;
	}

	// Handle translation: mute main player and connect audio source
	if (audioSource) {
		let isWhep = false;
		try {
			new URL(audioSource);
			if (!normalizeYoutubeVideoId(audioSource)) {
				isWhep = true;
			}
		} catch (e) {
			isWhep = false;
		}

		if (isWhep) {
			languageIframeUrl.value = null;
			whepClient = new WhepClient(audioSource, whepAudioEl.value);
			try {
				await whepClient.connect();
			} catch (err) {
				console.error('Failed to connect to WHEP translation source', err);
			}
		} else {
			// Create hidden translation audio iframe first
			languageIframeUrl.value = getLanguageIframeUrl(audioSource);
		}
		
		// Mute the main player using postMessage after a short delay
		setTimeout(() => {
			muteYouTubePlayer();
		}, 500);
	} else {
		// Remove translation audio iframe
		languageIframeUrl.value = null;
		// Unmute the main player using postMessage after a short delay
		setTimeout(() => {
			unmuteYouTubePlayer();
		}, 100);
	}
});

onMounted(async () => {
	if (!props.room) return;
	if (shouldUseLivestream.value) return;
	await initializeIframe(false);
});

onBeforeUnmount(() => {
	isUnmounted.value = true;
	if (whepClient) {
		whepClient.disconnect();
		whepClient = null;
	}
	iframeEl.value?.remove();
	jitsiApi?.dispose?.();
	jitsiApi = null;
	if (api.socketState !== 'open') return;
	// TODO move to store?
	if (props.room) api.call('room.leave', { room: props.room.id });
});

function muteYouTubePlayer() {
	if (!iframeEl.value || !iframeEl.value.contentWindow) return;
	try {
		iframeEl.value.contentWindow.postMessage(
			'{"event":"command","func":"mute","args":""}',
			'*'
		);
	} catch (error) {
		console.warn('Failed to mute embedded YouTube player', {
			roomId: props.room?.id,
			error,
		});
	}
}

function unmuteYouTubePlayer() {
	if (!iframeEl.value || !iframeEl.value.contentWindow) return;
	try {
		iframeEl.value.contentWindow.postMessage(
			'{"event":"command","func":"unMute","args":""}',
			'*'
		);
	} catch (error) {
		console.warn('Failed to unmute embedded YouTube player', {
			roomId: props.room?.id,
			error,
		});
	}
}

async function initializeIframe(mute, skipConsentCheck = false) {
	if (!module.value) return;
	if (shouldUseLivestream.value) return;
	if (iframeOffline.value) return;
	if (iframeEl.value) return; // already initialised
	if (iframeInitInProgress) return;
	iframeInitInProgress = true;
	iframeError.value = null;
	try {
		let iframeUrl;
		let hideIfBackground = false;
		let isYouTube = false;
		let jitsiConfig = null;
		const streamType = props.room?.currentStream?.stream_type;
		const effectiveModuleType = streamType === 'youtube' 
			? 'livestream.youtube' 
			: streamType === 'vimeo'
			? 'livestream.vimeo'
			: streamType === 'iframe'
			? 'livestream.iframe'
			: module.value.type;
		switch (effectiveModuleType) {
			case 'call.bigbluebutton': {
				({ url: iframeUrl } = await api.call('bbb.room_url', {
					room: props.room.id,
				}));
				hideIfBackground = true;
				break;
			}
			case 'call.zoom': {
				({ url: iframeUrl } = await api.call('zoom.room_url', {
					room: props.room.id,
				}));
				hideIfBackground = true;
				break;
			}
			case 'call.jitsi': {
				jitsiConfig = await api.call('jitsi.room_config', {
					room: props.room.id,
				});
				iframeUrl = getJitsiRoomUrl(jitsiConfig);
				hideIfBackground = true;
				break;
			}
			case 'livestream.iframe': {
				if (props.room?.currentStream?.url) {
					iframeUrl = props.room.currentStream.url;
				} else {
					iframeUrl = module.value.config.url;
				}
				break;
			}
			case 'livestream.vimeo': {
				if (props.room?.currentStream?.url) {
					const vimeoMatch = props.room.currentStream.url.match(/vimeo\.com\/(?:.*\/)?(\d+)/);
					if (vimeoMatch) {
						iframeUrl = `https://player.vimeo.com/video/${vimeoMatch[1]}?autoplay=${autoplay.value ? '1' : '0'}&muted=${mute ? '1' : '0'}`;
					} else {
						iframeUrl = props.room.currentStream.url;
					}
				} else if (module.value.config?.url) {
					const vimeoMatch = module.value.config.url.match(/vimeo\.com\/(?:.*\/)?(\d+)/);
					if (vimeoMatch) {
						iframeUrl = `https://player.vimeo.com/video/${vimeoMatch[1]}?autoplay=${autoplay.value ? '1' : '0'}&muted=${mute ? '1' : '0'}`;
					} else {
						iframeUrl = module.value.config.url;
					}
				}
				break;
			}
			case 'livestream.youtube': {
				isYouTube = true;
				let ytid;
				if (streamType === 'youtube' && props.room?.currentStream?.url) {
					ytid = normalizeYoutubeVideoId(props.room.currentStream.url);
				} else if (module.value.type === 'livestream.youtube' && module.value.config?.ytid) {
					ytid = normalizeYoutubeVideoId(module.value.config.ytid);
				} else {
					ytid = null;
				}
				if (!ytid) {
					iframeError.value = new Error('Invalid YouTube video ID');
					break;
				}
				const config = module.value.config || {};
				// Smart muting logic to balance autoplay and user control:
				// - Always mute if already muted (e.g., for language translation)
				// - Mute for autoplay ONLY if controls are visible (so user can unmute)
				// - If controls are hidden, don't force mute (autoplay may fail, but user gets audio when they click)
				const shouldMute = mute || (autoplay.value && !config.hideControls);
				iframeUrl = getYoutubeUrl(
					ytid,
					autoplay.value,
					shouldMute,
					config.hideControls,
					config.noRelated,
					config.showinfo,
					config.disableKb,
					config.loop,
					config.modestBranding,
					config.enablePrivacyEnhancedMode
				);
				break;
			}
		}
		if (!iframeUrl || isUnmounted.value) return;

		// Check iframe consent policy before creating the element.
		// skipConsentCheck is set when the user clicked "Show" in the consent gate
		// so the iframe can be created even for the "Show once" (non-persistent) path.
		// Consent applies to all iframe providers (including BBB/Zoom). hideIfBackground
		// only affects CSS for miniplayer layout, not whether consent is required.
		if (!skipConsentCheck) {
			const urlDomain = getUrlDomain(iframeUrl)
			if (isDomainBlocked(urlDomain)) {
				consentBlockedUrl.value = iframeUrl
				return
			}
		}
		// Consent is satisfied (or not required); clear any previous gate.
		consentBlockedUrl.value = null

		if (jitsiConfig) {
			await createJitsiIframe(jitsiConfig, hideIfBackground);
			return;
		}

		const iframe = document.createElement('iframe');
		iframe.src = iframeUrl;
		iframe.classList.add('iframe-media-source');
		if (hideIfBackground) {
			iframe.classList.add('hide-if-background');
		}
		// Add background and size-tiny classes if in background mode
		if (props.background) {
			iframe.classList.add('background');
			iframe.classList.add('size-tiny');
		}
		// Set iframe permissions and attributes
		iframe.allow =
			'screen-wake-lock *; camera *; microphone *; fullscreen *; display-capture *' +
			(autoplay.value ? '; autoplay *' : '');
		iframe.allowFullscreen = true;
		iframe.setAttribute('allowusermedia', 'true');
		iframe.setAttribute('allowfullscreen', ''); // iframe.allowfullscreen is not enough in firefox
		// Set referrerpolicy for YouTube embed compatibility (fixes Error 153)
		// https://developers.google.com/youtube/terms/required-minimum-functionality#embedded-player-api-client-identity
		if (isYouTube) {
			iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
			iframe.id = `youtube-player-${Date.now()}`;
		}
		const container = document.querySelector('#media-source-iframes');
		if (!container) return;
		container.appendChild(iframe);
		iframeEl.value = iframe;

		// Wait for iframe to load before sending postMessage commands
		if (isYouTube) {
			iframe.onload = () => {
				// If translation is already selected, mute the main player
				if (youtubeTransUrl.value) {
					setTimeout(() => muteYouTubePlayer(), 1000);
				}
			};
		}
	} catch (error) {
		iframeError.value = error;
	} finally {
		iframeInitInProgress = false;
	}
}

function destroyIframe() {
	jitsiApi?.dispose?.();
	jitsiApi = null;
	iframeEl.value?.remove();
	iframeEl.value = null;
	consentBlockedUrl.value = null;
}

async function createJitsiIframe(config, hideIfBackground) {
	const container = document.querySelector('#media-source-iframes');
	if (!container) return;
	if (config.protocol === 'http:') {
		createJitsiDirectIframe(config, hideIfBackground, container);
		return;
	}
	await loadJitsiExternalApi(config.domain);
	if (isUnmounted.value || !window.JitsiMeetExternalAPI) return;

	const options = {
		roomName: config.roomName,
		parentNode: container,
		userInfo: config.userInfo || {},
		configOverwrite: config.configOverwrite || {},
		interfaceConfigOverwrite: config.interfaceConfigOverwrite || {},
	};
	if (config.jwt) {
		options.jwt = config.jwt;
	}

	jitsiApi = new window.JitsiMeetExternalAPI(config.domain, options);
	const iframe = jitsiApi.getIFrame();
	if (!iframe) return;
	iframe.classList.add('iframe-media-source');
	iframe.classList.add('jitsi-media-source');
	if (hideIfBackground) {
		iframe.classList.add('hide-if-background');
	}
	if (props.background) {
		iframe.classList.add('background');
		iframe.classList.add('size-tiny');
	}
	iframe.allow =
		'screen-wake-lock *; camera *; microphone *; fullscreen *; display-capture *' +
		(autoplay.value ? '; autoplay *' : '');
	iframe.allowFullscreen = true;
	iframe.setAttribute('allowusermedia', 'true');
	iframe.setAttribute('allowfullscreen', '');
	iframeEl.value = iframe;
}

function createJitsiDirectIframe(config, hideIfBackground, container) {
	const iframe = document.createElement('iframe');
	iframe.src = getJitsiRoomUrl(config);
	iframe.classList.add('iframe-media-source');
	iframe.classList.add('jitsi-media-source');
	if (hideIfBackground) {
		iframe.classList.add('hide-if-background');
	}
	if (props.background) {
		iframe.classList.add('background');
		iframe.classList.add('size-tiny');
	}
	iframe.allow =
		'screen-wake-lock *; camera *; microphone *; fullscreen *; display-capture *' +
		(autoplay.value ? '; autoplay *' : '');
	iframe.allowFullscreen = true;
	iframe.setAttribute('allowusermedia', 'true');
	iframe.setAttribute('allowfullscreen', '');
	container.appendChild(iframe);
	iframeEl.value = iframe;
}

function loadJitsiExternalApi(domain) {
	if (window.JitsiMeetExternalAPI) return Promise.resolve();
	if (jitsiScriptLoads.has(domain)) return jitsiScriptLoads.get(domain);
	const promise = new Promise((resolve, reject) => {
		const script = document.createElement('script');
		script.async = true;
		script.src = `https://${domain}/external_api.js`;
		script.onload = resolve;
		script.onerror = reject;
		document.head.appendChild(script);
	});
	jitsiScriptLoads.set(domain, promise);
	return promise;
}

function encodeJitsiHash(prefix, values) {
	return Object.entries(values || {})
		.filter(([, value]) => value !== undefined && value !== null)
		.map(([key, value]) => `${prefix}.${key}=${encodeURIComponent(JSON.stringify(value))}`);
}

function getJitsiRoomUrl(config) {
	const url = new URL(config.url || `https://${config.domain}`);
	url.pathname = `/${encodeURIComponent(config.roomName)}`;
	if (config.jwt) {
		url.searchParams.set('jwt', config.jwt);
	}
	const hash = [
		...encodeJitsiHash('config', config.configOverwrite),
		...encodeJitsiHash('interfaceConfig', config.interfaceConfigOverwrite),
		...encodeJitsiHash('userInfo', config.userInfo),
	];
	if (hash.length) {
		url.hash = hash.join('&');
	}
	return url.toString();
}

function onConsentGiven(persistent) {
	if (persistent) {
		// Store commit runs first; unblockedIframeDomains watcher clears the gate and
		// calls initializeIframe once. Calling it here too can race with overlapping async inits.
		return
	}
	consentBlockedUrl.value = null
	initializeIframe(false, true)
}

function isPlaying() {
	if (props.call) {
		return janus.value?.roomId;
	}
	if (shouldUseLivestream.value) {
		return livestream.value?.playing && !livestream.value?.offline;
	}
	if (module.value?.type === 'call.janus') {
		return janus.value?.roomId;
	}
	// For every iframe-based module (BBB, Zoom, YouTube, Vimeo, custom iframe):
	// the room is "playing" only when the iframe element actually exists.
	// This correctly returns false when consent is pending (no iframe yet),
	// preventing App.vue from activating the miniplayer.
	return !!iframeEl.value;
}

function getYoutubeUrl(
	ytid,
	autoplayVal,
	mute,
	hideControls,
	noRelated,
	showinfo,
	disableKb,
	loop,
	modestBranding,
	enablePrivacyEnhancedMode
) {
	const params = new URLSearchParams();

	// Always add autoplay and mute as they control core functionality
	params.append('autoplay', autoplayVal ? '1' : '0');
	params.append('mute', mute ? '1' : '0');

	// Enable IFrame API for programmatic control
	params.append('enablejsapi', '1');
	params.append('origin', window.location.origin);

	// Only add optional parameters when explicitly enabled
	if (hideControls) {
		params.append('controls', '0');
	}

	if (noRelated) {
		params.append('rel', '0');
	}

	if (showinfo) {
		params.append('showinfo', '0');
	}

	if (disableKb) {
		params.append('disablekb', '1');
	}

	if (loop) {
		params.append('loop', '1');
		// Loop requires playlist parameter to work properly
		params.append('playlist', ytid);
	}

	if (modestBranding) {
		params.append('modestbranding', '1');
	}

	const domain = enablePrivacyEnhancedMode
		? 'www.youtube-nocookie.com'
		: 'www.youtube.com';
	return `https://${domain}/embed/${ytid}?${params}`;
}

// Added method to get the language iframe URL
function getLanguageIframeUrl(languageUrl) {
	// Checks if the languageUrl is not provided then return null
	if (!languageUrl) return null;
	const config = module.value?.config || {};
	const origin = window.location.origin;
	const params = new URLSearchParams({
		enablejsapi: '1',
		autoplay: '1',
		mute: '0', // Ensure translation audio is not muted
		modestbranding: '1',
		loop: '1',
		controls: '0',
		disablekb: '1',
		rel: '0',
		showinfo: '0',
		playlist: languageUrl,
		origin, // Required when using enablejsapi=1 (fixes Error 153)
	});

	const domain = config.enablePrivacyEnhancedMode
		? 'www.youtube-nocookie.com'
		: 'www.youtube.com';
	return `https://${domain}/embed/${languageUrl}?${params}`;
}

// Expose instance methods (used by parents via template refs)
defineExpose({ isPlaying });
</script>
<style lang="stylus">
.c-media-source
	position: absolute
	width: 0
	height: 0
	&.in-background
		z-index: 101
	.background-room
		position: fixed
		top: 51px
		right: 4px
		card()
		display: flex
		align-items: center
		height: 48px
		min-width: 280px
		max-width: 380px
		.description
			flex: auto
			align-self: stretch
			padding: 4px 8px
			max-width: 238px
			.hint
				color: $clr-secondary-text-light
				font-size: 10px
				margin-bottom: 2px
			.room-name
				color: var(--clr-text-primary)
				font-weight: 500
				flex-grow: 0
				ellipsis()
		.global-placeholder
			width: 86px
			flex: none
		.bunt-icon-button
			icon-button-style(style: clear)
			margin: 0 2px
		+below('l')
			top: 51px
	.background-room-enter-active, .background-room-leave-active
		transition: transform .3s ease
	// .background-room-enter-active
	// 	transition-delay: .1s
	.background-room-enter-from, .background-room-leave-to
		transform: translate(calc(-1 * var(--chatbar-width)), 52px)
.c-media-source .c-livestream, .c-media-source .c-januscall, .c-media-source .c-januschannelcall, .c-media-source .iframe-error, iframe.iframe-media-source
	position: fixed
	transition: all .3s ease
	&.size-tiny, &.background
		bottom: calc(var(--vh100) - 48px - 51px)
		right: 4px + 36px + 4px
		+below('l')
			bottom: calc(var(--vh100) - 48px - 48px - 3px)
	&:not(.size-tiny):not(.background)
		top: var(--mediasource-placeholder-top, 104px)
		left: var(--mediasource-placeholder-left, var(--sidebar-width))
		width: var(--mediasource-placeholder-width, 100vw)
		height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh))
iframe.iframe-media-source
	transition: all .3s ease
	border: none
	&.jitsi-media-source
		// Jitsi External API writes inline width/height on the generated iframe.
		// Force it back into the same measured media placeholder used by BBB/Zoom.
		&:not(.size-tiny):not(.background)
			top: var(--mediasource-placeholder-top, 104px) !important
			left: var(--mediasource-placeholder-left, var(--sidebar-width)) !important
			width: var(--mediasource-placeholder-width, 100vw) !important
			height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh)) !important
	&.background
		pointer-events: none
		height: 48px !important
		width: 86px !important
		z-index: 101
		&.hide-if-background
			width: 0 !important
			height: 0 !important
.c-media-source .iframe-consent-gate
	position: fixed
	display: flex
	transition: all .3s ease
	z-index: 1
	top: var(--mediasource-placeholder-top, 104px)
	left: var(--mediasource-placeholder-left, var(--sidebar-width))
	width: var(--mediasource-placeholder-width, 100vw)
	height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh))
	.c-iframe-blocker
		flex: auto
.c-media-source .iframe-error
	display: flex
	justify-content: center
	align-items: center
	background-color: $clr-blue-grey-200
	z-index: 1
	// Fallbacks prevent the overlay from shrinking to its text when
	// --mediasource-placeholder-* are not yet available.
	&:not(.size-tiny):not(.background)
		width: var(--mediasource-placeholder-width, 100vw)
		height: var(--mediasource-placeholder-height, var(--mobile-media-height, 40vh))
	&.size-tiny, &.background
		width: 86px
		height: 48px
		pointer-events: none
		z-index: 101
	.offline-message
		font-size: 36px
		color: $clr-secondary-text-light
		text-align: center
		padding: 16px
	&.size-tiny, &.background
		.offline-message
			font-size: 14px
			padding: 8px
</style>
