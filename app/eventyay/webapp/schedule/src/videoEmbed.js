/**
 * Convert a video-link custom field answer into an iframe embed URL.
 * Only YouTube/Vimeo are embedded; timestamps are preserved; autoplay is off.
 */

function parseTimeToSeconds (value) {
	if (value == null) return null
	const raw = String(value).trim()
	if (!raw) return null
	if (/^\d+$/.test(raw)) return Number(raw)
	const match = /^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$/.exec(raw)
	if (!match || (!match[1] && !match[2] && !match[3])) return null
	const hours = Number(match[1] || 0)
	const minutes = Number(match[2] || 0)
	const seconds = Number(match[3] || 0)
	return hours * 3600 + minutes * 60 + seconds
}

function youtubeStartSeconds (parsed) {
	for (const key of ['start', 't']) {
		const value = parsed.searchParams.get(key)
		const seconds = parseTimeToSeconds(value)
		if (seconds != null && seconds > 0) return seconds
	}
	if (parsed.hash && parsed.hash.startsWith('#t=')) {
		const seconds = parseTimeToSeconds(parsed.hash.slice(3))
		if (seconds != null && seconds > 0) return seconds
	}
	return null
}

function vimeoTimeHash (parsed) {
	if (parsed.hash && parsed.hash.startsWith('#t=')) {
		const fragmentTime = parsed.hash.slice(3)
		if (parseTimeToSeconds(fragmentTime) != null) return `t=${fragmentTime}`
	}
	for (const key of ['t', 'time']) {
		const value = parsed.searchParams.get(key)
		const seconds = parseTimeToSeconds(value)
		if (seconds != null && seconds > 0) return `t=${seconds}s`
	}
	return null
}

function youtubeEmbedUrl (videoId, parsed) {
	const params = new URLSearchParams({ autoplay: '0' })
	const start = youtubeStartSeconds(parsed)
	if (start) params.set('start', String(start))
	return `https://www.youtube-nocookie.com/embed/${videoId}?${params.toString()}`
}

function vimeoEmbedUrl (videoId, parsed) {
	let embedUrl = `https://player.vimeo.com/video/${videoId}?autoplay=0`
	const timeHash = vimeoTimeHash(parsed)
	if (timeHash) embedUrl += `#${timeHash}`
	return embedUrl
}

export function getVideoEmbedUrl (url) {
	if (!url || typeof url !== 'string') return ''
	const raw = url.trim()
	if (!raw) return ''
	let parsed
	try {
		parsed = new URL(raw)
	} catch {
		return ''
	}
	if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return ''

	const host = parsed.hostname.replace(/^www\./, '').toLowerCase()
	const parts = parsed.pathname.split('/').filter(Boolean)

	if (host === 'youtu.be') {
		const id = parts[0]
		return id ? youtubeEmbedUrl(id, parsed) : ''
	}
	if (host === 'youtube.com' || host === 'm.youtube.com' || host === 'youtube-nocookie.com') {
		let id = null
		if (parts[0] === 'embed' || parts[0] === 'shorts' || parts[0] === 'live' || parts[0] === 'v') {
			id = parts[1] || null
		} else {
			id = parsed.searchParams.get('v')
		}
		return id ? youtubeEmbedUrl(id, parsed) : ''
	}
	if (host === 'vimeo.com' || host === 'player.vimeo.com') {
		let id = null
		if (host === 'player.vimeo.com' && parts[0] === 'video' && parts[1]) {
			id = parts[1]
		} else {
			id = [...parts].reverse().find((part) => /^\d+$/.test(part)) || null
		}
		return id ? vimeoEmbedUrl(id, parsed) : ''
	}
	return ''
}
