import { test } from 'node:test'
import assert from 'node:assert/strict'
import moment from 'moment'
import {
	loadMomentLocale,
	isMomentLocaleLoaded,
	getLoadedMomentLocales,
	getMomentLocaleLoadStats,
	preloadMomentLocales,
	resetMomentLocaleLoader,
	MOMENT_LOCALE_LOADERS
} from './lazyLoader.js'

test('en is preloaded (bundled with moment core)', () => {
	assert.equal(isMomentLocaleLoaded('en'), true)
})

test('loadMomentLocale loads a locale on demand', async () => {
	resetMomentLocaleLoader()
	assert.equal(isMomentLocaleLoaded('de'), false)

	const result = await loadMomentLocale('de')

	assert.equal(result.success, true)
	assert.equal(result.cached, false)
	assert.equal(result.locale, 'de')
	assert.equal(isMomentLocaleLoaded('de'), true)
	// the locale must register with the shared moment instance
	assert.ok(moment.locales().includes('de'))
})

test('loadMomentLocale makes moment.locale() work for the locale', async () => {
	resetMomentLocaleLoader()
	await loadMomentLocale('fr')

	assert.equal(moment.locale('fr'), 'fr')
})

test('loadMomentLocale returns cached result on second load', async () => {
	resetMomentLocaleLoader()
	await loadMomentLocale('pt')

	const result = await loadMomentLocale('pt')

	assert.equal(result.success, true)
	assert.equal(result.cached, true)
})

test('concurrent loads of the same locale are deduplicated', async () => {
	resetMomentLocaleLoader()

	const results = await Promise.all([
		loadMomentLocale('es'),
		loadMomentLocale('es'),
		loadMomentLocale('es')
	])

	assert.ok(results.every(result => result.success === true))
	assert.equal(getLoadedMomentLocales().filter(locale => locale === 'es').length, 1)
})

test('loadMomentLocale rejects unknown locales', async () => {
	resetMomentLocaleLoader()

	const result = await loadMomentLocale('xx-yy')

	assert.equal(result.success, false)
	assert.ok(result.error)
})

test('loadMomentLocale rejects invalid input', async () => {
	resetMomentLocaleLoader()

	const result = await loadMomentLocale(null)

	assert.equal(result.success, false)
	assert.ok(result.error)
})

test('preloadMomentLocales loads multiple locales in parallel', async () => {
	resetMomentLocaleLoader()

	const results = await preloadMomentLocales(['it', 'tr', 'ko'])

	assert.equal(results.length, 3)
	assert.ok(results.every(result => result.success === true))
	assert.equal(isMomentLocaleLoaded('it'), true)
	assert.equal(isMomentLocaleLoaded('tr'), true)
	assert.equal(isMomentLocaleLoaded('ko'), true)
})

test('getMomentLocaleLoadStats reports loading state', async () => {
	resetMomentLocaleLoader()
	await loadMomentLocale('ja')

	const stats = getMomentLocaleLoadStats()

	assert.equal(stats.loadedCount, 2) // en + ja
	assert.equal(stats.availableCount, Object.keys(MOMENT_LOCALE_LOADERS).length + 1)
	assert.ok(stats.loadedLocales.includes('en'))
	assert.ok(stats.loadedLocales.includes('ja'))
})

test('resetMomentLocaleLoader clears loaded state', async () => {
	resetMomentLocaleLoader()
	await loadMomentLocale('ru')
	assert.equal(isMomentLocaleLoaded('ru'), true)

	resetMomentLocaleLoader()

	assert.equal(isMomentLocaleLoaded('ru'), false)
	assert.deepEqual(getLoadedMomentLocales(), ['en'])
})

test('loader map covers every locale the schedule supports', () => {
	const expected = [
		'de', 'fr', 'es', 'ar', 'zh-cn', 'zh-tw', 'pt', 'ja', 'ko', 'nl',
		'nb', 'nn', 'it', 'ru', 'pl', 'sv', 'da', 'fi', 'tr', 'he',
		'th', 'vi', 'id', 'ms', 'et', 'lt', 'lv', 'sl', 'sk', 'hu',
		'cs', 'el', 'ro', 'bg', 'hr', 'sr', 'mk', 'sq', 'mt', 'is',
		'fa', 'ur', 'ps', 'ku', 'bn', 'gu', 'mr', 'ta', 'te', 'ml', 'kn'
	]

	assert.deepEqual([...Object.keys(MOMENT_LOCALE_LOADERS)].sort(), [...expected].sort())
})

test('loader map keys are lowercase locale codes', () => {
	for (const key of Object.keys(MOMENT_LOCALE_LOADERS)) {
		assert.equal(key, key.toLowerCase())
	}
})
