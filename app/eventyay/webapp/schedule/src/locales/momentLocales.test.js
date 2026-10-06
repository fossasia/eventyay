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
  validateLanguageCode,
  setMomentLocale,
  getLocaleWhitelist,
  isWhitelistedLocale,
  validateWhitelist,
  getLocaleSecurityAudit
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

test('getMomentLocale() - Non-whitelisted locale falls back', () => {
  // da, nb, fi, etc. are in MOMENT_LOCALE_MAP but not in whitelist
  const result = getMomentLocale('da', { checkWhitelist: true })
  assert.equal(result, 'en')
})

test('getMomentLocale() - Whitelisted locale works', () => {
  const result = getMomentLocale('en', { checkWhitelist: true })
  assert.equal(result, 'en')
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

test('validateLanguageCode() - Non-whitelisted locale', () => {
  // da is in MOMENT_LOCALE_MAP but not whitelisted
  const result = validateLanguageCode('da')
  assert.equal(result.valid, false)
  assert.ok(result.errors.some(e => e.includes('whitelisted')))
})

// Test: setMomentLocale() - Whitelist Validation
test('setMomentLocale() - Valid whitelisted locale', () => {
  const result = setMomentLocale('en')
  assert.equal(result.success, true)
  assert.equal(result.whitelisted, true)
})

test('setMomentLocale() - Non-whitelisted locale rejected', () => {
  const result = setMomentLocale('da')  // Not whitelisted
  assert.equal(result.success, false)
  assert.ok(result.error)
})

test('setMomentLocale() - Non-whitelisted locale falls back', () => {
  const result = setMomentLocale('da')
  assert.equal(result.fallback, 'en')
})

test('setMomentLocale() - Throws on non-whitelisted with throwOnInvalid', () => {
  assert.throws(() => {
    setMomentLocale('da', { throwOnInvalid: true });
  });
})

test('setMomentLocale() - Normalizes locale to lowercase', () => {
  const result = setMomentLocale('PT')
  assert.equal(result.normalizedLocale, 'pt')
})

test('setMomentLocale() - Handles whitespace in locale', () => {
  const result = setMomentLocale('  en  ')
  assert.equal(result.success, true)
  assert.equal(result.normalizedLocale, 'en')
})

test('setMomentLocale() - Returns detailed result object', () => {
  const result = setMomentLocale('en')
  assert.ok(result.hasOwnProperty('success'))
  assert.ok(result.hasOwnProperty('requestedLocale'))
  assert.ok(result.hasOwnProperty('normalizedLocale'))
  assert.ok(result.hasOwnProperty('momentLocale'))
  assert.ok(result.hasOwnProperty('timestamp'))
  assert.ok(result.hasOwnProperty('whitelisted'))
})

test('setMomentLocale() - Invalid type falls back', () => {
  const result = setMomentLocale(null)
  assert.equal(result.success, false)
  assert.equal(result.fallback, 'en')
})

test('setMomentLocale() - Throws on invalid type with throwOnInvalid', () => {
  assert.throws(() => {
    setMomentLocale(123, { throwOnInvalid: true });
  });
})

// Test: Locale Whitelist
test('Locale Whitelist - getLocaleWhitelist returns array', () => {
  const whitelist = getLocaleWhitelist()
  assert.ok(Array.isArray(whitelist))
  assert.ok(whitelist.length > 0)
})

test('Locale Whitelist - Contains required locales', () => {
  const whitelist = getLocaleWhitelist()
  assert.ok(whitelist.includes('en'))
  assert.ok(whitelist.includes('pt'))
})

test('Locale Whitelist - No duplicates', () => {
  const whitelist = getLocaleWhitelist()
  const uniqueWhitelist = new Set(whitelist)
  assert.equal(whitelist.length, uniqueWhitelist.size)
})

test('Locale Whitelist - validateWhitelist works', () => {
  const validation = validateWhitelist()
  assert.equal(validation.valid, true)
  assert.ok(validation.whitelistSize > 0)
  assert.equal(validation.requiredCount, 2)
})

test('Locale Whitelist - isWhitelistedLocale works', () => {
  assert.ok(isWhitelistedLocale('en'))
  assert.ok(isWhitelistedLocale('pt'))
  assert.ok(!isWhitelistedLocale('da'))
  assert.ok(!isWhitelistedLocale('invalid'))
})

test('Locale Whitelist - getLocaleWhitelist returns copy', () => {
  const whitelist1 = getLocaleWhitelist()
  const whitelist2 = getLocaleWhitelist()
  assert.notStrictEqual(whitelist1, whitelist2)  // Different arrays (copies)
})

// Test: Locale Security Audit
test('Locale Security - getLocaleSecurityAudit returns structure', () => {
  const audit = getLocaleSecurityAudit()
  assert.ok(audit.hasOwnProperty('totalAttempts'))
  assert.ok(audit.hasOwnProperty('successCount'))
  assert.ok(audit.hasOwnProperty('failureCount'))
  assert.ok(audit.hasOwnProperty('recentAttempts'))
  assert.ok(audit.hasOwnProperty('suspiciousActivity'))
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