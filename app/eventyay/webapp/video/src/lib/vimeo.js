/**
 * Utility functions for parsing Vimeo URLs and generating embed URLs with playback parameters.
 */

const VIMEO_HOSTS = new Set(['vimeo.com', 'www.vimeo.com', 'player.vimeo.com'])

/**
 * Parses any Vimeo URL or ID and returns structured information:
 * - id: numeric video/event ID
 * - isLiveEvent: boolean true if URL is /event/12345
 * - hash: privacy hash string if unlisted URL (e.g. vimeo.com/12345/abcdef)
 * - originalUrl: raw input
 */
export function parseVimeoUrl(input) {
	if (!input) return null
	const trimmed = String(input).trim()
	if (!trimmed) return null

	// Raw numeric ID
	if (/^\d+$/.test(trimmed)) {
		return {
			id: trimmed,
			isLiveEvent: false,
			hash: null,
			originalUrl: trimmed
		}
	}

	try {
		const parsed = new URL(trimmed.includes('://') ? trimmed : `https://${trimmed}`)
		const host = parsed.hostname.toLowerCase().replace(/^www\./, '')
		if (!VIMEO_HOSTS.has(host) && host !== 'vimeo.com') {
			return null
		}

		const pathname = parsed.pathname.replace(/\/+$/, '')
		const pathParts = pathname.split('/').filter(Boolean)

		// Check for live event: /event/123456 or /event/123456/embed
		if (pathParts[0] === 'event' && pathParts[1] && /^\d+$/.test(pathParts[1])) {
			return {
				id: pathParts[1],
				isLiveEvent: true,
				hash: null,
				originalUrl: trimmed
			}
		}

		// Check for player.vimeo.com/video/123456
		if (host === 'player.vimeo.com' && pathParts[0] === 'video' && pathParts[1] && /^\d+$/.test(pathParts[1])) {
			const hash = parsed.searchParams.get('h') || (pathParts[2] && !/^\d+$/.test(pathParts[2]) ? pathParts[2] : null)
			return {
				id: pathParts[1],
				isLiveEvent: false,
				hash: hash || null,
				originalUrl: trimmed
			}
		}

		// Standard video: /123456 or unlisted: /123456/abcdef or /channels/.../123456 or /groups/.../videos/123456
		const lastNumIdx = pathParts.findIndex(p => /^\d+$/.test(p))
		if (lastNumIdx !== -1) {
			const videoId = pathParts[lastNumIdx]
			// Unlisted privacy hash comes immediately after the numeric ID
			let hash = parsed.searchParams.get('h') || null
			if (!hash && pathParts.length > lastNumIdx + 1 && !/^\d+$/.test(pathParts[lastNumIdx + 1])) {
				hash = pathParts[lastNumIdx + 1]
			}
			return {
				id: videoId,
				isLiveEvent: false,
				hash: hash || null,
				originalUrl: trimmed
			}
		}

		return null
	} catch {
		return null
	}
}

/**
 * Builds a player.vimeo.com embed URL from input and playback config options.
 *
 * Supported options:
 * - autoplay: boolean
 * - startMuted: boolean
 * - loop: boolean
 * - hideControls: boolean
 * - disableKb: boolean (disables keyboard shortcuts)
 * - dnt: boolean (do not track / privacy mode)
 * - showInfo: boolean (if true, hides title/byline/portrait; defaults to showing)
 * - password: string (optional passcode for password-protected videos)
 */
export function getVimeoEmbedUrl(input, options = {}) {
	const parsed = parseVimeoUrl(input)
	if (!parsed) return null

	const { id, isLiveEvent, hash } = parsed
	const base = isLiveEvent
		? `https://vimeo.com/event/${id}/embed`
		: `https://player.vimeo.com/video/${id}`

	const params = new URLSearchParams()

	if (options.autoplay) {
		params.set('autoplay', '1')
	} else {
		params.set('autoplay', '0')
	}

	if (options.startMuted) {
		params.set('muted', '1')
	}

	if (options.loop) {
		params.set('loop', '1')
	}

	if (options.hideControls) {
		params.set('controls', '0')
	}

	if (options.disableKb) {
		params.set('keyboard', '0')
	}

	if (options.dnt || options.enablePrivacyEnhancedMode) {
		params.set('dnt', '1')
	}

	if (options.showInfo) {
		// When "Hide Video Info" is checked, suppress title, byline, and portrait
		params.set('title', '0')
		params.set('byline', '0')
		params.set('portrait', '0')
	}

	// Privacy hash for unlisted videos
	if (hash) {
		params.set('h', hash)
	}

	// Password protection
	const password = options.password ? String(options.password).trim() : ''
	if (password) {
		params.set('password', password)
	}

	const queryString = params.toString()
	return queryString ? `${base}?${queryString}` : base
}
