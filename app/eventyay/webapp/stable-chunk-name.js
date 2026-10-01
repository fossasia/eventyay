const GROUP_NAMES = new Set([
	'app',
	'vendor',
	'vendor-rtc',
	'vendor-hls',
	'vendor-mux',
	'vendor-emoji',
	'vue',
	'moment',
	'i18n',
	'zod',
])

const SOURCE_MARKERS = [
	'/eventyay/webapp/video/',
	'/eventyay/webapp/schedule-editor/',
	'/eventyay/webapp/schedule/',
	'/eventyay/locale/',
	'/node_modules/',
]

function sourceBase(moduleId) {
	const clean = String(moduleId || '').split('?')[0]
	let rel = ''
	for (const marker of SOURCE_MARKERS) {
		const at = clean.lastIndexOf(marker)
		if (at !== -1) {
			rel = clean.slice(at + marker.length)
			break
		}
	}
	if (!rel) return ''
	const ext = (rel.match(/\.([A-Za-z0-9]+)$/) || [null, ''])[1]
	const withoutExt = rel.replace(/\.[^.]+$/, '')
	return `${withoutExt}${ext ? `-${ext}` : ''}`
		.replace(/[^A-Za-z0-9/_-]/g, '_')
		.replaceAll('/', '-')
}

export function stableChunkBase(chunkInfo) {
	// Shared groups have a fixed name. A source file uses its path so two
	// files with the same basename do not overwrite each other.
	if (!chunkInfo.facadeModuleId && GROUP_NAMES.has(chunkInfo.name)) {
		return chunkInfo.name
	}
	const source = chunkInfo.facadeModuleId || chunkInfo.moduleIds?.[0] || ''
	const base = sourceBase(source)
	if (!base) return chunkInfo.name
	if (GROUP_NAMES.has(base)) return `mod-${base}`
	return base
}
