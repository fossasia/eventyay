<template lang="pug">
.c-grid-schedule(ref="rootEl", :class="'density-' + density")
	.grid(ref="grid", :style="gridStyle", :class="gridClasses", @click="onGridClick($event)", @pointerup="stopDragging($event)")
		template(v-for="slice of visibleTimeslices", :key="slice.name")
			.timeslice(:ref="setTimesliceRef", :class="getSliceClasses(slice)", :data-slice="slice.date.format()", :style="getSliceStyle(slice)", @click="expandTimeslice(slice)") {{ getSliceLabel(slice) }}
				svg(viewBox="0 0 10 10", v-if="isSliceExpandable(slice)").expand
					path(d="M 0 4 L 5 0 L 10 4 z")
					path(d="M 0 6 L 5 10 L 10 6 z")
			.timeseparator(:class="getSliceClasses(slice)", :style="getSliceStyle(slice)")
		.room(:style="{'grid-area': `1 / 1 / auto / auto`}")
		.room(v-for="(room, i) of visibleRooms", :key="room.id", :style="getRoomHeaderStyle(room, i)")
			span.room-name(:title="getLocalizedString(room.name)") {{ getLocalizedString(room.name) }}
			.hide-room.no-print(v-if="visibleRooms.length > 1", @click="hiddenRooms = rooms.filter(r => hiddenRooms.includes(r) || r === room)")
				i.fa.fa-eye-slash
		session.placing-preview(v-if="draggedSession && hoverSlice", :style="getHoverSliceStyle()", :session="draggedSession", :isDragClone="true", :overrideStart="hoverSlice.time")
		template(v-for="session of visibleSessions", :key="session.id")
			session(
				v-if="hasValidPosition(session)"
				:session="session",
				:warnings="getSessionWarnings(session)",
				:isDragged="draggedSession && (session.id === draggedSession.id)",
				:style="getSessionStyle(session)",
				:showRoom="false",
				v-bind="talkSessionBindings",
				@startDragging="startDragging($event)",
				@editSession="emit('editSession', $event)",
				@deleteSession="emit('deleteSession', $event)",
				@assignMembers="emit('assignMembers', $event)",
				v-on="talkSessionListeners",
			)
		.availability(v-for="availability of visibleAvailabilities", :key="`${availability.room.id}-${availability.start.valueOf()}-${availability.end.valueOf()}`", :style="getSessionStyle(availability)", :class="availability.active ? ['active'] : []")
	#hidden-rooms.no-print(v-if="hiddenRooms.length")
		.hidden-rooms-header
			i.fa.fa-eye-slash
			span.hidden-rooms-title {{ $t('Hidden rooms') }}
			span.hidden-rooms-badge {{ hiddenRooms.length }}
		.room-list
			.room-entry(v-for="room of hiddenRooms", :key="room.id", @click="hiddenRooms.splice(hiddenRooms.indexOf(room), 1)", :title="$t('Click to show room')")
				span.room-name {{ getLocalizedString(room.name) }}
				button.show-room-btn(type="button", @click.stop="hiddenRooms.splice(hiddenRooms.indexOf(room), 1)", :aria-label="$t('Show room')", :title="$t('Show room')")
					i.fa.fa-eye(aria-hidden="true")
</template>

<script lang="ts" setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import moment, { Moment } from 'moment-timezone'
import TalkSession from './Session.vue'
import ShiftSession from '~/teamshifts-adapter/Session.vue'
import { resolveMode, computeShiftColumnLayout, buildShiftGridTemplateColumns, computeShiftOverlapSubcolumn, assignRoomTracks } from '~/teamshifts-adapter'
import { getLocalizedString } from '~/utils'

const mode = resolveMode()
const Session = mode === 'shifts' || mode === 'public-shifts' ? ShiftSession : TalkSession

interface Room {
  id: string
  name: string | Record<string, string>
  description?: Record<string, string>
}

interface Speaker {
  name: string
  code: string
}

interface SessionDatum {
  id: number | string
  code?: string
  title?: string | Record<string, string>
  speakers?: Speaker[]
  room: Room
  start: Moment
  end: Moment
  duration: number
  state?: string
  track?: { name: string | Record<string, string>; color?: string }
  abstract?: string
  [key: string]: string | number | boolean | Record<string, string> | Speaker[] | Room | Moment | { name: string | Record<string, string>; color?: string } | undefined
}

interface Availability {
  room: Room
  start: Moment
  end: Moment
  active?: boolean
  type?: string
  [key: string]: string | boolean | Room | Moment | undefined
}

interface Timeslice {
  date: Moment
  name: string
  hasSession?: boolean
  hasStart?: boolean
  hasEnd?: boolean
  isExpanded?: boolean
  datebreak?: boolean
  gap?: boolean
}

interface HoverSlice {
  time: Moment
  roomIndex: number
  room: Room
  duration: number
}

interface DragStartData {
  x: number
  y: number
  session: SessionDatum
  now: Moment
}

interface DragEventPayload {
  session: SessionDatum
  event: PointerEvent
}

const props = defineProps<{
  sessions: SessionDatum[]
  availabilities: {
    rooms?: Record<string, { start: string; end: string }[]>
    talks?: Record<string, { start: string; end: string }[]>
  }
  warnings: Record<string, { message: string }[]>
  start: Moment
  end: Moment
  rooms: Room[]
  currentDay: Moment | null
  draggedSession: SessionDatum | null
  density: 'compact' | 'default' | 'comfortable'
  timeDensityMinutes: number
  allowOverlap?: boolean
  isUnassigning?: boolean
}>()

