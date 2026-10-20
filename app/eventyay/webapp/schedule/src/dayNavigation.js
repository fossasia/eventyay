export function getDayAtScrollPosition (dayStarts, top) {
	let day = dayStarts[0]?.day || null
	for (const start of dayStarts) {
		if (start.top > top + 1) break
		day = start.day
	}
	return day
}

export function updateDayEndSpace (element, lastDayStart, viewportHeight, clearance, isLast = true) {
	const previous = parseFloat(element.style.getPropertyValue('--schedule-day-end-padding')) || 0
	const dayHeight = lastDayStart ? element.getBoundingClientRect().bottom - previous - lastDayStart.getBoundingClientRect().top : 0
	const padding = isLast && lastDayStart ? Math.ceil(Math.max(0, viewportHeight - clearance - dayHeight)) : 0
	if (padding !== previous) element.style.setProperty('--schedule-day-end-padding', `${padding}px`)
}
