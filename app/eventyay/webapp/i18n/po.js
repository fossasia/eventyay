export function unescapePoString(value) {
	return String(value || '')
		.replaceAll('\\n', '\n')
		.replaceAll('\\t', '\t')
		.replaceAll('\\r', '\r')
		.replaceAll('\\"', '"')
		.replaceAll('\\\\', '\\')
}

export function parsePo(content) {
	const entries = []
	const parts = `\n${String(content || '')}`.split(/\nmsgid /)
	for (const part of parts.slice(1)) {
		const lines = part.split('\n')
		let mode = 'id'
		const idChunks = []
		const strChunks = []
		const first = lines[0]
		const firstMatch = first.match(/^"(.*)"$/)
		if (firstMatch) idChunks.push(firstMatch[1])
		for (const line of lines.slice(1)) {
			if (line.startsWith('msgstr ')) {
				mode = 'str'
				const match = line.match(/^msgstr "(.*)"$/)
				if (match) strChunks.push(match[1])
				continue
			}
			if (line.startsWith('"')) {
				const chunk = line.endsWith('"') ? line.slice(1, -1) : line.slice(1)
				if (mode === 'id') idChunks.push(chunk)
				else strChunks.push(chunk)
			} else if (mode === 'str') {
				break
			}
		}
		const msgid = unescapePoString(idChunks.join(''))
		if (msgid) entries.push([msgid, unescapePoString(strChunks.join(''))])
	}
	return Object.fromEntries(entries)
}
