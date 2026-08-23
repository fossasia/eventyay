/**
 * Video catalog fallback: empty/untranslated locales must use English, never raw keys.
 * Run: node --test src/i18n-catalog.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import {spawnSync} from 'node:child_process'
import {readFileSync} from 'node:fs'
import {fileURLToPath} from 'node:url'
import path from 'node:path'
import i18next from 'i18next'
import {isEnglishLocale, mergeCatalogWithEnglish, usableTranslations} from './i18n-catalog.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(here, '../../../../../')
const enPoPath = path.resolve(here, '../../../locale/en/LC_MESSAGES/video.po')

function parsePo(content) {
	const entries = []
	const parts = content.split(/\nmsgid /)
	for (const part of parts.slice(1)) {
		const lines = part.splitlines ? part.splitlines() : part.split('\n')
		let mode = 'id'
		const idChunks = []
		const strChunks = []
		const first = lines[0]
		const firstMatch = first.match(/^"(.*)"$/)
		if (firstMatch) idChunks.push(firstMatch[1])
		for (const line of lines.slice(1)) {
			if (line.startsWith('msgstr ')) {
				mode = 'str'
				const match = line.match(/^msgstr "(.*)"$/)
				if (match) strChunks.push(match[1])
				continue
			}
			if (line.startsWith('"')) {
				const chunk = line.endsWith('"') ? line.slice(1, -1) : line.slice(1)
				if (mode === 'id') idChunks.push(chunk)
				else strChunks.push(chunk)
			} else if (mode === 'str') {
				break
			}
		}
		const msgid = idChunks.join('')
		if (msgid) entries.push([msgid, strChunks.join('')])
	}
	return Object.fromEntries(entries)
}

function catalogFromGit(refPath) {
	const result = spawnSync('git', ['show', refPath], {cwd: repoRoot, encoding: 'utf8'})
	if (result.status !== 0) {
		throw new Error(result.stderr || `git show ${refPath} failed`)
	}
	return parsePo(result.stdout)
}

function namespacedKeys(catalog) {
	return Object.keys(catalog).filter((key) => key.includes(':') && !key.includes(' '))
}

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

test('real video.po files: Hindi stays English, German keeps Zeitplan', async () => {
	const english = parsePo(readFileSync(enPoPath, 'utf8'))
	const hindi = catalogFromGit('chore/video-po-catalogs:app/eventyay/locale/hi/LC_MESSAGES/video.po')
	const german = catalogFromGit('chore/video-po-catalogs:app/eventyay/locale/de/LC_MESSAGES/video.po')

	assert.ok(english['RoomsSidebar:schedule:label'])
	assert.notEqual(english['RoomsSidebar:schedule:label'], 'RoomsSidebar:schedule:label')
	assert.equal(hindi['RoomsSidebar:schedule:label'] || '', '')
	assert.equal(german['RoomsSidebar:schedule:label'], 'Zeitplan')

	const hiMerged = mergeCatalogWithEnglish(english, hindi, 'hi')
	const deMerged = mergeCatalogWithEnglish(english, german, 'de')

	const englishFallback = usableTranslations(english, 'en')
	for (const key of namespacedKeys(englishFallback)) {
		assert.notEqual(englishFallback[key], key, `English catalog still stores key ${key}`)
		assert.equal(hiMerged[key], englishFallback[key], `Hindi should fall back to English for ${key}`)
	}
	assert.equal(hiMerged['RoomsSidebar:schedule:label'], 'Schedule')
	assert.equal(hiMerged['CreateChatPrompt:error:no-permission'], 'You do not have permission to create channels.')
	assert.equal(deMerged['RoomsSidebar:schedule:label'], 'Zeitplan')
	assert.equal(deMerged.Save || english.Save, english.Save)

	await i18next.init({
		lng: 'hi',
		fallbackLng: 'en',
		resources: {
			en: {translation: usableTranslations(english, 'en')},
			hi: {translation: hiMerged},
			de: {translation: deMerged},
		},
		keySeparator: false,
		nsSeparator: false,
		returnEmptyString: false,
	})
	assert.equal(i18next.t('RoomsSidebar:schedule:label'), 'Schedule')
	assert.equal(i18next.t('RoomsSidebar:admin-headline:text'), english['RoomsSidebar:admin-headline:text'])
	assert.notEqual(i18next.t('RoomsSidebar:admin-headline:text'), 'RoomsSidebar:admin-headline:text')

	await i18next.changeLanguage('de')
	assert.equal(i18next.t('RoomsSidebar:schedule:label'), 'Zeitplan')
	assert.equal(i18next.t('RoomsSidebar:admin-headline:text'), german['RoomsSidebar:admin-headline:text'] || english['RoomsSidebar:admin-headline:text'])
	assert.notEqual(i18next.t('RoomsSidebar:schedule:label'), 'RoomsSidebar:schedule:label')

	await i18next.changeLanguage('en')
	assert.equal(i18next.t('RoomsSidebar:schedule:label'), 'Schedule')
})