const emit = defineEmits([
  'startDragging',
  'editSession',
  'deleteSession',
  'assignMembers',
  'unscheduleSession',
  'createSession',
  'rescheduleSession',
  'changeDay'
])

const talkSessionBindings = mode === 'talks' ? { allowUnschedule: true } : {}
const talkSessionListeners = mode === 'talks'
  ? { unscheduleSession: (session: SessionDatum) => emit('unscheduleSession', session) }
  : {}

const rootEl = ref<HTMLElement | null>(null)
const grid = ref<HTMLElement | null>(null)
const scrolledDay = ref<Moment | null>(null)
const hoverSlice = ref<HoverSlice | null>(null)
const expandedTimes = ref<Moment[]>([])
const gridOffset = ref(0)
const dragScrollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const dragStart = ref<DragStartData | null>(null)
const hiddenRooms = ref<Room[]>([])
const timesliceRefs = ref<HTMLElement[]>([])

let cachedGrid: {
  rooms: { left: number; right: number; room: Room; roomIndex: number }[]
  slices: { top: number; bottom: number; time: Moment }[]
} | null = null

watch(() => props.draggedSession, (val) => {
  if (!val) {
    hoverSlice.value = null
    cachedGrid = null
  }
})

watch(() => props.isUnassigning, (val) => {
  if (val) {
    hoverSlice.value = null
  }
})


function applyRoomFocusFromQuery() {
  const params = new URLSearchParams(window.location.search)
  const roomParam = params.get('room')
  if (!roomParam || !props.rooms?.length) return
  const focusId = String(roomParam)
  const focusRoom = props.rooms.find((room) => String(room.id) === focusId)
  if (!focusRoom) return
  hiddenRooms.value = props.rooms.filter((room) => room !== focusRoom)
}

watch(() => props.rooms, () => applyRoomFocusFromQuery(), { immediate: true })

let observer: IntersectionObserver | null = null
const layoutObservers: ResizeObserver[] = []
let windowResizeListener: (() => void) | null = null
let gridOffsetFrame: number | null = null

const refreshGridOffset = () => {
  cachedGrid = null
  if (grid.value) {
    gridOffset.value = grid.value.getBoundingClientRect().left
  }
}

const scheduleRefreshGridOffset = () => {
  cachedGrid = null
  if (gridOffsetFrame !== null) {
    return
  }
  gridOffsetFrame = requestAnimationFrame(() => {
    gridOffsetFrame = null
    refreshGridOffset()
  })
}

const observeElementResize = (element: HTMLElement | null) => {
  if (!element || typeof ResizeObserver === 'undefined') {
    return
  }
  const resizeObserver = new ResizeObserver(scheduleRefreshGridOffset)
  resizeObserver.observe(element)
  layoutObservers.push(resizeObserver)
}

const hasValidPosition = (session: SessionDatum): boolean => {
  return !!(session.room && session.start && session.end)
}

const getSliceName = (date: Moment): string => `slice-${date.format('MM-DD-HH-mm')}`

const hoverSliceLegal = computed(() => {
  if (!hoverSlice.value || !hoverSlice.value.room || !props.draggedSession) return false
  if (props.allowOverlap) return true
  const start = hoverSlice.value.time
  const end = hoverSlice.value.time.clone().add(props.draggedSession.duration, 'm')
  const sessionId = props.draggedSession.id
  const roomId = hoverSlice.value.room.id

  for (const session of props.sessions.filter(s => s.start)) {
    if (session.room.id === roomId && session.id !== sessionId) {
      if (
        session.start.isSame(start) ||
        session.end.isSame(end) ||
        session.start.isBetween(start, end) ||
        session.end.isBetween(start, end) ||
        start.isBetween(session.start, session.end) ||
        end.isBetween(session.start, session.end)
      ) return false
    }
  }
  return true
})

