/**
 * Exporter Service - fetches schedule exporters from Django API
 */
import config from 'config'
import api from './api'

let exportersCache = null
let cacheTimestamp = null
const CACHE_TTL = 5 * 60 * 1000

/** Fetch available exporters from API with caching */
export async function getExporters(forceRefresh = false) {
	// Return cached data if still valid
	if (!forceRefresh && exportersCache && cacheTimestamp && (Date.now() - cacheTimestamp < CACHE_TTL)) {
		return exportersCache
	}

	try {
		const url = config.api.base + 'schedules/exporters/'
		const authHeader = api._config?.token
			? `Bearer ${api._config.token}`
			: (api._config?.clientId ? `Client ${api._config.clientId}` : null)

		const headers = {
			Accept: 'application/json',
		}
		if (authHeader) {
			headers.Authorization = authHeader
		}

		const response = await fetch(url, {
			method: 'GET',
			headers,
		})

		if (!response.ok) {
			throw new Error(`Failed to fetch exporters: ${response.status}`)
		}

		const data = await response.json()
		const exporters = data.results || []

		// Transform to consistent format for components
		exportersCache = exporters.map(exporter => ({
			id: exporter.identifier,
			label: exporter.label,
			type: exporter.type, // 'public' or 'personal'
			public: exporter.public,
			// Derive file extension from identifier for download filename
			extension: getExtensionFromIdentifier(exporter.identifier),
			// Check if this is a calendar type (for QR code display)
			isCalendar: isCalendarExporter(exporter.identifier),
		}))

		cacheTimestamp = Date.now()
		return exportersCache
	} catch (error) {
		console.error('[Exporters] Failed to fetch exporters:', error)
		if (exportersCache) return exportersCache
		return getFallbackExporters()
	}
}

/** Get export download URL */
export function getExportUrl(exporterId, scheduleId = 'latest') {
	return `${config.api.base}schedules/${scheduleId}/exporters/${exporterId}`
}

/** Download export file and return blob with filename */
export async function downloadExport(exporterId, scheduleId = 'latest') {
	const url = getExportUrl(exporterId, scheduleId)
	const authHeader = api._config?.token
		? `Bearer ${api._config.token}`
		: (api._config?.clientId ? `Client ${api._config.clientId}` : null)

	const headers = {}
	if (authHeader) {
		headers.Authorization = authHeader
	}

	const response = await fetch(url, {
		method: 'GET',
		headers,
	})

	if (!response.ok) {
		throw new Error(`Export failed: ${response.status}`)
	}

	let filename = `schedule-${exporterId}`
	const contentDisposition = response.headers.get('Content-Disposition')
	if (contentDisposition) {
		const match = contentDisposition.match(/filename="?([^"]+)"?/)
		if (match) filename = match[1]
	} else {
		filename = `schedule.${getExtensionFromIdentifier(exporterId)}`
	}

	const blob = await response.blob()
	return { blob, filename }
}

/** Trigger file download in browser */
export function triggerDownload(blob, filename) {
	const url = window.URL.createObjectURL(blob)
	const a = document.createElement('a')
	document.body.appendChild(a)
	a.href = url
	a.download = filename
	a.click()
	window.URL.revokeObjectURL(url)
	a.remove()
}

function getExtensionFromIdentifier(identifier) {
	const parts = identifier.split('.')
	return parts.length > 1 ? parts[parts.length - 1] : 'txt'
}

function isCalendarExporter(identifier) {
	return identifier.includes('.ics') || identifier.includes('.xcal') || identifier.includes('.xml')
}

function getFallbackExporters() {
	return [
		{ id: 'schedule.ics', label: 'iCal', type: 'public', public: true, extension: 'ics', isCalendar: true },
		{ id: 'schedule.json', label: 'JSON', type: 'public', public: true, extension: 'json', isCalendar: false },
		{ id: 'schedule.xml', label: 'XML', type: 'public', public: true, extension: 'xml', isCalendar: true },
		{ id: 'schedule.xcal', label: 'XCal', type: 'public', public: true, extension: 'xcal', isCalendar: true },
		{ id: 'schedule-my.ics', label: 'My Schedule (iCal)', type: 'personal', public: false, extension: 'ics', isCalendar: true },
		{ id: 'schedule-my.json', label: 'My Schedule (JSON)', type: 'personal', public: false, extension: 'json', isCalendar: false },
		{ id: 'schedule-my.xml', label: 'My Schedule (XML)', type: 'personal', public: false, extension: 'xml', isCalendar: true },
		{ id: 'schedule-my.xcal', label: 'My Schedule (XCal)', type: 'personal', public: false, extension: 'xcal', isCalendar: true },
	]
}

export function clearCache() {
	exportersCache = null
	cacheTimestamp = null
}

export default {
	getExporters,
	getExportUrl,
	downloadExport,
	triggerDownload,
	clearCache,
}
