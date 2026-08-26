import {spawnSync} from 'node:child_process'
import {createRequire} from 'node:module'
import {
	existsSync,
	mkdirSync,
	mkdtempSync,
	readdirSync,
	readFileSync,
	rmSync,
	writeFileSync,
} from 'node:fs'
import {tmpdir} from 'node:os'
import path from 'node:path'
import {fileURLToPath, pathToFileURL} from 'node:url'

function parseArgs(argv) {
	const args = {allLocales: false, input: 'src/**/*.{vue,js,ts}'}
	for (let i = 0; i < argv.length; i += 1) {
		const item = argv[i]
		if (item === '--domain') args.domain = argv[++i]
		else if (item === '--app') args.app = argv[++i]
		else if (item === '--input') args.input = argv[++i]
		else if (item === '--all-locales') args.allLocales = true
		else if (item === 'extract') args.command = 'extract'
	}
	return args
}

const args = parseArgs(process.argv.slice(2))
if (args.command !== 'extract' || !args.domain) {
	console.error('Usage: node extract.mjs extract --domain <name> [--app <dir>] [--input <glob>] [--all-locales]')
	process.exit(1)
}

const appRoot = path.resolve(args.app || process.cwd())
const localeRoot = path.resolve(appRoot, '../../locale')
const domain = args.domain
const require = createRequire(path.join(appRoot, 'package.json'))
const conv = await import(pathToFileURL(require.resolve('i18next-conv')).href)
const {gettextToI18next, i18nextToPo, i18nextToPot} = conv

function poPath(lang) {
	return path.join(localeRoot, lang, 'LC_MESSAGES', `${domain}.po`)
}

function isSourceLocale(lang) {
	return lang === 'en' || String(lang).startsWith('en_') || String(lang).startsWith('en-')
}

function potPath() {
	return path.join(localeRoot, `${domain}.pot`)
}

function discoverLocaleDirs() {
	return readdirSync(localeRoot, {withFileTypes: true})
		.filter((entry) => entry.isDirectory())
		.map((entry) => entry.name)
		.sort()
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
	mkdirSync(path.dirname(dest), {recursive: true})
	let po = await jsonToPo(lang, catalog)
	po = po.replace(/"Language: \\n"/, `"Language: ${lang}\\n"`)
	po = normalizeGettextHeader(po)
	writeFileSync(dest, po)
	return dest
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
	const merged = {...ukCatalog}
	for (const [key, value] of Object.entries(uaCatalog)) {
		if (value) merged[key] = value
	}
	await writePo('ua', merged)
	rmSync(ukPath)
}

function walkSourceFiles(dir, files = []) {
	for (const entry of readdirSync(dir, {withFileTypes: true})) {
		if (entry.name === 'node_modules' || entry.name === 'dist') continue
		const full = path.join(dir, entry.name)
		if (entry.isDirectory()) walkSourceFiles(full, files)
		else if (/\.(vue|js|ts)$/.test(entry.name)) files.push(full)
	}
	return files
}

function unescapeJsString(value) {
	return String(value || '')
		.replaceAll('\\n', '\n')
		.replaceAll('\\t', '\t')
		.replaceAll('\\r', '\r')
		.replaceAll("\\'", "'")
		.replaceAll('\\"', '"')
		.replace(/\\u([0-9a-fA-F]{4})/g, (_, hex) => String.fromCharCode(Number.parseInt(hex, 16)))
		.replaceAll('\\\\', '\\')
}

function isGeneratedPluralKey(key, keys) {
	const match = key.match(/^(.*)_(zero|one|two|few|many|other)$/)
	if (!match) return false
	const base = match[1]
	return keys.has(base) || base.includes('{{')
}

function cleanExtractedKeys(extracted) {
	const normalized = {}
	for (const [rawKey, rawValue] of Object.entries(extracted || {})) {
		const key = unescapeJsString(rawKey)
		if (!key || key.startsWith('undefined:')) continue
		const value = unescapeJsString(rawValue)
		normalized[key] = value || key
	}
	const keys = new Set(Object.keys(normalized))
	for (const key of keys) {
		if (isGeneratedPluralKey(key, keys)) delete normalized[key]
	}
	return normalized
}