const timeslices = computed<Timeslice[]>(() => {
  const minimumSliceMins = props.timeDensityMinutes || 30
  const slices: Timeslice[] = []
  const slicesLookup: Record<string, Timeslice> = {}

  const pushSlice = (
    date: Moment,
    params: Partial<Pick<Timeslice, 'hasStart' | 'hasEnd' | 'hasSession' | 'isExpanded'>> = {}
  ) => {
    const name = getSliceName(date)
    let slice = slicesLookup[name]
    if (slice) {
      slice.hasSession = slice.hasSession || !!params.hasSession
      slice.hasStart = slice.hasStart || !!params.hasStart
      slice.hasEnd = slice.hasEnd || !!params.hasEnd
      slice.isExpanded = slice.isExpanded || !!params.isExpanded
    } else {
      slice = {
        date,
        name,
        hasSession: !!params.hasSession,
        hasStart: !!params.hasStart,
        hasEnd: !!params.hasEnd,
        isExpanded: !!params.isExpanded,
        datebreak: date.isSame(date.clone().startOf('day')),
      }
      slices.push(slice)
      slicesLookup[name] = slice
    }
  }

  const fillHalfHours = (start: Moment, end: Moment, { hasSession }: { hasSession?: boolean } = {}) => {
    let mins = end.diff(start, 'minutes')
    const startingMins = minimumSliceMins - (start.minute() % minimumSliceMins)
    const halfHourSlices: Moment[] = []

    if (startingMins && startingMins !== minimumSliceMins) {
      halfHourSlices.push(start.clone().add(startingMins, 'minutes'))
      mins -= startingMins
    }

    const endingMins = end.minute() % minimumSliceMins

    for (let i = 1; i <= mins / minimumSliceMins; i++) {
      const sliceDate = start.clone().add(startingMins + minimumSliceMins * i, 'minutes')
      if (sliceDate.isAfter(end)) break
      halfHourSlices.push(sliceDate)
    }

    if (endingMins) {
      halfHourSlices.push(end.clone().subtract(endingMins, 'minutes'))
    }

    const lastSlice = halfHourSlices.pop()
    halfHourSlices.forEach(slice => pushSlice(slice!, { hasSession }))
    if (lastSlice) pushSlice(lastSlice)
  }

  for (const session of props.sessions) {
    const lastSlice = slices[slices.length - 1]

    if (!lastSlice) {
      pushSlice(session.start.clone().startOf('day'))
    } else if (session.start.isAfter(lastSlice.date, 'minutes')) {
      fillHalfHours(lastSlice.date, session.start)
    }

    pushSlice(session.start, { hasStart: true, hasSession: true })
    pushSlice(session.end, { hasEnd: true })
    fillHalfHours(session.start, session.end, { hasSession: true })
  }

  for (const slice of expandedTimes.value) {
    pushSlice(slice, { isExpanded: true })
  }

  fillHalfHours(props.start, props.end)

  const sliceIsFraction = (slice?: Timeslice): boolean => {
    if (!slice) return false
    return slice.date.minutes() % minimumSliceMins !== 0
  }

  const sliceShouldDisplay = (slice?: Timeslice, index?: number): boolean => {
    if (!slice || index === undefined) return false
    if (slice.datebreak && slice.date.isAfter(props.end)) return false
    if (slice.hasSession || slice.datebreak || slice.hasStart || slice.hasEnd || slice.isExpanded) return true
    if (slice.date.hour() >= 9 && slice.date.hour() < 19) return true

    const prevSlice = slices[index - 1]
    const nextSlice = slices[index + 1]

    if (sliceIsFraction(slice)) return true
    if (
      ((prevSlice?.hasSession || (prevSlice as any)?.hasBreak || prevSlice?.hasEnd) && sliceIsFraction(prevSlice)) ||
      ((nextSlice?.hasSession || (nextSlice as any)?.hasBreak) && sliceIsFraction(nextSlice)) ||
      ((!nextSlice?.hasSession || !(nextSlice as any)?.hasBreak) && (slice.hasSession || (slice as any).hasBreak) && sliceIsFraction(nextSlice))
    ) return true
    if ((prevSlice as any)?.hasBreak && (slice as any).hasBreak) return false
    return false
  }

  slices.sort((a, b) => a.date.diff(b.date))
  const compactedSlices: Timeslice[] = []

  for (const [index, slice] of slices.entries()) {
    if (sliceShouldDisplay(slice, index)) {
      compactedSlices.push(slice)
      continue
    }

    const prevSlice = slices[index - 1]
    if (prevSlice && sliceShouldDisplay(prevSlice, index - 1) && !prevSlice.datebreak) {
      prevSlice.gap = true
    }
  }

  if (compactedSlices.length && compactedSlices[compactedSlices.length - 1].gap) {
    compactedSlices[compactedSlices.length - 1].gap = false
  }

  return compactedSlices
})

const oddTimeslices = computed<Moment[]>(() => {
  const minimumSliceMins = props.timeDensityMinutes || 30
  const result: Moment[] = []
  props.sessions.forEach(session => {
    if (session.start.minute() % minimumSliceMins !== 0) result.push(session.start)
    if (session.end.minute() % minimumSliceMins !== 0) result.push(session.end)
  })
  // Remove duplicates by stringifying dates (safe as moment objects)
  return [...new Set(result.map(m => m.format()))].map(f => moment(f))
})

const visibleTimeslices = computed<Timeslice[]>(() => {
  const minimumSliceMins = props.timeDensityMinutes || 30
  return timeslices.value.filter(slice =>
    slice.date.minute() % minimumSliceMins === 0 ||
    expandedTimes.value.some(et => et.isSame(slice.date)) ||
    oddTimeslices.value.some(ot => ot.isSame(slice.date))
  )
})

const densityScale = computed(() => {
  if (props.density === 'compact') return 0.65
  if (props.density === 'comfortable') return 1.4
  return 1
})

const shiftMinColWidth = computed(() => '320px')

const shiftColumnLayout = computed(() => {
  if (!props.allowOverlap) return new Map()
  return computeShiftColumnLayout(visibleRooms.value as any[], props.sessions as any[])
})

const shiftTrackMap = computed(() => {
  if (!props.allowOverlap) return new Map()
  const merged = new Map<number | string, number>()
  for (const room of visibleRooms.value) {
    const tracks = assignRoomTracks(room.id, props.sessions as any[])
    for (const [id, track] of tracks) merged.set(id, track)
  }
  return merged
})

