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

function collectLiteralKeys(appRoot) {
	const keys = {}
	const callRe = /(?:\$t|translate|i18next\.t|i18n\.t)\(\s*(['"])((?:\\.|(?!\1)[^\\])*)(\1)/g
	for (const file of walkSourceFiles(path.join(appRoot, 'src'))) {
		const text = readFileSync(file, 'utf8')
		callRe.lastIndex = 0
		let match
		while ((match = callRe.exec(text))) {
			const key = match[2].replaceAll('\\n', '\n').replaceAll('\\t', '\t').replaceAll("\\'", "'").replaceAll('\\"', '"')
			if (!key || key.startsWith('undefined:') || key.endsWith(':')) continue
			if (key.includes(':') && !key.includes(' ')) continue
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
	const extracted = {
		...extractKeysToTempJson(),
		...collectLiteralKeys(appRoot),
	}
	for (const key of Object.keys(extracted)) {
		if (key.startsWith('undefined:')) delete extracted[key]
	}
	const keys = Object.keys(extracted).sort()
	const localeDirs = discoverLocaleDirs().filter((item) => item !== 'uk')
	const langs = new Set(['en'])
	for (const dir of localeDirs) {
		if (dir === 'en') continue
		if (args.allLocales || existsSync(poPath(dir))) langs.add(dir)
	}

	const enExisting = await loadExistingCatalog('en')
	const enCatalog = {}
	for (const key of keys) {
		if (key.startsWith('undefined:')) {
			enCatalog[key] = ''
			continue
		}
		const previous = enExisting[key]
		enCatalog[key] = previous && previous !== '' ? previous : extracted[key]
	}
	await writePo('en', enCatalog)

	const empty = Object.fromEntries(keys.map((key) => [key, '']))
	writeFileSync(
		potPath(),
		normalizeGettextHeader(String(await i18nextToPot('en', JSON.stringify(empty), {foldLength: 0})))
	)

	for (const lang of [...langs].filter((item) => item !== 'en').sort()) {
		const existing = await loadExistingCatalog(lang)
		const catalog = {}
		for (const key of keys) {
			catalog[key] = existing[key] || ''
		}
		await writePo(lang, catalog)
	}
	console.log(`Updated ${domain}.po for`, [...langs].sort().join(', '))
}

await extractAndMerge()
