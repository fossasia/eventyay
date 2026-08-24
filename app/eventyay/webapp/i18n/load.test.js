import test from 'node:test'
import assert from 'node:assert/strict'
import {resolveLocaleLoader, toGettextLocale} from './load.js'

test('locale aliases resolve Ukrainian and Persian catalogs', () => {
	const loaders = {
		'/locale/ua/LC_MESSAGES/schedule.po': () => 'ua',
		'/locale/fa/LC_MESSAGES/schedule.po': () => 'fa',
		'/locale/en/LC_MESSAGES/schedule.po': () => 'en',
		'/locale/ja/LC_MESSAGES/schedule.po': () => 'ja',
	}
	assert.equal(resolveLocaleLoader(loaders, 'uk')(), 'ua')
	assert.equal(resolveLocaleLoader(loaders, 'fa-ir')(), 'fa')
	assert.equal(resolveLocaleLoader(loaders, 'en-GB')(), 'en')
	assert.equal(resolveLocaleLoader(loaders, 'ja-jp')(), 'ja')
	assert.equal(toGettextLocale('zh-hans'), 'zh_Hans')
	assert.equal(toGettextLocale('pt-br'), 'pt_BR')
})