const gridStyle = computed(() => {
  const scale = densityScale.value
  const minimumSliceMins = props.timeDensityMinutes || 30
  const baseSliceHeight = 60 * (minimumSliceMins / 30)
  let rows = `[header] ${Math.round(52 * scale)}px `
  rows += timeslices.value.map((slice, index) => {
    const next = timeslices.value[index + 1]
    let height = baseSliceHeight
    if (slice.gap) {
      height = 100 * (minimumSliceMins / 30)
    } else if (slice.datebreak) {
      height = Math.max(52, baseSliceHeight)
    } else if (next) {
      height = Math.min(baseSliceHeight, next.date.diff(slice.date, 'minutes') * 2)
    }
    height = Math.round(height * scale)
    return `[${slice.name}] minmax(${height}px, auto)`
  }).join(' ')

  if (props.allowOverlap && visibleRooms.value.length) {
    return {
      'grid-template-columns': buildShiftGridTemplateColumns(visibleRooms.value, props.sessions as any[], shiftMinColWidth.value),
      'grid-template-rows': rows,
    }
  }

  return {
    '--total-rooms': visibleRooms.value.length.toString(),
    'grid-template-rows': rows,
  }
})

const gridClasses = computed(() => {
  const result: string[] = []
  if (props.draggedSession) result.push('is-dragging')
  if (hoverSlice.value && props.draggedSession && !hoverSliceLegal.value) result.push('illegal-hover')
  return result
})

const availabilitySlices = computed<Availability[]>(() => {
  const avails: Availability[] = []
  if (!visibleTimeslices.value.length) return avails
  const earliestStart = visibleTimeslices.value[0].date
  const latestEnd = visibleTimeslices.value[visibleTimeslices.value.length - 1].date
  const draggedAvails: Array<{ start: Moment; end: Moment }> = []

  if (props.draggedSession && props.availabilities.talks?.[props.draggedSession.id as any]) {
    for (const avail of props.availabilities.talks[props.draggedSession.id as any]) {
      draggedAvails.push({
        start: moment(avail.start),
        end: moment(avail.end),
      })
    }
  }

  for (const room of visibleRooms.value) {
    if (!props.availabilities.rooms?.[room.id] || !props.availabilities.rooms[room.id].length) {
      avails.push({ room, start: earliestStart, end: latestEnd })
    } else {
      for (const avail of props.availabilities.rooms[room.id]) {
        avails.push({
          room,
          start: moment(avail.start),
          end: moment(avail.end),
        })
      }
    }

    for (const avail of draggedAvails) {
      avails.push({
        room,
        start: avail.start,
        end: avail.end,
        active: true,
      })
    }
  }

  return avails
})

const scrollParent = computed<HTMLElement | null>(() => rootEl.value?.parentElement ?? null)

const staticOffsetTop = computed(() => {
  if (!rootEl.value?.parentElement) return 0
  const rect = rootEl.value.parentElement.getBoundingClientRect()
  return rect.top
})

const visibleRooms = computed(() => {
  return props.rooms.filter(room => !hiddenRooms.value.includes(room))
})

watch([visibleRooms, visibleTimeslices, gridStyle], () => {
  cachedGrid = null
})

const visibleSessions = computed(() => {
  return props.sessions.filter(session => !hiddenRooms.value.includes(session.room))
})

const visibleAvailabilities = computed(() => {
  const result: Availability[] = []
  for (const avail of availabilitySlices.value) {
    if (hiddenRooms.value.includes(avail.room)) continue
    const start = visibleTimeslices.value.find(slice => slice.date.isSameOrAfter(avail.start))
    const end = visibleTimeslices.value.find(slice => slice.date.isSameOrAfter(avail.end))
    if (!start || !end) continue
    result.push({
      room: avail.room,
      start: start.date,
      end: end.date,
      active: avail.active,
    })
  }
  return result
})

const setTimesliceRef = (el: HTMLElement | null) => {
  if (el && !timesliceRefs.value.includes(el)) timesliceRefs.value.push(el)
}

const startDragging = ({ session, event }: DragEventPayload) => {
  refreshGridOffset()
  dragStart.value = {
    x: event.clientX,
    y: event.clientY,
    session,
    now: moment(),
  }
  emit('startDragging', { event, session })
}

const stopDragging = (event: PointerEvent) => {
  if (dragStart.value && props.draggedSession) {
    const distance = Math.abs(dragStart.value.x - event.clientX) + Math.abs(dragStart.value.y - event.clientY)
    const timeDiff = moment().diff(dragStart.value.now, 'ms')
    const session = dragStart.value.session
    dragStart.value = null

    if (distance < 6 && timeDiff < 300) {
      emit('editSession', session)
      return
    }
  }

  if (!props.draggedSession) return
  if (pointerRaf !== null) {
    cancelAnimationFrame(pointerRaf)
    pointerRaf = null
  }
  updateHoverSlice(event)
  if (!hoverSlice.value || !hoverSliceLegal.value) return
  const start = hoverSlice.value.time
  const end = hoverSlice.value.time.clone().add(props.draggedSession.duration, 'm')

  if (!props.draggedSession.id) {
    // Create a new session object with the correct room format
    const newSessionData: SessionDatum = {
      ...props.draggedSession,
      start: moment(start.format()),
      end: moment(end.format()),
      room: { 
        id: hoverSlice.value.room.id,
        name: hoverSlice.value.room.name
      }
    }
    
    emit('createSession', { session: newSessionData })
  } else {
    emit('rescheduleSession', {
      session: props.draggedSession,
      start: start.format(),
      end: end.format(),
      room: hoverSlice.value.room,
    })
  }
  cachedGrid = null
  hoverSlice.value = null
}

