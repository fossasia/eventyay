/**
 * Shared Vue catalog fallback: empty/untranslated locales must use English, never raw keys.
 * Run: node --test catalog.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {isEnglishLocale, mergeCatalogWithEnglish, toDjangoLanguage, usableTranslations} from './catalog.js'

test('usableTranslations drops empty and msgid copies except in English', () => {
	const catalog = {
		Save: 'Save',
		'RoomsSidebar:schedule:label': 'RoomsSidebar:schedule:label',
		Schedule: '',
		Cancel: 'Abbrechen',
	}
	assert.deepEqual(usableTranslations(catalog, 'de'), {Cancel: 'Abbrechen'})
	assert.deepEqual(usableTranslations(catalog, 'en'), {
		Save: 'Save',
		'RoomsSidebar:schedule:label': 'RoomsSidebar:schedule:label',
		Cancel: 'Abbrechen',
	})
})

test('missing or empty catalogs fall back to English', () => {
	const english = {
		'RoomsSidebar:schedule:label': 'Schedule',
		Save: 'Save',
	}
	assert.equal(mergeCatalogWithEnglish(english, null, 'hi')['RoomsSidebar:schedule:label'], 'Schedule')
	assert.equal(mergeCatalogWithEnglish(english, {}, 'bg')['RoomsSidebar:schedule:label'], 'Schedule')
	assert.equal(mergeCatalogWithEnglish(english, {Save: ''}, 'ja').Save, 'Save')
	assert.equal(isEnglishLocale('en-gb'), true)
})

test('partial Weblate catalogs overlay English', () => {
	const english = {
		'RoomsSidebar:schedule:label': 'Schedule',
		Save: 'Save',
	}
	const german = {
		'RoomsSidebar:schedule:label': 'Zeitplan',
		Save: '',
	}
	const merged = mergeCatalogWithEnglish(english, german, 'de')
	assert.equal(merged['RoomsSidebar:schedule:label'], 'Zeitplan')
	assert.equal(merged.Save, 'Save')
})

test('English-as-msgid schedule keys still fall back when a locale is empty', () => {
	const english = {Search: 'Search', min: 'min'}
	const hindi = mergeCatalogWithEnglish(english, {Search: '', min: 'min'}, 'hi')
	assert.equal(hindi.Search, 'Search')
	assert.equal(hindi.min, 'min')
})

test('toDjangoLanguage normalizes underscores and case', () => {
	assert.equal(toDjangoLanguage('en_GB'), 'en-gb')
	assert.equal(toDjangoLanguage('de_Formal'), 'de-formal')
	assert.equal(isEnglishLocale('en_US'), true)
	assert.equal(isEnglishLocale('de'), false)
})
