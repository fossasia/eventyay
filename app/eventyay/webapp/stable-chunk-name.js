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

export function stableChunkBase(chunkInfo) {
	if (GROUP_NAMES.has(chunkInfo.name)) return chunkInfo.name
	const source = chunkInfo.facadeModuleId || chunkInfo.moduleIds?.[0] || chunkInfo.name
	const clean = String(source).split('?')[0]
	const markers = ['/webapp/video/', '/webapp/schedule-editor/', '/webapp/schedule/', '/node_modules/']
	let rel = clean
	for (const marker of markers) {
		const at = clean.lastIndexOf(marker)
		if (at !== -1) {
			rel = clean.slice(at + marker.length)
			break
		}
	}
	const base = rel
		.replace(/\.[^.]+$/, '')
		.replace(/[^A-Za-z0-9/_-]/g, '_')
		.replaceAll('/', '-')
	return base || chunkInfo.name
}
