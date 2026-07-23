/**
 * Lightweight parity checks for getVideoEmbedUrl (timestamps + autoplay off).
 * Run: node --test src/videoEmbed.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { getVideoEmbedUrl } from './videoEmbed.js'

function assertYoutubeEmbed (embedUrl, videoId, start = null) {
	const parsed = new URL(embedUrl)
	assert.equal(parsed.origin, 'https://www.youtube-nocookie.com')
	assert.equal(parsed.pathname, `/embed/${videoId}`)
	assert.equal(parsed.searchParams.get('autoplay'), '0')
	if (start == null) {
		assert.equal(parsed.searchParams.get('start'), null)
	} else {
		assert.equal(parsed.searchParams.get('start'), String(start))
	}
}

function assertVimeoEmbed (embedUrl, videoId, timeHash = null) {
	const parsed = new URL(embedUrl)
	assert.equal(parsed.origin, 'https://player.vimeo.com')
	assert.equal(parsed.pathname, `/video/${videoId}`)
	assert.equal(parsed.searchParams.get('autoplay'), '0')
	assert.equal(parsed.hash, timeHash ? `#${timeHash}` : '')
}

test('youtube embeds preserve timestamps and disable autoplay', () => {
	assertYoutubeEmbed(getVideoEmbedUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ'), 'dQw4w9WgXcQ')
	assertYoutubeEmbed(getVideoEmbedUrl('https://youtu.be/dQw4w9WgXcQ?t=45'), 'dQw4w9WgXcQ', 45)
	assertYoutubeEmbed(getVideoEmbedUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=1m30s'), 'dQw4w9WgXcQ', 90)
	assertYoutubeEmbed(getVideoEmbedUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ&start=125'), 'dQw4w9WgXcQ', 125)
	assertYoutubeEmbed(getVideoEmbedUrl('https://www.youtube.com/watch?v=dQw4w9WgXcQ#t=30'), 'dQw4w9WgXcQ', 30)
	assertYoutubeEmbed(getVideoEmbedUrl('https://youtu.be/dQw4w9WgXcQ?t=1h2m3s'), 'dQw4w9WgXcQ', 3723)
	assertYoutubeEmbed(getVideoEmbedUrl('https://www.youtube.com/shorts/dQw4w9WgXcQ?t=12'), 'dQw4w9WgXcQ', 12)
})

test('vimeo embeds preserve timestamps and disable autoplay', () => {
	assertVimeoEmbed(getVideoEmbedUrl('https://vimeo.com/123456789'), '123456789')
	assertVimeoEmbed(getVideoEmbedUrl('https://vimeo.com/123456789#t=1m30s'), '123456789', 't=1m30s')
	assertVimeoEmbed(getVideoEmbedUrl('https://vimeo.com/123456789?t=75'), '123456789', 't=75s')
	assertVimeoEmbed(getVideoEmbedUrl('https://player.vimeo.com/video/123456789#t=10s'), '123456789', 't=10s')
})

test('non-video urls are not embedded', () => {
	assert.equal(getVideoEmbedUrl('https://example.com/watch?v=abc'), '')
	assert.equal(getVideoEmbedUrl('https://www.youtube.com/watch?v='), '')
	assert.equal(getVideoEmbedUrl('not-a-url'), '')
})
