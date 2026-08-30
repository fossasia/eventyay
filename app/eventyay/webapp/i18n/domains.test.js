/**
 * Real gettext templates for video, schedule, and schedule-editor must load
 * through the shared fallback helpers. English lives in *.pot, not en/*.po.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {existsSync, readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import {importFromApp} from './app-deps.js'
import {mergeCatalogWithEnglish} from './catalog.js'
import {createGettextRuntime} from './runtime.js'
import {parsePo} from './po.js'

const {default: i18next} = await importFromApp('i18next')

const localeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../locale')

function readSourceCatalog(domain) {
	return parsePo(readFileSync(path.join(localeRoot, `${domain}.pot`), 'utf8'))
}

const DOMAINS = [
	{
		domain: 'video',
		sampleKey: 'Schedule',
		translated: {de: 'Zeitplan'},
	},
	{
		domain: 'schedule',
		sampleKey: 'Search',
		translated: {},
	},
	{
		domain: 'schedule-editor',
		sampleKey: 'Save',
		translated: {de: 'Speichern'},
	},
]

test('gettext source language is pot templates, not English po files', () => {
	for (const domain of ['django', 'djangojs', 'video', 'schedule', 'schedule-editor']) {
		assert.ok(existsSync(path.join(localeRoot, `${domain}.pot`)), `${domain}.pot is missing`)
		assert.equal(
			existsSync(path.join(localeRoot, 'en', 'LC_MESSAGES', `${domain}.po`)),
			false,
			`${domain} must not ship locale/en/LC_MESSAGES/${domain}.po next to ${domain}.pot`
		)
	}
})

for (const {domain, sampleKey, translated} of DOMAINS) {
	test(`${domain}.po is bilingual and Hindi falls back to the English msgid`, async () => {
		const english = readSourceCatalog(domain)
		assert.ok(Object.hasOwn(english, sampleKey), `${domain} is missing ${sampleKey}`)
		assert.equal(english[sampleKey], '')
		const hindi = mergeCatalogWithEnglish(english, {[sampleKey]: '', Save: ''}, 'hi')
		assert.equal(hindi[sampleKey], undefined)

		const runtime = createGettextRuntime({
			domain,
			i18next: i18next.createInstance(),
			localeLoaders: {
				[`/locale/en/LC_MESSAGES/${domain}.po`]: async () => ({default: english}),
			},
			warnOnMissing: false,
		})
		await runtime.init({lng: 'hi'})
		assert.equal(runtime.translate(sampleKey), sampleKey)
		assert.notEqual(runtime.translate(sampleKey), '')
		if (domain === 'video') {
			assert.equal(runtime.translate('Click "Add Stream Schedule" to create one.'), 'Click "Add Stream Schedule" to create one.')
		}
		if (translated.de) {
			const german = mergeCatalogWithEnglish(english, {[sampleKey]: translated.de}, 'de')
			assert.equal(german[sampleKey], translated.de)
		}
	})
}

test('video German overlay keeps Zeitplan while empty keys stay English', async () => {
	const english = readSourceCatalog('video')
	const german = mergeCatalogWithEnglish(english, {
		Schedule: 'Zeitplan',
		Save: '',
	}, 'de')
	assert.equal(german.Schedule, 'Zeitplan')
	assert.equal(german.Save, undefined)
	const runtime = createGettextRuntime({
		domain: 'video',
		i18next: i18next.createInstance(),
		localeLoaders: {
			'/locale/en/LC_MESSAGES/video.po': async () => ({default: english}),
			'/locale/de/LC_MESSAGES/video.po': async () => ({default: german}),
		},
		warnOnMissing: false,
	})
	await runtime.init({lng: 'de'})
	assert.equal(runtime.translate('Schedule'), 'Zeitplan')
	assert.equal(runtime.translate('Save'), 'Save')
})

test('gettext templates have unique msgids and no source-language po files', () => {
	const namespacedKey = /^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z]/
	const allowedNamespaced = /^(https?:|Note:)/
	const vueDomains = new Set(['video', 'schedule', 'schedule-editor'])
	for (const domain of ['django', 'djangojs', 'video', 'schedule', 'schedule-editor']) {
		const potText = readFileSync(path.join(localeRoot, `${domain}.pot`), 'utf8')
		const msgids = [...potText.matchAll(/^msgid "(.*)"$/gm)].map((match) => match[1]).filter(Boolean)
		if (vueDomains.has(domain)) {
			assert.equal(msgids.length, new Set(msgids).size, `${domain}.pot has duplicate msgids`)
			const catalog = readSourceCatalog(domain)
			for (const key of Object.keys(catalog)) {
				if (namespacedKey.test(key) && !allowedNamespaced.test(key)) {
					assert.fail(`${domain}.pot still has namespaced msgid ${JSON.stringify(key)}`)
				}
			}
		}
		assert.equal(existsSync(path.join(localeRoot, 'en', 'LC_MESSAGES', `${domain}.po`)), false)
	}
})
