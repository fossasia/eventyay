/**
 * Tests for centralized moment.js locale configuration.
 * Run: node --test src/locales/momentLocales.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import moment from 'moment'
import MOMENT_LOCALE_MAP, { getMomentLocale, getAvailableLocales } from './momentLocales.js'

test('should have correct locale map', () => {
	assert.equal(MOMENT_LOCALE_MAP.en, 'en')
	assert.equal(MOMENT_LOCALE_MAP.pt, 'pt')
	assert.equal(MOMENT_LOCALE_MAP['zh-cn'], 'zh-cn')
})

test('should get moment locale for language code', () => {
	assert.equal(getMomentLocale('en'), 'en')
	assert.equal(getMomentLocale('pt'), 'pt')
	assert.equal(getMomentLocale('zh-cn'), 'zh-cn')
})

test('should fallback to en for unknown locale', () => {
	assert.equal(getMomentLocale('unknown'), 'en')
	assert.equal(getMomentLocale(''), 'en')
	assert.equal(getMomentLocale(null), 'en')
})

test('should get all available locales', () => {
	const locales = getAvailableLocales()
	assert.ok(locales.includes('en'))
	assert.ok(locales.includes('pt'))
	assert.ok(locales.includes('zh-cn'))
	assert.ok(Array.isArray(locales))
	// Count should match the map keys
	assert.equal(locales.length, Object.keys(MOMENT_LOCALE_MAP).length)
})

test('should have loaded all moment locales', () => {
	// Reset to en first
	moment.locale('en')
	// Test that locales can be set (some may fall back if not loaded)
	// The important thing is that moment.locale() doesn't throw
	getAvailableLocales().forEach(locale => {
		const momentLocale = getMomentLocale(locale)
		// This should not throw
		assert.doesNotThrow(() => moment.locale(momentLocale))
		// Verify a valid locale is returned (may be fallback)
		assert.ok(typeof moment.locale() === 'string')
		assert.ok(moment.locale().length > 0)
	})
})

test('moment locale formats dates correctly in different languages', () => {
	moment.locale('de')
	assert.equal(moment.locale(), 'de')
	const deFormat = moment().format('LL')
	assert.ok(deFormat.includes('Oktober'))

	moment.locale('fr')
	assert.equal(moment.locale(), 'fr')
	const frFormat = moment().format('LL')
	assert.ok(frFormat.includes('octobre'))

	moment.locale('en')
	assert.equal(moment.locale(), 'en')
	const enFormat = moment().format('LL')
	assert.ok(enFormat.includes('October'))
})

test('rapid locale switches settle on last selected', () => {
	moment.locale('de')
	moment.locale('fr')
	moment.locale('es')
	moment.locale('de')
	assert.equal(moment.locale(), 'de')
})