const expandTimeslice = (slice: Timeslice) => {
  cachedGrid = null
  const index = visibleTimeslices.value.indexOf(slice)
  if (index + 1 >= visibleTimeslices.value.length) {
    const minimumSliceMins = props.timeDensityMinutes || 30
    expandedTimes.value.push(slice.date.clone().add(Math.min(5, minimumSliceMins), 'm'))
  } else {
    const end = visibleTimeslices.value[index + 1].date.clone()
    const minimumSliceMins = props.timeDensityMinutes || 30
    const interval = end.diff(slice.date, 'minutes') <= minimumSliceMins ? Math.min(5, minimumSliceMins) : minimumSliceMins
    const time = slice.date.clone().add(interval, 'm')
    while (time.isBefore(end)) {
      expandedTimes.value.push(time.clone())
      time.add(interval, 'm')
    }
  }
  expandedTimes.value = [...new Set(expandedTimes.value.map(d => d.valueOf()))].map(v => moment(v))
}

const getTimeAndRoomFromPoint = (clientX: number, clientY: number) => {
  if (!rootEl.value || props.isUnassigning) return null

  if (!cachedGrid) {
    const roomEls = rootEl.value.querySelectorAll('.grid > .room')
    const rooms = []
    for (let i = 1; i < roomEls.length; i++) {
      const rect = roomEls[i].getBoundingClientRect()
      if (i - 1 < visibleRooms.value.length) {
        rooms.push({ left: rect.left, right: rect.right, room: visibleRooms.value[i - 1], roomIndex: i - 1 })
      }
    }
    const timesliceEls = rootEl.value.querySelectorAll('.grid > .timeslice')
    const slices = []
    for (let i = 0; i < timesliceEls.length; i++) {
      const el = timesliceEls[i] as HTMLElement
      if (!el.dataset.slice) continue
      const rect = el.getBoundingClientRect()
      const nextRect = timesliceEls[i + 1]?.getBoundingClientRect()
      slices.push({ top: rect.top, bottom: nextRect ? nextRect.top : rect.bottom, time: moment(el.dataset.slice) })
    }
    if (!rooms.length || !slices.length) return null
    cachedGrid = { rooms, slices }
  }

  const room = cachedGrid.rooms.find((r) => clientX >= r.left && clientX < r.right)
  if (!room) return null

  const slice = cachedGrid.slices.find((s) => clientY >= s.top && clientY < s.bottom)
  if (!slice) return null

  return { time: slice.time, room: room.room, roomIndex: room.roomIndex }
}

let lastPlacementTime = 0

const tryPlaceSessionAtPoint = (clientX: number, clientY: number): boolean => {
  if (!props.draggedSession) return false
  const now = Date.now()
  if (now - lastPlacementTime < 100) return false // prevent duplicate triggers
  lastPlacementTime = now

  const slot = getTimeAndRoomFromPoint(clientX, clientY)
  if (!slot || !slot.room || !slot.time) return false

  const start = slot.time
  const end = slot.time.clone().add(props.draggedSession.duration, 'm')

  if (!props.draggedSession.id) {
    emit('createSession', {
      session: {
        ...props.draggedSession,
        start: moment(start.format()),
        end: moment(end.format()),
        room: {
          id: slot.room.id,
          name: slot.room.name
        }
      }
    })
  } else {
    emit('rescheduleSession', {
      session: props.draggedSession,
      start: start.format(),
      end: end.format(),
      room: slot.room,
    })
  }
  hoverSlice.value = null
  return true
}

const onGridClick = (event: MouseEvent) => {
  if (!props.draggedSession) return
  const target = event.target as HTMLElement
  if (target && target.closest('.c-linear-schedule-session:not(.clone)')) {
    return
  }
  tryPlaceSessionAtPoint(event.clientX, event.clientY)
}

const updateHoverSlice = (e: PointerEvent) => {
  if (!props.draggedSession || props.isUnassigning) {
    hoverSlice.value = null
    return
  }

  if (dragStart.value) {
    dragStart.value = { ...dragStart.value, y: e.clientY }
  }

  if (!dragScrollTimer.value) {
    dragScrollTimer.value = setInterval(dragOnScroll, 100)
  }

  const slot = getTimeAndRoomFromPoint(e.clientX, e.clientY)
  if (!slot) {
    hoverSlice.value = null
    return
  }

  const targetSlot: HoverSlice = {
    time: slot.time,
    roomIndex: slot.roomIndex,
    room: slot.room,
    duration: props.draggedSession.duration,
  }

  if (
    hoverSlice.value &&
    hoverSlice.value.room?.id === targetSlot.room?.id &&
    hoverSlice.value.time.isSame(targetSlot.time)
  ) {
    return
  }

  hoverSlice.value = targetSlot
}

let pointerRaf: number | null = null
let lastPointerEvent: PointerEvent | null = null
const onDocPointerMove = (e: PointerEvent) => {
  if (props.draggedSession && e.isPrimary) {
    lastPointerEvent = e
    if (pointerRaf !== null) return
    pointerRaf = requestAnimationFrame(() => {
      pointerRaf = null
      if (props.draggedSession && lastPointerEvent) updateHoverSlice(lastPointerEvent)
    })
  }
}

