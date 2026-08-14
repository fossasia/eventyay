import type { Mode, Capabilities, ApiConfig, SessionKind } from './types'

export type { Mode, Capabilities, ApiConfig, SessionKind }

const basePath = process.env.BASE_PATH || ''

function getDataAttribute(attr: string): string {
  if (typeof window === 'undefined') return ''
  const el = document.querySelector('#app') as HTMLElement | null
  return el?.dataset?.[attr] ?? ''
}

export function resolveMode(): Mode {
  const dataMode = getDataAttribute('mode')
  if (dataMode === 'public-shifts') return 'public-shifts'
  if (dataMode === 'shifts') return 'shifts'
  if (typeof window !== 'undefined' && window.location.pathname.includes('/teamshifts/')) {
    return 'shifts'
  }
  return 'talks'
}

export function getCapabilities(mode?: Mode): Capabilities {
  const m = mode ?? resolveMode()
  switch (m) {
    case 'public-shifts':
      return {
        canDrag: false,
        canCreateBreak: false,
        canEdit: false,
        canDelete: false,
        canAssignMembers: false,
        canEditRoles: false,
        showSpeakers: false,
        showTracks: false,
        showRoles: true,
        showClaimUI: true,
        showSubmissionLinks: false,
        allowOverlap: true,
      }
    case 'shifts':
      return {
        canDrag: true,
        canCreateBreak: false,
        canEdit: true,
        canDelete: true,
        canAssignMembers: true,
        canEditRoles: true,
        showSpeakers: false,
        showTracks: false,
        showRoles: true,
        showClaimUI: false,
        showSubmissionLinks: false,
        allowOverlap: true,
      }
    case 'talks':
    default:
      return {
        canDrag: true,
        canCreateBreak: true,
        canEdit: true,
        canDelete: true,
        canAssignMembers: false,
        canEditRoles: false,
        showSpeakers: true,
        showTracks: true,
        showRoles: false,
        showClaimUI: false,
        showSubmissionLinks: true,
        allowOverlap: false,
      }
  }
}

export function getApiConfig(mode?: Mode): ApiConfig {
  const m = mode ?? resolveMode()

  if (m === 'public-shifts') {
    const match = window.location.pathname.match(/\/([^/]+)\/([^/]+)\/teamshifts\//)
    if (!match) {
      throw new Error('Public shift schedule must be loaded under /<organizer>/<event>/teamshifts/')
    }
    const baseUrl = `${basePath}/${match[1]}/${match[2]}/teamshifts`
    return {
      baseUrl,
      endpoints: {
        talks: '/shifts/api/',
        availabilities: '/schedule/api/availabilities/',
        warnings: '/schedule/api/warnings/',
        members: '/schedule/api/members/',
        assignments: '/schedule/api/assignments/',
      },
    }
  }

  const match = window.location.pathname.match(/\/event\/([^/]+)\/([^/]+)/)
  if (!match) {
    throw new Error('Schedule editor must be loaded under /orga/event/<organizer>/<event>/ or /teamshifts/event/<organizer>/<event>/')
  }

  const prefix = m === 'shifts' ? '/teamshifts' : '/orga'
  const baseUrl = `${basePath}${prefix}/event/${match[1]}/${match[2]}`

  if (m === 'shifts') {
    return {
      baseUrl,
      endpoints: {
        talks: '/schedule/api/shifts/',
        availabilities: '/schedule/api/availabilities/',
        warnings: '/schedule/api/warnings/',
        members: '/schedule/api/members/',
        assignments: '/schedule/api/assignments/',
      },
    }
  }

  return {
    baseUrl,
    endpoints: {
      talks: '/schedule/api/talks/',
      availabilities: '/schedule/api/availabilities/',
      warnings: '/schedule/api/warnings/',
      members: '',
      assignments: '',
    },
  }
}

export function getClaimedShiftIds(): Set<number> {
  const raw = getDataAttribute('claimedShifts')
  if (!raw) return new Set()
  try {
    return new Set(JSON.parse(raw) as number[])
  } catch {
    return new Set()
  }
}

export function getCsrfToken(): string {
  return getDataAttribute('csrfToken')
}

export function getClaimBaseUrl(): string {
  return getDataAttribute('claimBaseUrl')
}

export function resolveSessionKind(mode: Mode, session: { code?: string | null }): SessionKind {
  if (mode === 'shifts' || mode === 'public-shifts') return 'shift'
  if (session.code == null) return 'break'
  return 'talk'
}
