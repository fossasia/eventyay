/**
 * Checks the fullscreen side gutter shared by App.vue and ScheduleView.vue.
 * Run: node --test src/styles/fullscreen.test.js
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import stylus from 'stylus'

const stylesDir = dirname(fileURLToPath(import.meta.url))

function renderGutter () {
	const src = "@import 'fullscreen'\n.root\n\t&:fullscreen\n\t\tfullscreen-gutter()\n"
	return stylus(src).set('paths', [stylesDir]).render()
}

// selector -> declarations, e.g. {'margin-left': '16px'}
function parseRules (css) {
	const rules = {}
	for (const [, selectors, body] of css.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
		const decls = Object.fromEntries(body.split(';')
			.map(decl => decl.split(':').map(part => part.trim()))
			.filter(([property]) => property))
		for (const selector of selectors.split(',')) rules[selector.trim().replace(/\s+/g, ' ')] = decls
	}
	return rules
}

test('fullscreen gutter adds 16px to the toolbar, grid and list sides', () => {
	const rules = parseRules(renderGutter())
	const gutter = side => ({ [`${side}-left`]: '16px', [`${side}-right`]: '16px' })
	assert.deepEqual(rules['.root:fullscreen > .c-schedule-toolbar .toolbar-row'], gutter('padding'))
	assert.deepEqual(rules['.root:fullscreen .c-grid-schedule'], gutter('margin'))
	assert.deepEqual(rules['.root:fullscreen .c-linear-schedule > .bucket'], gutter('padding'))
	assert.deepEqual(rules['.root:fullscreen .c-linear-schedule > .bucket .c-linear-schedule-session'], { 'margin-right': '0' })
	assert.deepEqual(rules['.root:fullscreen .c-linear-schedule > .bucket .break'], { 'margin-right': '0' })
})

test('both fullscreen targets use the gutter', () => {
	for (const file of ['../App.vue', '../components/ScheduleView.vue']) {
		const style = readFileSync(join(stylesDir, file), 'utf8').replace(/\r\n/g, '\n').split('<style lang="stylus">')[1]
		assert.match(style, /@import '(\.\.\/)?styles\/fullscreen\.styl'/, file)
		assert.match(style, /\t&:fullscreen\n(\t\t.*\n)*?\t\tfullscreen-gutter\(\)\n/, file)
	}
})