const getHoverSliceStyle = (): Record<string, string> | undefined => {
  if (!hoverSlice.value || !props.draggedSession) return undefined
  let col = hoverSlice.value.roomIndex + 2
  if (props.allowOverlap && hoverSlice.value.room) {
    const layout = shiftColumnLayout.value.get(hoverSlice.value.room.id)
    if (layout) col = layout.colStart
  }
  const startSliceName = getSliceName(hoverSlice.value.time)
  const scale = densityScale.value
  const durationPx = Math.round(props.draggedSession.duration * 2 * scale)
  const baseMinHeight = props.density === 'compact' ? 48 : (props.density === 'comfortable' ? 112 : 88)
  const minHeightPx = Math.max(baseMinHeight, durationPx - 8)

  return {
    'grid-row-start': startSliceName,
    'grid-row-end': 'auto',
    'grid-column': `${col} / ${col + 1}`,
    'min-height': `${minHeightPx}px`,
  }
}

const getSessionWarnings = (session: SessionDatum): { message: string }[] => {
  return session.code ? (props.warnings[session.code] || []) : []
}

const getOverlapGroup = (session: SessionDatum | Availability): { index: number; total: number } => {
  if (!session.room || !session.start || !session.end) return { index: 0, total: 1 }
  if (!('id' in session)) return { index: 0, total: 1 }

  const overlapping = visibleSessions.value.filter(s => {
    if (s.id === (session as SessionDatum).id) return true
    if (!s.room || !s.start || !s.end) return false
    if (s.room.id !== session.room.id) return false
    return s.start.isBefore(session.end) && s.end.isAfter(session.start)
  })

  return { index: 0, total: overlapping.length }
}

const getSessionStyle = (session: SessionDatum | Availability): Record<string, string | number> => {
  if (!session.room || !session.start) return {}
  const roomIndex = visibleRooms.value.indexOf(session.room)

  if (props.allowOverlap) {
    const { total } = getOverlapGroup(session)
    if (total > 1 && 'id' in session) {
      const roomLayout = shiftColumnLayout.value.get(session.room.id)
      if (roomLayout && roomLayout.colSpan > 1) {
        const track = shiftTrackMap.value.get((session as any).id)
        if (track != null) {
          const subCol = roomLayout.colStart + track
          return {
            'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
            'grid-column': `${subCol} / ${subCol + 1}`,
          }
        }
      }
    }
    const layout = shiftColumnLayout.value.get(session.room.id)
    if (layout) {
      if (!('id' in session)) {
        return {
          'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
          'grid-column': `${layout.colStart} / ${layout.colStart + layout.colSpan}`,
        }
      }
      return {
        'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
        'grid-column': layout.colStart.toString(),
      }
    }
    const col = roomIndex > -1 ? roomIndex + 2 : 1
    return {
      'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
      'grid-column': col.toString(),
    }
  }

  return {
    'grid-row': `${getSliceName(session.start)} / ${getSliceName(session.end)}`,
    'grid-column': roomIndex > -1 ? (roomIndex + 2).toString() : '',
  }
}


const getRoomHeaderStyle = (room: { id: number | string }, fallbackIndex: number): Record<string, string> => {
  if (!props.allowOverlap) {
    return { 'grid-area': `1 / ${fallbackIndex + 2} / auto / auto` }
  }
  const roomLayout = shiftColumnLayout.value.get(room.id)
  if (!roomLayout) return { 'grid-area': `1 / ${fallbackIndex + 2} / auto / auto` }
  return {
    'grid-row': '1 / auto',
    'grid-column': `${roomLayout.colStart} / ${roomLayout.colStart + roomLayout.colSpan}`,
  }
}

const getSliceClasses = (slice: Timeslice): Record<string, boolean> => ({
  datebreak: slice.datebreak || false,
  gap: slice.gap || false,
  expandable: isSliceExpandable(slice),
})

const isSliceExpandable = (slice: Timeslice): boolean => {
  const index = visibleTimeslices.value.indexOf(slice)
  if (index + 1 === visibleTimeslices.value.length) return false
  const nextSlice = visibleTimeslices.value[index + 1]
  return nextSlice.date.diff(slice.date, 'minutes') > 5
}

const getSliceStyle = (slice: Timeslice): Record<string, string> => {
  return { 'grid-area': `${slice.name} / 1 / auto / auto` }
}

const getSliceLabel = (slice: Timeslice): string => {
  if (slice.datebreak) return slice.date.format('ddd[\n]DD. MMM')
  return slice.date.format('LT')
}

let isScrollDayUpdate = false

const getStickyHeaderClearance = (): number => {
  const roomEl = rootEl.value?.querySelector('.room')
  const controlsEl = rootEl.value?.parentElement?.querySelector('.schedule-controls')
  return (roomEl?.getBoundingClientRect().height || 52) + (controlsEl?.getBoundingClientRect().height || 48)
}

const scrollToDayStart = (day: Moment | null) => {
  if (!day) return
  const dayStr = day.format('YYYY-MM-DD')
  const el = timesliceRefs.value.find((el) => {
    if (!el.dataset?.slice || !el.classList.contains('datebreak')) return false
    return moment.parseZone(el.dataset.slice).format('YYYY-MM-DD') === dayStr
  })
  if (!el || !scrollParent.value) return
  const clearance = getStickyHeaderClearance()
  const rect = el.getBoundingClientRect()
  const parentRect = scrollParent.value.getBoundingClientRect()
  const delta = rect.top - parentRect.top - clearance
  scrollParent.value.scrollTop += delta
  scrolledDay.value = day
}

const onScroll = () => {
  cachedGrid = null
}

