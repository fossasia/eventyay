/**
 * Schedule catalog fallback: empty locales must use English, never raw keys.
 * Run: node --test src/i18n-catalog.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import i18next from 'i18next'
import {mergeCatalogWithEnglish, usableTranslations} from '../../i18n/catalog.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const enPoPath = path.resolve(here, '../../../locale/en/LC_MESSAGES/schedule.po')

function parsePo(content) {
	const entries = []
	const parts = content.split(/\nmsgid /)
	for (const part of parts.slice(1)) {
		const lines = part.split('\n')
		let mode = 'id'
		const idChunks = []
		const strChunks = []
		const first = lines[0]
		const firstMatch = first.match(/^"(.*)"$/)
		if (firstMatch) idChunks.push(firstMatch[1])
		for (const line of lines.slice(1)) {
			if (line.startsWith('msgstr ')) {
				mode = 'str'
				const match = line.match(/^msgstr "(.*)"$/)
				if (match) strChunks.push(match[1])
				continue
			}
			if (line.startsWith('"')) {
				const chunk = line.endsWith('"') ? line.slice(1, -1) : line.slice(1)
				if (mode === 'id') idChunks.push(chunk)
				else strChunks.push(chunk)
			} else if (mode === 'str') {
				break
			}
		}
		const msgid = idChunks.join('')
		if (msgid) entries.push([msgid, strChunks.join('')])
	}
	return Object.fromEntries(entries)
}

test('English schedule.po strings are usable and Hindi falls back to them', async () => {
	const english = parsePo(readFileSync(enPoPath, 'utf8'))
	assert.ok(english.Search || english.search || english['Search sessions…'] || Object.keys(english).length > 10)
	const sampleKey = english.Search ? 'Search' : Object.keys(english).find((key) => english[key] && english[key] !== key)
	assert.ok(sampleKey)
	const hindi = mergeCatalogWithEnglish(english, {Search: ''}, 'hi')
	assert.equal(hindi[sampleKey], usableTranslations(english, 'en')[sampleKey])
	await i18next.init({
		lng: 'hi',
		fallbackLng: 'en',
		resources: {
			en: {translation: usableTranslations(english, 'en')},
			hi: {translation: hindi},
		},
		keySeparator: false,
		nsSeparator: false,
		returnEmptyString: false,
	})
	assert.equal(i18next.t(sampleKey), usableTranslations(english, 'en')[sampleKey])
	assert.equal(i18next.t('No schedule has been published yet. Please check back later.'), 'No schedule has been published yet. Please check back later.')
})
