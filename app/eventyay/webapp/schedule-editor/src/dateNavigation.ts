export function dayForHash<T extends { format: (format: string) => string }>(days: T[], date: string): T | undefined {
  return days.find((day) => day.format('YYYY-MM-DD') === date) || (!date ? days[0] : undefined)
}

export function updateDayHash(date: string, replace: boolean): void {
  if (window.location.hash === `#${date}`) return
  if (replace) {
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}#${date}`)
  } else {
    window.location.hash = date
  }
}

export function isVerticallyScrollable(scrollHeight: number, clientHeight: number, overflowY: string): boolean {
  return scrollHeight > clientHeight && ['auto', 'scroll'].includes(overflowY)
}

export function horizontalTabScrollDelta(selectorLeft: number, selectorRight: number, tabLeft: number, tabRight: number): number {
  if (tabLeft < selectorLeft) return tabLeft - selectorLeft
  if (tabRight > selectorRight) return tabRight - selectorRight
  return 0
}