const scrollBy = (offset: number) => {
  if (scrollParent.value) {
    scrollParent.value.scrollBy({ top: offset, behavior: 'smooth' })
    cachedGrid = null
  }
}

const dragOnScroll = () => {
  if (!props.draggedSession) {
    if (dragScrollTimer.value) {
      clearInterval(dragScrollTimer.value)
      dragScrollTimer.value = null
    }
    return
  }

  const event = dragStart.value?.session && dragStart.value.session ? dragStart.value.session : null
  if (!dragStart.value) return

  const yPos = dragStart.value.y - staticOffsetTop.value
  const parentHeight = scrollParent.value?.clientHeight ?? 0

  if (yPos < 160) {
    scrollBy(yPos < 90 ? -200 : -75)
  } else if (yPos > parentHeight - 100) {
    scrollBy(yPos > parentHeight - 40 ? 200 : 75)
  }
}

const onIntersect = (entries: IntersectionObserverEntry[]) => {
  const intersecting = entries.filter((entry) => entry.isIntersecting)
  if (!intersecting.length) return
  const entry = intersecting
    .slice()
    .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]
  if (!entry) return
  const dayStr = (entry.target as HTMLElement).dataset?.slice
  if (!dayStr) return
  const day = moment.parseZone(dayStr).startOf('day')
  if (scrolledDay.value && day.isSame(scrolledDay.value, 'day')) return
  scrolledDay.value = day
  // Only update the active day indicator — don't trigger a scroll jump.
  // scrollToDayStart is only called from toolbar clicks.
  isScrollDayUpdate = true
  emit('changeDay', day)
}

watch(() => props.currentDay, (day) => {
  // Only scroll when triggered by toolbar click, not by scroll-based observer
  if (isScrollDayUpdate) {
    isScrollDayUpdate = false
    return
  }
  scrollToDayStart(day)
})

onMounted(async () => {
  await nextTick()

  refreshGridOffset()
  observeElementResize(rootEl.value)
  const layoutRoot = rootEl.value?.closest('#page-content') ?? rootEl.value?.closest('.pretalx-schedule')
  if (layoutRoot instanceof HTMLElement && layoutRoot !== rootEl.value) {
    observeElementResize(layoutRoot)
  }
  windowResizeListener = () => {
    cachedGrid = null
    scheduleRefreshGridOffset()
  }
  window.addEventListener('resize', windowResizeListener)

  // Listen on document level so touch drags (where pointer is captured elsewhere) work
  document.addEventListener('pointermove', onDocPointerMove)

  observer = new IntersectionObserver(onIntersect, {
    root: scrollParent.value,
    rootMargin: '-45% 0px',
  })

  timesliceRefs.value.forEach(el => {
    if (!el.dataset?.slice || !el.classList.contains('datebreak')) return
    observer?.observe(el)
  })
  scrollParent.value?.addEventListener('scroll', onScroll, { passive: true })
})

onUnmounted(() => {
  timesliceRefs.value = []
  document.removeEventListener('pointermove', onDocPointerMove)
  scrollParent.value?.removeEventListener('scroll', onScroll)
  if (pointerRaf !== null) {
    cancelAnimationFrame(pointerRaf)
    pointerRaf = null
  }
  cachedGrid = null
  if (gridOffsetFrame !== null) {
    cancelAnimationFrame(gridOffsetFrame)
    gridOffsetFrame = null
  }
  layoutObservers.forEach((resizeObserver) => resizeObserver.disconnect())
  layoutObservers.length = 0
  if (windowResizeListener) {
    window.removeEventListener('resize', windowResizeListener)
    windowResizeListener = null
  }
  if (observer) {
    observer.disconnect()
    observer = null
  }

  if (dragScrollTimer.value) {
    clearInterval(dragScrollTimer.value)
    dragScrollTimer.value = null
  }
})
</script>

