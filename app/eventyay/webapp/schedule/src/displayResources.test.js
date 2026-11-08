import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeDisplayResources, resolveAbsoluteUrl } from './displayResources.js'

test('normalizeDisplayResources handles empty or invalid inputs', () => {
	assert.deepEqual(normalizeDisplayResources(), [])
	assert.deepEqual(normalizeDisplayResources(null), [])
	assert.deepEqual(normalizeDisplayResources('not-an-array'), [])
	assert.deepEqual(normalizeDisplayResources([]), [])
})

test('normalizeDisplayResources appends #resource to file resources ending in .pdf', () => {
	const resources = [
		{ id: 1, description: 'Slides', resource: 'https://example.com/slides.pdf' },
	]
	const result = normalizeDisplayResources(resources)
	assert.equal(result[0].resource, 'https://example.com/slides.pdf#resource')
	assert.equal(result[0].link, undefined)
	assert.equal(result[0].description, 'Slides')
})

test('normalizeDisplayResources appends #resource to link resources ending in .pdf', () => {
	const resources = [
		{ id: 2, description: 'Paper PDF', link: 'https://example.com/paper.pdf' },
	]
	const result = normalizeDisplayResources(resources)
	assert.equal(result[0].link, 'https://example.com/paper.pdf#resource')
	assert.equal(result[0].resource, undefined)
	assert.equal(result[0].description, 'Paper PDF')
})

test('normalizeDisplayResources handles PDF URLs with query parameters or query string', () => {
	const resources = [
		{ id: 3, description: 'Signed PDF', resource: 'https://example.com/doc.pdf?token=xyz&v=2' },
		{ id: 4, description: 'Link PDF with query', link: 'https://cdn.example.com/slides.pdf?auth=abc' },
	]
	const result = normalizeDisplayResources(resources)
	assert.equal(result[0].resource, 'https://example.com/doc.pdf?token=xyz&v=2#resource')
	assert.equal(result[1].link, 'https://cdn.example.com/slides.pdf?auth=abc#resource')
})

test('normalizeDisplayResources does not add redundant hash if # is already present', () => {
	const resources = [
		{ id: 5, description: 'Pre-hashed PDF', resource: 'https://example.com/slides.pdf#resource' },
		{ id: 6, description: 'Page-linked PDF', link: 'https://example.com/doc.pdf#page=4' },
	]
	const result = normalizeDisplayResources(resources)
	assert.equal(result[0].resource, 'https://example.com/slides.pdf#resource')
	assert.equal(result[1].link, 'https://example.com/doc.pdf#page=4')
})

test('normalizeDisplayResources leaves non-PDF resources untouched', () => {
	const resources = [
		{ id: 7, description: 'Project Repo', link: 'https://github.com/fossasia/eventyay' },
		{ id: 8, description: 'Document', resource: 'https://example.com/notes.docx' },
		{ id: 9, description: 'Audio', resource: 'https://example.com/podcast.mp3' },
	]
	const result = normalizeDisplayResources(resources)
	assert.equal(result[0].link, 'https://github.com/fossasia/eventyay')
	assert.equal(result[0].resource, undefined)
	assert.equal(result[1].resource, 'https://example.com/notes.docx')
	assert.equal(result[2].resource, 'https://example.com/podcast.mp3')
})

test('resolveAbsoluteUrl leaves absolute URLs unchanged', () => {
	assert.equal(resolveAbsoluteUrl('https://example.com/slides.pdf', 'https://eventyay.com/demo/'), 'https://example.com/slides.pdf')
	assert.equal(resolveAbsoluteUrl('http://example.com/doc.pdf', 'https://eventyay.com/demo/'), 'http://example.com/doc.pdf')
	assert.equal(resolveAbsoluteUrl('ftp://ftp.example.com/slides.pdf', 'https://eventyay.com/demo/'), 'ftp://ftp.example.com/slides.pdf')
	assert.equal(resolveAbsoluteUrl('sftp://files.example.com/data.tar.gz', 'https://eventyay.com/demo/'), 'sftp://files.example.com/data.tar.gz')
	assert.equal(resolveAbsoluteUrl('', 'https://eventyay.com/demo/'), '')
	assert.equal(resolveAbsoluteUrl(null, 'https://eventyay.com/demo/'), null)
})

test('resolveAbsoluteUrl resolves path-relative URLs against subpath eventUrl', () => {
	assert.equal(
		resolveAbsoluteUrl('uploads/slides.pdf', 'https://eventyay.com/democon/'),
		'https://eventyay.com/democon/uploads/slides.pdf'
	)
	assert.equal(
		resolveAbsoluteUrl('uploads/slides.pdf', 'https://eventyay.com/democon'),
		'https://eventyay.com/democon/uploads/slides.pdf'
	)
	assert.equal(
		resolveAbsoluteUrl('files/presentation.pptx', 'https://eventyay.com/e/my-event/'),
		'https://eventyay.com/e/my-event/files/presentation.pptx'
	)
	assert.equal(
		resolveAbsoluteUrl('uploads/slides.pdf', 'https://eventyay.com/democon?preview=1'),
		'https://eventyay.com/democon/uploads/slides.pdf'
	)
})

test('resolveAbsoluteUrl resolves root-relative URLs against origin', () => {
	assert.equal(
		resolveAbsoluteUrl('/media/uploads/slides.pdf', 'https://eventyay.com/democon/'),
		'https://eventyay.com/media/uploads/slides.pdf'
	)
	assert.equal(
		resolveAbsoluteUrl('/static/doc.pdf', 'https://custom.domain.org/nested/path/'),
		'https://custom.domain.org/static/doc.pdf'
	)
})
