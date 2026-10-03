/**
 * Organizer-side language stream entries (room editor).
 * Run: node --test src/lib/interpretation-language-streams.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {
	cloneLanguageStreamEntries,
	defaultLanguageStreamEntry,
	normalizeLanguageStreamEntry,
	serializeLanguageStreamEntry,
} from './interpretation-language-streams.js'

const WHEP = 'https://voxbento.example/demo-12-es/whep'

test('new and legacy entries are human streams', () => {
	assert.equal(defaultLanguageStreamEntry().stream_type, 'human')
	const [legacy] = cloneLanguageStreamEntries([{ language: 'Spanish', youtube_id: WHEP }])
	assert.equal(legacy.stream_type, 'human')
	assert.equal(legacy.url, WHEP)
})

test('an AI entry drops its source and video flag', () => {
	const entry = { language: 'German', stream_type: 'ai', url: WHEP, youtube_id: WHEP, use_video: true }
	normalizeLanguageStreamEntry(entry)
	assert.deepEqual(entry, { language: 'German', stream_type: 'ai', url: '', youtube_id: '', use_video: false })

	const saved = serializeLanguageStreamEntry({ language: 'French', stream_type: 'ai', url: WHEP, use_video: true })
	assert.deepEqual(saved, { language: 'French', stream_type: 'ai', url: '', youtube_id: '', use_video: false })
})

test('switching an entry back to human keeps it editable', () => {
	const entry = { language: 'German', stream_type: 'ai', url: '', youtube_id: '' }
	normalizeLanguageStreamEntry(entry)
	entry.stream_type = 'human'
	entry.url = WHEP
	normalizeLanguageStreamEntry(entry)
	assert.equal(entry.youtube_id, WHEP)
	assert.equal(serializeLanguageStreamEntry(entry).youtube_id, WHEP)
})
