import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeDisplayResources } from './displayResources.js'

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
