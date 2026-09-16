import * as identiheart from './renderer-identiheart.js'
import * as initials from './renderer-initials.js'

const renderers = {
	identiheart,
	initials
}

function hashSource(source) {
	return String(source).split('').reduce((hash, char) => {
		hash = ((hash << 5) - hash) + char.charCodeAt(0)
		return hash | 0
	}, 0)
}

function createSeededRandom(seed) {
	let state = seed >>> 0
	const next = () => {
		state = (state + 0x6d2b79f5) >>> 0
		let t = state
		t = Math.imul(t ^ (t >>> 15), t | 1)
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
		return (t ^ (t >>> 14)) >>> 0
	}
	return {
		engine: { next },
		integer(min, max) {
			return min + (next() % (max - min + 1))
		},
		pick(values) {
			return values[next() % values.length]
		}
	}
}

export function renderSvg(user, style) {
	const seed = hashSource(user.profile?.avatar?.identicon ?? user.profile?.identicon ?? user.id)
	const random = createSeededRandom(seed)
	const renderer = renderers[style] || identiheart
	const config = {
		colorPalette: renderer.definition.colorPalette.defaults
	}
	return renderer.renderSvg(random, user.profile, config)
}

export function renderUrl(user, style) {
	return `data:image/svg+xml;base64,${btoa(renderSvg(user, style).replace(/[\t\n]/g, ''))}`
}

export { renderers }
