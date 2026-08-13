export type Mode = 'talks' | 'shifts' | 'public-shifts'

export type SessionKind = 'talk' | 'break' | 'shift'

export interface Capabilities {
  canDrag: boolean
  canCreateBreak: boolean
  canEdit: boolean
  canDelete: boolean
  canAssignMembers: boolean
  canEditRoles: boolean
  showSpeakers: boolean
  showTracks: boolean
  showRoles: boolean
  showClaimUI: boolean
  showSubmissionLinks: boolean
  allowOverlap: boolean
}

export interface ApiEndpoints {
  talks: string
  availabilities: string
  warnings: string
  members: string
  assignments: string
}

export interface ApiConfig {
  baseUrl: string
  endpoints: ApiEndpoints
}
