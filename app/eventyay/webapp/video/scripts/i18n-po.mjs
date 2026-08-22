import { spawnSync } from 'node:child_process'
import {
	existsSync,
	mkdirSync,
	mkdtempSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { gettextToI18next, i18nextToPo, i18nextToPot } from 'i18next-conv'

const scriptDir = path.dirname(fileURLToPath(import.meta.url))
const videoRoot = path.resolve(scriptDir, '..')
const localeRoot = path.resolve(videoRoot, '../../locale')

function poPath(lang) {
	return path.join(localeRoot, lang, 'LC_MESSAGES', 'video.po')
}

function potPath() {
	return path.join(localeRoot, 'video.pot')
}

function discoverLocaleDirs() {
	return readdirSync(localeRoot, { withFileTypes: true })
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort()
}

async function jsonToPo(lang, catalog) {
	const po = await i18nextToPo(lang, JSON.stringify(catalog), {
		ctxSeparator: false,
		foldLength: 0,
		language: lang,
	})
	return String(po)
}

async function writePo(lang, catalog) {
	const dest = poPath(lang)
	mkdirSync(path.dirname(dest), { recursive: true })
	let po = await jsonToPo(lang, catalog)
	po = po.replace(/"Language: \\n"/, `"Language: ${lang}\\n"`)
	po = normalizeGettextHeader(po)
	writeFileSync(dest, po)
	return dest
}

function normalizeGettextHeader(po) {
	return po
		.replace(/"mime-version:/i, '"MIME-Version:')
		.replace(/"Plural-Forms: (.*)\\n"/, (_, value) => {
			let forms = String(value).replaceAll('!==', '!=').replaceAll('===', '==')
			if (!forms.trim().endsWith(';')) forms = `${forms};`
			return `"Plural-Forms: ${forms}\\n"`
		})
}

async function loadExistingCatalog(lang) {
	try {
		const src = readFileSync(poPath(lang), 'utf8').replaceAll('#~|', '#~#|')
		const mapped = await gettextToI18next(lang, src)
		return JSON.parse(String(mapped))
	} catch {
		return {}
	}
}

async function absorbUkIntoUa() {
	const ukPath = poPath('uk')
	if (!existsSync(ukPath)) return
	const ukCatalog = await loadExistingCatalog('uk')
	const uaCatalog = await loadExistingCatalog('ua')
	const merged = { ...ukCatalog }
	for (const [key, value] of Object.entries(uaCatalog)) {
		if (value) merged[key] = value
	}
	await writePo('ua', merged)
	rmSync(ukPath)
}

function extractKeysToTempJson() {
	const tempDir = mkdtempSync(path.join(tmpdir(), 'video-i18n-'))
	const configPath = path.join(tempDir, 'i18next-parser.config.cjs')
	writeFileSync(
		configPath,
		`module.exports = {
	locales: ['en'],
	keySeparator: false,
	namespaceSeparator: false,
	input: ['src/**/*.{vue,js}'],
	output: ${JSON.stringify(path.join(tempDir, '$LOCALE.json'))},
	sort: true,
	createOldCatalogs: false,
	failOnWarnings: false,
	lexers: {
		js: [{ lexer: 'JavascriptLexer', functions: ['t', '$t', 'i18next.t', 'i18n.t'] }],
		vue: [{ lexer: 'JavascriptLexer', functions: ['t', '$t', 'i18next.t', 'i18n.t'] }],
	},
	defaultValue: function (locale, namespace, key) { return key },
	resetDefaultValueLocale: 'en',
}
`
	)
	const result = spawnSync(
		'npx',
		['i18next-parser', 'src/**/*.{vue,js}', '-c', configPath],
		{ cwd: videoRoot, encoding: 'utf8', shell: false }
	)
	if (result.status !== 0) {
		rmSync(tempDir, { recursive: true, force: true })
		throw new Error(result.stderr || result.stdout || 'i18next-parser failed')
	}
	const extracted = JSON.parse(readFileSync(path.join(tempDir, 'en.json'), 'utf8'))
	rmSync(tempDir, { recursive: true, force: true })
	return extracted
}

async function extractAndMerge() {
	await absorbUkIntoUa()
	const extracted = extractKeysToTempJson()
	const keys = Object.keys(extracted).sort()
	const langs = discoverLocaleDirs().filter((item) => item !== 'uk')
	if (!langs.includes('en')) langs.unshift('en')

	const enExisting = await loadExistingCatalog('en')
	const enCatalog = {}
	for (const key of keys) {
		const previous = enExisting[key]
		enCatalog[key] = previous && previous !== '' ? previous : extracted[key]
	}
	await writePo('en', enCatalog)

	const empty = Object.fromEntries(keys.map((key) => [key, '']))
	writeFileSync(potPath(), normalizeGettextHeader(String(await i18nextToPot('en', JSON.stringify(empty), { foldLength: 0 }))))

	for (const lang of langs.filter((item) => item !== 'en')) {
		const existing = await loadExistingCatalog(lang)
		const catalog = {}
		for (const key of keys) {
			catalog[key] = existing[key] || ''
		}
		await writePo(lang, catalog)
	}
	console.log('Updated video.po for', langs.join(', '))
}

const command = process.argv[2]
if (command === 'extract') {
	await extractAndMerge()
} else {
	console.error('Usage: node scripts/i18n-po.mjs extract')
	process.exit(1)
}
