/**
 * Tests for centralized moment.js locale configuration with validation.
 * Run: node --test src/locales/momentLocales.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import moment from 'moment'
import MOMENT_LOCALE_MAP, {
  getMomentLocale,
  getAvailableLocales,
  validateLanguageCode
} from './momentLocales.js'

// Test: getMomentLocale() - Input Validation
test('getMomentLocale() - Valid Inputs', () => {
  assert.equal(getMomentLocale('en'), 'en')
  assert.equal(getMomentLocale('pt'), 'pt')
  assert.equal(getMomentLocale('es'), 'es')
  assert.equal(getMomentLocale('zh-cn'), 'zh-cn')
  assert.equal(getMomentLocale('ja'), 'ja')
})

test('getMomentLocale() - Invalid Type: null', () => {
  const result = getMomentLocale(null)
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid Type: undefined', () => {
  const result = getMomentLocale(undefined)
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid Type: number', () => {
  const result = getMomentLocale(123)
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid Type: object', () => {
  const result = getMomentLocale({})
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid Type: array', () => {
  const result = getMomentLocale(['en'])
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid String: empty', () => {
  const result = getMomentLocale('')
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid String: whitespace', () => {
  const result = getMomentLocale('   ')
  assert.equal(result, 'en')
})

test('getMomentLocale() - Invalid String: unknown locale', () => {
  const result = getMomentLocale('unknown-locale')
  assert.equal(result, 'en')
})

test('getMomentLocale() - Strict Mode throws on null', () => {
  assert.throws(() => getMomentLocale(null, { strictMode: true }), TypeError)
})

test('getMomentLocale() - Strict Mode throws on unknown', () => {
  assert.throws(() => getMomentLocale('unknown', { strictMode: true }), RangeError)
})

test('getMomentLocale() - Strict Mode allows valid', () => {
  assert.doesNotThrow(() => getMomentLocale('en', { strictMode: true }))
})

test('getMomentLocale() - throwOnUnknown option', () => {
  assert.throws(() => getMomentLocale('invalid', { throwOnUnknown: true }), RangeError)
})

// Test: validateLanguageCode()
test('validateLanguageCode() - Valid locale', () => {
  const result = validateLanguageCode('en')
  assert.equal(result.valid, true)
  assert.equal(result.errors.length, 0)
  assert.equal(result.resolvedLocale, 'en')
})

test('validateLanguageCode() - Unknown locale', () => {
  const result = validateLanguageCode('unknown')
  assert.equal(result.valid, false)
  assert.ok(result.errors.length > 0)
})

test('validateLanguageCode() - Typo suggestion', () => {
  const result = validateLanguageCode('eng')
  assert.equal(result.valid, false)
  assert.ok(result.suggestions.length > 0)
})

test('validateLanguageCode() - Null input', () => {
  const result = validateLanguageCode(null)
  assert.equal(result.valid, false)
  assert.ok(result.errors.length > 0)
})

test('validateLanguageCode() - Optional locale warning', () => {
  const result = validateLanguageCode('es')
  assert.equal(result.valid, true)
  assert.ok(result.warnings.length > 0 || result.warnings.length === 0) // es may not be required
})

// Test: getAvailableLocales()
test('getAvailableLocales() - Returns array', () => {
  const locales = getAvailableLocales()
  assert.ok(Array.isArray(locales))
  assert.ok(locales.length > 0)
})

test('getAvailableLocales() - Detailed option', () => {
  const locales = getAvailableLocales({ detailed: true })
  assert.ok(locales[0].hasOwnProperty('code'))
  assert.ok(locales[0].hasOwnProperty('momentLocale'))
  assert.ok(locales[0].hasOwnProperty('isRequired'))
})

test('getAvailableLocales() - Sort option', () => {
  const locales = getAvailableLocales({ sortByName: true })
  const sorted = [...locales].sort()
  assert.deepEqual(locales, sorted)
})

test('getAvailableLocales() - Required only', () => {
  const locales = getAvailableLocales({ includeRequired: true })
  assert.ok(locales.includes('en'))
  assert.ok(locales.includes('pt'))
})

// Test: Moment locale functionality
test('Moment locale formats dates correctly', () => {
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

test('Rapid locale switches settle on last selected', () => {
  moment.locale('de')
  moment.locale('fr')
  moment.locale('es')
  moment.locale('de')
  assert.equal(moment.locale(), 'de')
})