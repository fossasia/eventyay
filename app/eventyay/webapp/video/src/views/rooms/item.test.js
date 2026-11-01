import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, babelParse } from '@vue/compiler-sfc'
import { normalizeAudioTranslationSource } from '../../lib/validators.js'

// Exercise the component methods without mounting unrelated room modules.
const { descriptor } = parse(readFileSync(new URL('./item.vue', import.meta.url), 'utf8'))
const script = descriptor.script.content
const component = babelParse(script, { sourceType: 'module' }).program.body
	.find(node => node.type === 'ExportDefaultDeclaration').declaration
const methodsNode = component.properties.find(node => node.key.name === 'methods').value
const methods = new Function('normalizeAudioTranslationSource', `return (${script.slice(methodsNode.start, methodsNode.end)})`)(normalizeAudioTranslationSource)

function roomContext(languages) {
	const commits = []
	const current = { language: 'German', url: 'https://example.com/old', useVideo: false }
	return {
		...methods,
		room: { id: 'room-1' },
		pluginLanguages: languages,
		currentInterpretation: current,
		activeTranslationConfig: current,
		showPluginLanguageDropdown: languages.some(entry => entry.language !== 'Original' && normalizeAudioTranslationSource(entry.url || entry.youtube_id)),
		commits,
		$store: { commit: (type, payload) => commits.push({ type, payload }) },
	}
}

test('manual caption selection uses the emitted language for caption-only and shared audio entries', () => {
	const context = roomContext([])
	for (const translation of [
		{ language: 'German', url: null, caption_ws_url: 'wss://example.com/de' },
		{ language: 'French', url: 'https://example.com/shared' },
	]) {
		context.handleCcLanguageChange(translation)
		assert.equal(context.selectedCcLanguage, translation.language)
		assert.equal(context.isManualCCOverride, true)
		assert.equal(context.activeTranslationConfig, context.currentInterpretation)
	}
})

test('manual caption selection falls back to Original when the emitted language is absent', () => {
	const context = roomContext([])
	for (const translation of [undefined, null, {}, { language: '' }]) {
		context.handleCcLanguageChange(translation)
		assert.equal(context.selectedCcLanguage, 'Original')
	}
})

test('schedule change reapplies selected language even when the old URL now matches another language', () => {
	const context = roomContext([
		{ language: 'French', url: 'https://example.com/old' },
		{ language: 'German', url: 'https://example.com/new', use_video: true },
	])
	context.clearStaleTranslation()
	assert.equal(context.activeTranslationConfig.language, 'German')
	assert.equal(context.activeTranslationConfig.url, 'https://example.com/new')
	assert.equal(context.activeTranslationConfig.useVideo, true)
	assert.deepEqual(context.commits, [{
		type: 'updateInterpretationAudio',
		payload: { roomId: 'room-1', interpretation: context.activeTranslationConfig },
	}])
})

test('schedule change normalizes the selected language YouTube source before reapplying it', () => {
	const context = roomContext([{ language: 'German', youtube_id: 'dQw4w9WgXcQ' }])
	context.clearStaleTranslation()
	assert.equal(context.activeTranslationConfig.url, 'dQw4w9WgXcQ')
	assert.equal(context.commits.length, 1)
})

test('unchanged interpretation URL does not restart playback', () => {
	const context = roomContext([{ language: 'German', url: 'https://example.com/old' }])
	context.clearStaleTranslation()
	assert.deepEqual(context.commits, [])
})

for (const languages of [[], [{ language: 'German', url: 'invalid' }]]) {
	test(`missing or unusable selected language preserves the existing stale-translation behavior (${languages.length} rows)`, () => {
		const context = roomContext(languages)
		context.clearStaleTranslation()
		assert.deepEqual(context.commits, [{
			type: 'updateInterpretationAudio',
			payload: { roomId: 'room-1', interpretation: null },
		}])

		const matchingContext = roomContext([
			...languages, { language: 'French', url: 'https://example.com/old' },
		])
		matchingContext.clearStaleTranslation()
		assert.deepEqual(matchingContext.commits, [])
	})
}