function collectLiteralKeys(appRoot) {
	const keys = {}
	const quotedRe = /(?:\$t|translate|i18next\.t|i18n\.t)\(\s*(['"])((?:\\.|(?!\1)[^\\])*)(\1)/g
	const backtickRe = /(?:\$t|translate|i18next\.t|i18n\.t)\(\s*`([^`$]*)`/g
	for (const file of walkSourceFiles(path.join(appRoot, 'src'))) {
		const text = readFileSync(file, 'utf8')
		quotedRe.lastIndex = 0
		let match
		while ((match = quotedRe.exec(text))) {
			const key = unescapeJsString(match[2])
			if (!key || key.startsWith('undefined:')) continue
			keys[key] = key
		}
		backtickRe.lastIndex = 0
		while ((match = backtickRe.exec(text))) {
			const key = unescapeJsString(match[1])
			if (!key || key.startsWith('undefined:') || key.includes('${')) continue
			keys[key] = key
		}
	}
	return keys
}

function extractKeysToTempJson() {
	const tempDir = mkdtempSync(path.join(tmpdir(), `${domain}-i18n-`))
	const configPath = path.join(tempDir, 'i18next-parser.config.cjs')
	writeFileSync(
		configPath,
		`module.exports = {
	locales: ['en'],
	keySeparator: false,
	namespaceSeparator: false,
	input: ${JSON.stringify([args.input])},
	output: ${JSON.stringify(path.join(tempDir, '$LOCALE.json'))},
	sort: true,
	createOldCatalogs: false,
	failOnWarnings: false,
	pluralSeparator: false,
	lexers: {
		js: [{ lexer: 'JavascriptLexer', functions: ['t', '$t', 'i18next.t', 'i18n.t', 'translate'] }],
		ts: [{ lexer: 'JavascriptLexer', functions: ['t', '$t', 'i18next.t', 'i18n.t', 'translate'] }],
		vue: [{ lexer: 'JavascriptLexer', functions: ['t', '$t', 'i18next.t', 'i18n.t', 'translate'] }],
	},
	defaultValue: function (locale, namespace, key) { return key },
	resetDefaultValueLocale: 'en',
}
`
	)
	const result = spawnSync('npx', ['i18next-parser', args.input, '-c', configPath], {
		cwd: appRoot,
		encoding: 'utf8',
		shell: false,
	})
	if (result.status !== 0) {
		rmSync(tempDir, {recursive: true, force: true})
		throw new Error(result.stderr || result.stdout || 'i18next-parser failed')
	}
	const extracted = JSON.parse(readFileSync(path.join(tempDir, 'en.json'), 'utf8'))
	rmSync(tempDir, {recursive: true, force: true})
	return extracted
}

async function extractAndMerge() {
	await absorbUkIntoUa()
	const extracted = cleanExtractedKeys({
		...extractKeysToTempJson(),
		...collectLiteralKeys(appRoot),
	})
	const keys = Object.keys(extracted).sort()
	const localeDirs = discoverLocaleDirs().filter((item) => item !== 'uk' && !isSourceLocale(item))
	const langs = new Set()
	for (const dir of localeDirs) {
		if (args.allLocales || existsSync(poPath(dir))) langs.add(dir)
	}

	const empty = Object.fromEntries(keys.map((key) => [key, '']))
	writeFileSync(
		potPath(),
		normalizeGettextHeader(String(await i18nextToPot('en', JSON.stringify(empty), {foldLength: 0})))
	)

	for (const lang of [...langs].sort()) {
		const existing = await loadExistingCatalog(lang)
		const catalog = {}
		for (const key of keys) {
			catalog[key] = existing[key] || ''
		}
		await writePo(lang, catalog)
	}
	console.log(`Updated ${domain}.pot` + (langs.size ? ` and ${domain}.po for ${[...langs].sort().join(', ')}` : ''))
}

await extractAndMerge()
