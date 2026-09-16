import test from 'node:test'
import assert from 'node:assert/strict'
import { parseVimeoUrl, getVimeoEmbedUrl } from './vimeo.js'

test('parseVimeoUrl handles various formats', () => {
	// Raw ID
	assert.deepEqual(parseVimeoUrl('123456789'), {
		id: '123456789',
		isLiveEvent: false,
		hash: null,
		originalUrl: '123456789'
	})

	// Standard URL
	assert.deepEqual(parseVimeoUrl('https://vimeo.com/123456789'), {
		id: '123456789',
		isLiveEvent: false,
		hash: null,
		originalUrl: 'https://vimeo.com/123456789'
	})

	// Unlisted URL with hash in path
	assert.deepEqual(parseVimeoUrl('https://vimeo.com/123456789/abcdef12'), {
		id: '123456789',
		isLiveEvent: false,
		hash: 'abcdef12',
		originalUrl: 'https://vimeo.com/123456789/abcdef12'
	})

	// Unlisted URL with hash in query param
	assert.deepEqual(parseVimeoUrl('https://player.vimeo.com/video/123456789?h=abcdef12'), {
		id: '123456789',
		isLiveEvent: false,
		hash: 'abcdef12',
		originalUrl: 'https://player.vimeo.com/video/123456789?h=abcdef12'
	})

	// Live event URL
	assert.deepEqual(parseVimeoUrl('https://vimeo.com/event/987654'), {
		id: '987654',
		isLiveEvent: true,
		hash: null,
		originalUrl: 'https://vimeo.com/event/987654'
	})

	// Non-vimeo URL
	assert.equal(parseVimeoUrl('https://youtube.com/watch?v=123'), null)
	assert.equal(parseVimeoUrl(''), null)
})

test('getVimeoEmbedUrl serializes options correctly', () => {
	// Defaults
	assert.equal(
		getVimeoEmbedUrl('https://vimeo.com/123456789'),
		'https://player.vimeo.com/video/123456789?autoplay=0'
	)

	// Autoplay and muted
	assert.equal(
		getVimeoEmbedUrl('https://vimeo.com/123456789', { autoplay: true, startMuted: true }),
		'https://player.vimeo.com/video/123456789?autoplay=1&muted=1'
	)

	// Loop, hide controls, disable keyboard, DNT
	const fullUrl = getVimeoEmbedUrl('https://vimeo.com/123456789', {
		autoplay: true,
		startMuted: true,
		loop: true,
		hideControls: true,
		disableKb: true,
		dnt: true,
		showInfo: true,
	})
	assert.ok(fullUrl.includes('autoplay=1'))
	assert.ok(fullUrl.includes('muted=1'))
	assert.ok(fullUrl.includes('loop=1'))
	assert.ok(fullUrl.includes('controls=0'))
	assert.ok(fullUrl.includes('keyboard=0'))
	assert.ok(fullUrl.includes('dnt=1'))
	assert.ok(fullUrl.includes('title=0'))
	assert.ok(fullUrl.includes('byline=0'))
	assert.ok(fullUrl.includes('portrait=0'))

	// Password protection
	const passUrl = getVimeoEmbedUrl('https://vimeo.com/123456789', { password: 'secretpass' })
	assert.ok(passUrl.includes('password=secretpass'))

	// Unlisted with hash
	const unlistedUrl = getVimeoEmbedUrl('https://vimeo.com/123456789/hash123')
	assert.ok(unlistedUrl.includes('h=hash123'))

	// Live event
	assert.equal(
		getVimeoEmbedUrl('https://vimeo.com/event/987654', { autoplay: true }),
		'https://vimeo.com/event/987654/embed?autoplay=1'
	)
})
