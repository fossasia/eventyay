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
	.iframe-error(v-if="iframeError") {{ $t('MediaSource:iframe-error:text') }}
	.join-error(v-if="joinErrorKey", role="alert", aria-live="polite") {{ $t(joinErrorKey) }}
	iframe#video-player-translation(v-if="languageIframeUrl", :src="languageIframeUrl", style="position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none;", frameborder="0", gesture="media", allow="autoplay; encrypted-media", referrerpolicy="strict-origin-when-cross-origin")
</template>
<script setup>
// TODO functional component?
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useRoute } from 'vue-router';
import { useStore } from 'vuex';
import { isEqual } from 'lodash';
import api from 'lib/api';
import { normalizeYoutubeVideoId } from 'lib/validators';
import JanusCall from 'components/JanusCall';
import JanusChannelCall from 'components/JanusChannelCall';
import Livestream from 'components/Livestream';

// Props & Emits
defineOptions({
	components: { Livestream, JanusCall, JanusChannelCall },
});
const props = defineProps({
	room: Object,
	call: Object,
	background: {
		type: Boolean,
		default: false,
	},
});
defineEmits(['close']);

const store = useStore();
const route = useRoute();

const iframeError = ref(null);
const joinErrorKey = ref(null);
const iframeEl = ref(null);
const languageIframeUrl = ref(null);
const isUnmounted = ref(false);


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

const inRoomManager = computed(() => route.name === 'room:manage');

watch(
	() => props.background,
	(value) => {
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

watch(youtubeTransUrl, (ytUrl) => {
	if (!props.room) return;
	const streamType = props.room?.currentStream?.stream_type;
	const isYouTube = streamType === 'youtube' || module.value?.type === 'livestream.youtube';
	if (!isYouTube) return;

	// Handle translation: mute main player and create translation audio iframe
	if (ytUrl) {
		// Create hidden translation audio iframe first
		languageIframeUrl.value = getLanguageIframeUrl(ytUrl);
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
	iframeEl.value?.remove();
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

function getJoinErrorKey(error) {
	const code =
		error?.apiError?.code ??
		error?.error ??
		error?.message ??
		null

	switch (code) {
		case 'bbb.join.missing_profile':
			return 'MediaSource:join-error:missing-profile:text'

		case 'bbb.failed':
			return 'MediaSource:join-error:bbb-failed:text'

		case 'bbb.no_server':
			return 'MediaSource:join-error:no-server:text'

		case 'zoom.no_meeting_id':
			return 'MediaSource:join-error:zoom-no-meeting-id:text'

		default:
			return 'MediaSource:join-error:default:text'
	}
}

async function initializeIframe(mute) {
	joinErrorKey.value = null
	iframeError.value = null
	try {
		if (!module.value) return;
		if (shouldUseLivestream.value) return;
		let iframeUrl;
		let hideIfBackground = false;
		let isYouTube = false;
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
        joinErrorKey.value = getJoinErrorKey(error);
    
        if (joinErrorKey.value) {
        iframeError.value = null;
      } else {
        iframeError.value = error;
      }
		  
      console.error('MediaSource join failed:', error)
	}
}

function destroyIframe() {
	iframeEl.value?.remove();
	iframeEl.value = null;
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
	if (module.value?.type === 'call.bigbluebutton') {
		return !!iframeEl.value;
	}
	if (module.value?.type === 'call.zoom') {
		return !!iframeEl.value;
	}
	return true;
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
.c-media-source .c-livestream, .c-media-source .c-januscall, .c-media-source .c-januschannelcall, iframe.iframe-media-source
	position: fixed
	transition: all .3s ease
	&.size-tiny, &.background
		bottom: calc(var(--vh100) - 48px - 51px)
		right: 4px + 36px + 4px
		+below('l')
			bottom: calc(var(--vh100) - 48px - 48px - 3px)
	&:not(.size-tiny):not(.background)
		top: 104px
		width: var(--mediasource-placeholder-width)
		height: var(--mediasource-placeholder-height)
		+below('l')
			bottom: calc(var(--vh100) - 48px - 56px - var(--mediasource-placeholder-height))
			right: calc(100vw - var(--mediasource-placeholder-width))
iframe.iframe-media-source
	transition: all .3s ease
	border: none
	&.background
		pointer-events: none
		height: 48px
		width: 86px
		z-index: 101
		&.hide-if-background
			width: 0
			height: 0
.join-error
	position: fixed
	top: 120px
	left: 50%
	transform: translateX(-50%)
	background: rgba($clr-danger, 0.12)
	color: $clr-danger
	padding: 12px 16px
	border-radius: 4px
	z-index: 200
	max-width: 420px
	text-align: center

</style>
