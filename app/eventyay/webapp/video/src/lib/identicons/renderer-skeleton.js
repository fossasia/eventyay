// Example Empty Identicon Renderer
// Each renderer module exposes two parts:
// - a renderer definition, which specifies how it can be configured by event organizers
// - the render function, which renders a SVG based on numbers from a random number generator and (optionally) a user profile

export const definition = {
	label: 'Skeleton',
	colorPalette: {
		size: 3,
		defaults: ['#ff0000', '#00ff00', '#0000ff']
	}
}

// SVG render function
// Parameters:
// - random: seeded generator with integer(min, max), pick(array), and engine.next()
// - userProfile: object, can be used to render additional information from, optional
//   - display_name: string
//   - fields: object, additional fields added by event organizers
// - config: object, event-global config for identicons, based on renderer definition
//   - colorPalette: [string], array of colors, same size as definition.colorPalette.size

export function renderSvg(random, userProfile, config) {
	return `
	<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">
		YOUR SVG HERE
	</svg>
	`
}
