import 'styles/preloader.styl'

/* global ENV_DEVELOPMENT */

// Set debug favicon in development mode
const DEBUG_FAVICON_PATH = '/static/common/img/icons/favicon_debug.ico';
if (ENV_DEVELOPMENT) {
	const favicon = document.getElementById('favicon')
	const faviconShortcut = document.getElementById('favicon-shortcut')
	if (favicon) favicon.href = DEBUG_FAVICON_PATH
	if (faviconShortcut) faviconShortcut.href = DEBUG_FAVICON_PATH
}

const showBrowserBlock = function() {
	document.getElementById('browser-block').style.display = 'block'
	document.body.removeChild(document.getElementById('app'))
}

// test syntax & API features
;(function() {
	try {
		// modernizr haz no object.values flag
		if (typeof Object.values !== 'function') {
			throw new Error('Object.values not supported')
		}
		if (typeof Array.prototype.at !== 'function') {
			throw new Error('Array.prototype.at not supported')
		}
		// load app
		import('./main')
	} catch (e) {
		console.error(e)
		showBrowserBlock()
	}
})()