<style lang="stylus">
.c-grid-schedule
	flex: auto
	min-height: auto
	display: flex
	flex-direction: column
	.grid
		display: grid
		grid-template-columns: 78px repeat(var(--total-rooms), minmax(300px, 1fr)) auto
		@media (max-width: 767px)
			grid-template-columns: 78px repeat(var(--total-rooms), minmax(260px, 1fr)) auto
		position: relative
		min-width: min-content
		min-height: auto
		&.illegal-hover
			cursor: not-allowed
			.c-linear-schedule-session
				cursor: not-allowed
		> .room
			position: sticky
			top: calc(36px)
			display: flex
			justify-content: center
			align-items: center
			font-size: 13px
			font-weight: 600
			background-color: $clr-white
			border-bottom: 1px solid $clr-dividers-light
			z-index: 40
			min-width: 300px
			box-sizing: border-box
			padding: 6px 10px
			@media (max-width: 767px)
				min-width: 260px
			&:first-child
				left: 0
				top: calc(36px)
				z-index: 45
				min-width: 78px
				width: 78px
				padding: 0
				background-color: $clr-white

			.room-name
				overflow: hidden
				text-overflow: ellipsis
				white-space: nowrap
				min-width: 0
				padding: 0 4px

			.hide-room
				color: $clr-secondary-text-light
				font-size: 14px
				margin-inline-start: 16px
				cursor: pointer
				padding: 4px 8px
				border-radius: 4px

				&:hover
					background-color: $clr-grey-200

		.c-linear-schedule-session
			min-width: 0
			z-index: 10
			transition: padding 0.2s ease, font-size 0.2s ease
			&.placing-preview
				position: absolute
				top: 4px
				left: 8px
				right: 8px
				margin: 0
				min-width: 0
				opacity: 0.88
				pointer-events: none
				transition: none
				box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18), 0 2px 6px rgba(0, 0, 0, 0.08)
				border-radius: 6px
				filter: brightness(0.98)
				z-index: 100
	.timeslice
		color: $clr-secondary-text-light
		padding: 8px 10px 0 10px
		white-space: nowrap
		position: sticky
		left: 0
		width: 78px
		min-width: 78px
		box-sizing: border-box
		text-align: center
		background-color: $clr-grey-50
		border-top: 1px solid $clr-dividers-light
		z-index: 25
		transition: padding 0.2s ease, font-size 0.2s ease
		.expand
			display: none
		&.datebreak
			font-weight: 600
			border-top: 3px solid $clr-dividers-light
			white-space: pre
			display: flex
			flex-direction: column
			justify-content: center
			align-items: center
			line-height: 1.3
			padding: 4px
		&.expandable:hover
			background-color: $clr-grey-200
			cursor: pointer
			.expand
				display: block
				width: 20px
				margin: 4px auto
				path
					fill: $clr-grey-500

	// Density: compact
	&.density-compact
		.timeslice
			padding: 4px 6px 0 6px
			font-size: 12px
		.grid-viewport .grid
			.c-linear-schedule-session, .break
				margin: 4px 3px
				min-height: 48px
				font-size: 12px
		.c-linear-schedule-session
			min-height: 48px
			font-size: 12px
			.time-box
				width: 50px
				padding: 4px 4px 2px 4px
				.start
					font-size: 13px
					margin-bottom: 4px
					.duration
						font-size: 11px
			.info
				padding: 4px 6px
				.title
					font-size: 13px
					margin-bottom: 2px
				.session-type
					font-size: 10px
					margin-bottom: 2px
				.speakers
					font-size: 11px
				.bottom-info
					.track
						font-size: 10px
		.grid > .room
			font-size: 14px
			padding: 4px

	// Density: comfortable
	&.density-comfortable
		.timeslice
			padding: 12px 14px 0 14px
			font-size: 15px
		.grid-viewport .grid
			.c-linear-schedule-session, .break
				margin: 12px 9px
				min-height: 120px
				font-size: 15px
		.c-linear-schedule-session
			min-height: 120px
			font-size: 15px
			.time-box
				width: 72px
				padding: 14px 10px 8px 10px
				.start
					font-size: 18px
					margin-bottom: 10px
					.duration
						font-size: 14px
			.info
				padding: 12px
				.title
					font-size: 18px
					margin-bottom: 4px
				.session-type
					font-size: 12px
					margin-bottom: 4px
				.speakers
					font-size: 14px
				.bottom-info
					.track
						font-size: 13px
		.grid > .room
			font-size: 20px
			padding: 12px

	.timeseparator
		height: 1px
		background-color: $clr-dividers-light
		position: absolute
		// transform: translate(-16px, -8px)
		width: 100%
		&.datebreak
			height: 3px

.availability
	background-color: white
	pointer-events: none
	&.active
		background-color: rgba(56, 158, 119, 0.1)
#hidden-rooms
	position: fixed
	z-index: 500
	bottom: 16px
	right: 16px
	min-width: 220px
	max-width: 300px
	background-color: $clr-white
	border: 1px solid #e2e8f0
	border-radius: 8px
	box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12)
	overflow: hidden
	font-size: 13px

	.hidden-rooms-header
		display: flex
		align-items: center
		gap: 6px
		padding: 8px 12px
		background-color: #f8fafc
		border-bottom: 1px solid #e2e8f0
		color: #334155
		font-weight: 600
		font-size: 13px
		.fa-eye-slash
			color: #64748b
			font-size: 12px
		.hidden-rooms-title
			flex: 1
		.hidden-rooms-badge
			background-color: #e2e8f0
			color: #475569
			font-size: 11px
			font-weight: 700
			padding: 2px 6px
			border-radius: 10px

	.room-list
		padding: 4px
		max-height: 200px
		overflow-y: auto

	.room-entry
		display: flex
		justify-content: space-between
		align-items: center
		padding: 6px 10px
		border-radius: 6px
		cursor: pointer
		transition: background-color 0.15s ease
		color: #1e293b
		font-size: 12px
		font-weight: 500
		&:hover
			background-color: #f1f5f9
			.show-room-btn
				color: var(--color-primary, #2185d0)
		.room-name
			flex: 1
			overflow: hidden
			text-overflow: ellipsis
			white-space: nowrap
			padding-right: 8px
		.show-room-btn
			display: flex
			align-items: center
			justify-content: center
			width: 24px
			height: 24px
			padding: 0
			border: none
			background: transparent
			color: #64748b
			cursor: pointer
			border-radius: 4px
			transition: all 0.15s ease
			&:hover
				background-color: #e2e8f0
				color: var(--color-primary, #2185d0)
			.fa
				font-size: 12px

html[dir="rtl"],
html.rtl
	.c-grid-schedule
		.grid > .room:first-child
			right: 0
			left: auto
			border-left: 1px solid $clr-dividers-light
			border-right: none
		.timeslice
			right: 0
			left: auto
			border-left: 1px solid $clr-dividers-light
			border-right: none
	#hidden-rooms
		left: 16px
		right: auto
</style>
