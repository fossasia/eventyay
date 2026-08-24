/**
 * Real English catalogs for video, schedule, and schedule-editor must load
 * through the shared fallback helpers.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import {importFromApp} from './app-deps.js'
import {mergeCatalogWithEnglish, usableTranslations} from './catalog.js'
import {createGettextRuntime} from './runtime.js'
import {parsePo} from './po.js'

const {default: i18next} = await importFromApp('i18next')

const localeRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../locale')

function readEnglish(domain) {
	return parsePo(readFileSync(path.join(localeRoot, 'en', 'LC_MESSAGES', `${domain}.po`), 'utf8'))
}

const DOMAINS = [
	{
		domain: 'video',
		sampleKey: 'RoomsSidebar:schedule:label',
		sampleValue: 'Schedule',
		namespaced: true,
	},
	{
		domain: 'schedule',
		sampleKey: 'Search',
		sampleValue: 'Search',
		namespaced: false,
	},
	{
		domain: 'schedule-editor',
		sampleKey: 'Save',
		sampleValue: 'Save',
		namespaced: false,
	},
]

for (const {domain, sampleKey, sampleValue, namespaced} of DOMAINS) {
	test(`${domain}.po English catalog is usable and Hindi falls back to it`, async () => {
		const english = readEnglish(domain)
		assert.ok(english[sampleKey], `${domain} is missing ${sampleKey}`)
		assert.equal(english[sampleKey], sampleValue)
		const hindi = mergeCatalogWithEnglish(english, {[sampleKey]: '', Save: ''}, 'hi')
		assert.equal(hindi[sampleKey], usableTranslations(english, 'en')[sampleKey])

		if (namespaced) {
			for (const key of Object.keys(usableTranslations(english, 'en'))) {
				if (!key.includes(':') || key.includes(' ')) continue
				assert.notEqual(english[key], key, `${domain} still stores raw key ${key}`)
				assert.equal(hindi[key], english[key], `Hindi should fall back to English for ${key}`)
			}
		}

		const runtime = createGettextRuntime({
			domain,
			i18next: i18next.createInstance(),
			localeLoaders: {
				[`/locale/en/LC_MESSAGES/${domain}.po`]: async () => ({default: english}),
			},
			warnOnMissing: false,
		})
		await runtime.init({lng: 'hi'})
		assert.equal(runtime.translate(sampleKey), sampleValue)
		assert.notEqual(runtime.translate(sampleKey), '')
		if (domain === 'video') {
			assert.equal(
				english['Click "Add Stream Schedule" to create one.'],
				'Click "Add Stream Schedule" to create one.'
			)
		}
	})
}

test('video German overlay keeps Zeitplan while empty keys stay English', async () => {
	const english = readEnglish('video')
	const german = mergeCatalogWithEnglish(english, {
		'RoomsSidebar:schedule:label': 'Zeitplan',
		Save: '',
	}, 'de')
	assert.equal(german['RoomsSidebar:schedule:label'], 'Zeitplan')
	assert.equal(german.Save || english.Save, english.Save)
})
