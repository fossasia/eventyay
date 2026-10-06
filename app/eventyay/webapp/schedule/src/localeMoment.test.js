/**
 * Tests for moment.js locale loading in schedule app.
 * Run: node --test src/localeMoment.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'

function normalizeLocaleCode (code) {
	if (!code) return ''
	return code.toString().trim().toLowerCase().replace(/_/g, '-')
}

function localePrimary (code) {
	const normalized = normalizeLocaleCode(code)
	return normalized.split('-')[0] || normalized
}

function localeToMoment (code) {
	if (!code) return 'en'
	const normalized = normalizeLocaleCode(code)
	const map = {
		'zh-hans': 'zh-cn',
		'zh-hant': 'zh-tw',
		'pt-pt': 'pt',
		'nn-no': 'nn',
		'nb-no': 'nb',
		'de-formal': 'de',
		'de-informal': 'de',
		'nl-informal': 'nl',
	}
	return map[normalized] || normalized
}

test('localeToMoment maps Django codes to moment codes', () => {
	assert.equal(localeToMoment('de'), 'de')
	assert.equal(localeToMoment('ar'), 'ar')
	assert.equal(localeToMoment('fr'), 'fr')
	assert.equal(localeToMoment('es'), 'es')
	assert.equal(localeToMoment('zh-hans'), 'zh-cn')
	assert.equal(localeToMoment('zh-hant'), 'zh-tw')
	assert.equal(localeToMoment('pt-br'), 'pt-br')
	assert.equal(localeToMoment('pt-pt'), 'pt')
	assert.equal(localeToMoment('nb-no'), 'nb')
	assert.equal(localeToMoment('nn-no'), 'nn')
	assert.equal(localeToMoment('de-formal'), 'de')
	assert.equal(localeToMoment('de-informal'), 'de')
	assert.equal(localeToMoment('nl-informal'), 'nl')
	assert.equal(localeToMoment('zh-Hans'), 'zh-cn')
	assert.equal(localeToMoment('ZH-HANT'), 'zh-tw')
})

test('localeToMoment returns normalized code for unknown locales', () => {
	assert.equal(localeToMoment('xx-yy'), 'xx-yy')
	assert.equal(localeToMoment('unknown'), 'unknown')
})

test('normalizeLocaleCode handles various formats', () => {
	assert.equal(normalizeLocaleCode('de'), 'de')
	assert.equal(normalizeLocaleCode('DE'), 'de')
	assert.equal(normalizeLocaleCode('de_DE'), 'de-de')
	assert.equal(normalizeLocaleCode('de-de'), 'de-de')
	assert.equal(normalizeLocaleCode('  Zh-Hans  '), 'zh-hans')
	assert.equal(normalizeLocaleCode(''), '')
})

test('localePrimary extracts primary language', () => {
	assert.equal(localePrimary('de'), 'de')
	assert.equal(localePrimary('de-de'), 'de')
	assert.equal(localePrimary('zh-hans'), 'zh')
	assert.equal(localePrimary('pt-br'), 'pt')
	assert.equal(localePrimary('en'), 'en')
})

test('moment locale formats dates correctly in different languages', async () => {
	const moment = (await import('moment-timezone')).default
	
	// Test German
	moment.locale('de')
	assert.equal(moment.locale(), 'de')
	const deFormat = moment().format('LL')
	assert.ok(deFormat.includes('Oktober') || deFormat.includes('Oktober'))
	
	// Test Arabic
	moment.locale('ar')
	assert.equal(moment.locale(), 'ar')
	const arFormat = moment().format('LL')
	assert.ok(arFormat.includes('أكتوبر') || arFormat.includes('أكتوبر'))
	
	// Test French
	moment.locale('fr')
	assert.equal(moment.locale(), 'fr')
	const frFormat = moment().format('LL')
	assert.ok(frFormat.includes('octobre'))
	
	// Test Spanish
	moment.locale('es')
	assert.equal(moment.locale(), 'es')
	const esFormat = moment().format('LL')
	assert.ok(esFormat.includes('octubre'))
	
	// Test Portuguese (Brazil)
	moment.locale('pt-br')
	assert.equal(moment.locale(), 'pt-br')
	const ptbrFormat = moment().format('LL')
	assert.ok(ptbrFormat.includes('outubro'))
	
	// Test Chinese (Simplified)
	moment.locale('zh-cn')
	assert.equal(moment.locale(), 'zh-cn')
	const zhcnFormat = moment().format('LL')
	assert.ok(zhcnFormat.includes('10月') || zhcnFormat.includes('10月'))
	
	// Test Chinese (Traditional)
	moment.locale('zh-tw')
	assert.equal(moment.locale(), 'zh-tw')
	const zhtwFormat = moment().format('LL')
	assert.ok(zhtwFormat.includes('10月') || zhtwFormat.includes('10月'))
	
	// Test Japanese
	moment.locale('ja')
	assert.equal(moment.locale(), 'ja')
	const jaFormat = moment().format('LL')
	assert.ok(jaFormat.includes('10月') || jaFormat.includes('10月'))
	
	// Test Korean
	moment.locale('ko')
	assert.equal(moment.locale(), 'ko')
	const koFormat = moment().format('LL')
	assert.ok(koFormat.includes('10월') || koFormat.includes('10월'))
	
	// Reset to English
	moment.locale('en')
	assert.equal(moment.locale(), 'en')
	const enFormat = moment().format('LL')
	assert.ok(enFormat.includes('October'))
})

test('moment locale fallback for unsupported code', async () => {
	const moment = (await import('moment-timezone')).default
	
	// moment-timezone with data falls back to English for unknown locales
	moment.locale('unsupported-code-xyz')
	// Should not throw, and locale should be set (may fall back to en)
	assert.ok(moment.locale())
	assert.ok(moment().format('LL'))
})

test('rapid locale switches settle on last selected', async () => {
	const moment = (await import('moment-timezone')).default
	
	let lastLocale = 'en'
	const switches = [
		() => { moment.locale('de'); lastLocale = 'de' },
		() => { moment.locale('fr'); lastLocale = 'fr' },
		() => { moment.locale('es'); lastLocale = 'es' },
		() => { moment.locale('de'); lastLocale = 'de' },
	]
	
	for (const sw of switches) sw()
	
	assert.equal(moment.locale(), 'de')
	assert.equal(lastLocale, 'de')
})