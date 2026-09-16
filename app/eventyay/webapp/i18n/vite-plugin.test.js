import test from 'node:test'
import assert from 'node:assert/strict'
import {createGettextPlugin, gettextFilePath} from './vite-plugin.js'

const VIDEO_PO = `
msgid "Schedule"
msgstr "Zeitplan"

msgid "Admin mode"
msgstr "Admin-Modus"
`

test('gettext plugin strips Vite query strings before matching .po paths', () => {
	assert.equal(
		gettextFilePath('/app/eventyay/locale/en/LC_MESSAGES/video.po?import'),
		'/app/eventyay/locale/en/LC_MESSAGES/video.po'
	)
	assert.equal(
		gettextFilePath('/app/eventyay/locale/en/LC_MESSAGES/video.po?raw&import'),
		'/app/eventyay/locale/en/LC_MESSAGES/video.po'
	)
	const plugin = createGettextPlugin('video')
	const transformed = plugin.transform(
		VIDEO_PO,
		'/app/eventyay/locale/de/LC_MESSAGES/video.po?import'
	)
	assert.ok(transformed)
	assert.match(transformed.code, /"Schedule":"Zeitplan"/)
	assert.match(transformed.code, /"Admin mode":"Admin-Modus"/)
	assert.equal(
		plugin.transform(VIDEO_PO, '/app/eventyay/locale/en/LC_MESSAGES/django.po'),
		null
	)
	assert.equal(
		plugin.transform('export default {}', '/app/eventyay/locale/en/LC_MESSAGES/video.po?import&raw'),
		null
	)
	assert.deepEqual(
		JSON.parse(plugin.transform(`
msgid "Schedule"
msgstr ""
`, '/app/eventyay/locale/en/LC_MESSAGES/video.po').code.replace('export default ', '')),
		{}
	)
})
