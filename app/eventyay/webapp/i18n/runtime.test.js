import test from 'node:test'
import assert from 'node:assert/strict'
import {importFromApp} from './app-deps.js'
import {createGettextRuntime} from './runtime.js'
import {usableTranslations} from './catalog.js'
import {createTranslate, subscribeLocale} from './locale.js'

const {default: i18next} = await importFromApp('i18next')

function runtimeFor(domain, catalogs, options = {}) {
	const localeLoaders = Object.fromEntries(
		Object.entries(catalogs).map(([lang, catalog]) => [
			`/locale/${lang}/LC_MESSAGES/${domain}.po`,
			async () => ({default: catalog}),
		])
	)
	return createGettextRuntime({
		domain,
		i18next: i18next.createInstance(),
		localeLoaders,
		warnOnMissing: false,
		...options,
	})
}

test('video English-as-msgid keys fall back to English and keep German overlays', async () => {
	const runtime = runtimeFor('video', {
		en: {
			Schedule: 'Schedule',
			Save: 'Save',
			"{{name}}'s screen": "{{name}}'s screen",
		},
		de: {
			Schedule: 'Zeitplan',
			Save: '',
		},
		hi: {
			Schedule: '',
			Save: 'Save',
		},
	})
	await runtime.init({lng: 'hi'})
	assert.equal(runtime.translate('Schedule'), 'Schedule')
	assert.equal(runtime.translate('Save'), 'Save')

	await runtime.changeLanguage('de')
	assert.equal(runtime.translate('Schedule'), 'Zeitplan')
	assert.equal(runtime.translate('Save'), 'Save')

	await runtime.changeLanguage('en-gb')
	assert.equal(runtime.translate('Schedule'), 'Schedule')
	assert.equal(runtime.translate("{{name}}'s screen", {name: 'Ada'}), "Ada's screen")
})

test('schedule English-as-msgid keys stay English when a locale is empty', async () => {
	const runtime = runtimeFor('schedule', {
		en: {
			Search: 'Search',
			min: 'min',
			'No {{name}} available': 'No {{name}} available',
		},
		hi: {
			Search: '',
			min: 'min',
		},
	})
	await runtime.init({lng: 'hi'})
	assert.equal(runtime.translate('Search'), 'Search')
	assert.equal(runtime.translate('min'), 'min')
	assert.equal(runtime.translate('No {{name}} available', {name: 'rooms'}), 'No rooms available')
})

test('schedule-editor keys fall back the same way as schedule', async () => {
	const runtime = runtimeFor('schedule-editor', {
		en: {
			Save: 'Save',
			'Hidden rooms': 'Hidden rooms',
			'Assign Members for {{title}}': 'Assign Members for {{title}}',
		},
		de: {
			Save: 'Speichern',
			'Hidden rooms': '',
		},
	})
	await runtime.init({lng: 'de'})
	assert.equal(runtime.translate('Save'), 'Speichern')
	assert.equal(runtime.translate('Hidden rooms'), 'Hidden rooms')
	assert.equal(runtime.translate('Assign Members for {{title}}', {title: 'Keynote'}), 'Assign Members for Keynote')
})

test('missing catalogs and loader errors fall back to English', async () => {
	const runtime = runtimeFor('schedule', {
		en: {Search: 'Search', Save: 'Save'},
	})
	const warnings = []
	const originalWarn = console.warn
	const originalError = console.error
	console.warn = (...args) => warnings.push(args.join(' '))
	console.error = () => {}
	try {
		const missing = createGettextRuntime({
			domain: 'schedule',
			i18next: i18next.createInstance(),
			localeLoaders: {
				'/locale/en/LC_MESSAGES/schedule.po': async () => ({default: {Search: 'Search'}}),
				'/locale/de/LC_MESSAGES/schedule.po': async () => {
					throw new Error('catalog exploded')
				},
			},
			warnOnMissing: true,
		})
		await missing.init({lng: 'hi'})
		assert.equal(missing.translate('Search'), 'Search')
		assert.ok(warnings.some((line) => line.includes('schedule') && line.includes('hi')))

		await missing.changeLanguage('de')
		assert.equal(missing.translate('Search'), 'Search')
		assert.equal(missing.i18n.language, 'en')
	} finally {
		console.warn = originalWarn
		console.error = originalError
	}
})

test('Vue plugin exposes the same translate helper for all apps', async () => {
	const runtime = runtimeFor('video', {
		en: {Save: 'Save'},
	})
	await runtime.init({lng: 'en'})
	const app = {config: {globalProperties: {}}}
	runtime.install(app)
	assert.equal(app.config.globalProperties.$t('Save'), 'Save')
	assert.equal(app.config.globalProperties.$localize({en: 'Hello', de: 'Hallo'}), 'Hello')
	assert.equal(app.config.globalProperties.$i18n, runtime.i18n)
})

test('usableTranslations output is what i18next receives for non-English catalogs', () => {
	const german = usableTranslations({
		Save: 'Save',
		Cancel: 'Abbrechen',
		Empty: '',
	}, 'de')
	assert.deepEqual(german, {Cancel: 'Abbrechen'})
})

test('language changes notify subscribers used by the Vue runtime', async () => {
	const seen = []
	const stop = subscribeLocale((revision) => seen.push(revision))
	const runtime = runtimeFor('schedule', {en: {Search: 'Search'}})
	await runtime.init({lng: 'en'})
	await runtime.changeLanguage('en-gb')
	assert.ok(seen.length >= 2)
	stop()
})

test('raw PO loaders populate bilingual video strings', async () => {
	const runtime = createGettextRuntime({
		domain: 'video',
		i18next: i18next.createInstance(),
		localeLoaders: {
			'/locale/en/LC_MESSAGES/video.po': async () => (
				'msgid "Schedule"\nmsgstr ""\n'
			),
		},
		warnOnMissing: false,
	})
	await runtime.init({lng: 'en'})
	assert.equal(runtime.translate('Schedule'), 'Schedule')
})

test('translate keeps strings with colons even when i18next would split namespaces', async () => {
	const i18n = i18next.createInstance()
	await i18n.init({
		lng: 'en',
		resources: {
			en: {
				translation: {
					'Admin:mode:start': 'Admin mode',
				},
			},
		},
	})
	assert.notEqual(i18n.t('Admin:mode:start'), 'Admin mode')
	const translate = createTranslate(i18n)
	assert.equal(translate('Admin:mode:start'), 'Admin mode')
})

test('missing locale loaders warn instead of throwing', async () => {
	const warnings = []
	const originalWarn = console.warn
	console.warn = (...args) => warnings.push(args.join(' '))
	try {
		const runtime = createGettextRuntime({
			domain: 'video',
			i18next: i18next.createInstance(),
			localeLoaders: {},
			warnOnMissing: true,
		})
		await runtime.init({lng: 'en'})
		assert.ok(warnings.some((line) => line.includes('video') && line.includes('locale loaders')))
		assert.equal(runtime.translate('Schedule'), 'Schedule')
	} finally {
		console.warn = originalWarn
	}
})
