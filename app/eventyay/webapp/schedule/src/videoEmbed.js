/**
 * Convert a video-link custom field answer into an iframe embed URL.
 * YouTube, Vimeo, and Wikimedia Commons file pages are embedded.
 * Timestamps are preserved; autoplay is off.
 */

const COMMONS_VIDEO_EXTENSIONS = new Set(['webm', 'ogv', 'ogg', 'mp4', 'm4v', 'mpeg', 'mpg'])

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

function commonsFileName (parsed) {
	const host = parsed.hostname.toLowerCase()
	const allowed = host === 'commons.wikimedia.org'
		|| host === 'www.commons.wikimedia.org'
		|| host === 'commons.m.wikimedia.org'
	if (!allowed) return null
	const parts = parsed.pathname.split('/').filter(Boolean)
	let rawName = null
	if (parts.length === 2 && parts[0] === 'wiki') {
		let page = parts[1]
		try {
			page = decodeURIComponent(page)
		} catch (error) {
			console.error('Commons file name is not valid percent-encoding', error)
		}
		if (page.toLowerCase().startsWith('file:')) rawName = page.slice(5)
	} else if (parts.length === 2 && parts[0] === 'w' && parts[1] === 'index.php') {
		const title = parsed.searchParams.get('title') || ''
		if (title.toLowerCase().startsWith('file:')) rawName = title.slice(5)
	}
	if (!rawName) return null
	rawName = rawName.trim().replace(/ /g, '_')
	if (!rawName || rawName.length > 240) return null
	if (/[/\u0000?#&]/.test(rawName) || rawName.includes('\\') || rawName.startsWith('.') || rawName.includes('..')) {
		return null
	}
	const extension = rawName.includes('.') ? rawName.split('.').pop().toLowerCase() : ''
	if (!COMMONS_VIDEO_EXTENSIONS.has(extension)) return null
	return rawName
}

function commonsEmbedUrl (fileName) {
	return `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(fileName)}?embedplayer=yes`
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
	const commonsFile = commonsFileName(parsed)
	if (commonsFile) return commonsEmbedUrl(commonsFile)
	return ''
}
