import {
  ScheduleSchema,
  AvailabilitySchema,
  WarningsSchema,
  TalkSchema,
  type Talk,
  type Schedule,
  type Availability,
  type Warnings,
} from './schemas'
import moment, { type Moment } from 'moment'
import {
  resolveMode,
  getApiConfig,
  getCsrfToken,
} from './teamshifts-adapter'

export { resolveMode as getAppMode } from './teamshifts-adapter'
export { getClaimedShiftIds, getCsrfToken, getClaimBaseUrl } from './teamshifts-adapter'

const calculateDuration = (start?: string, end?: string): number | undefined => {
  if (!start || !end) return undefined
  try {
    const startTime = new Date(start).getTime()
    const endTime = new Date(end).getTime()
    return (endTime - startTime) / (1000 * 60)
  } catch {
    return undefined
  }
}

interface TalkPayload {
  id?: number
  code?: string
  title?: string | Record<string, string>
  description?: string | Record<string, string>
  room?: string | number | { id: string | number }
  start?: string
  end?: string
  duration?: number
  role?: string | number
  capacity?: number
  roles?: { id: string | number; capacity: number }[]
}

type HttpRequestBody = Record<string, unknown> | string | null

interface MembersResponse {
  members: { id: number; name: string; email?: string }[]
}

interface AssignmentResponse {
  status: string
}

const api = {
  getOrgaEventBase(): string {
    return getApiConfig().baseUrl
  },

  get organizerSlug(): string | null {
    if (typeof window === 'undefined') return null
    const match = window.location.pathname.match(/\/(?:orga|teamshifts)\/event\/([^/]+)\/([^/]+)/)
    return match ? match[1] : null
  },

  get eventSlug(): string | null {
    if (typeof window === 'undefined') return null
    const match = window.location.pathname.match(/\/(?:orga|teamshifts)\/event\/([^/]+)\/([^/]+)/)
    return match ? match[2] : null
  },

  async http<T>(verb: string, url: string, body: HttpRequestBody): Promise<T> {
    const headers: Record<string, string> = {}
    if (body) headers['Content-Type'] = 'application/json'
    if (verb !== 'GET') {
      const csrfToken = getCsrfToken()
      if (csrfToken) headers['X-CSRFToken'] = csrfToken
    }

    const options: RequestInit = {
      method: verb,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: 'include',
    }

    const response = await fetch(url, options)

    if (response.status === 204) {
      return undefined as unknown as T
    }

    const json = await response.json()

    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}: ${JSON.stringify(json)}`)
    }

    return json as T
  },

  async fetchTalks(options?: { since?: string; warnings?: boolean }): Promise<Schedule> {
    const config = getApiConfig()
    let url = `${config.baseUrl}${config.endpoints.talks}`

    const params = new URLSearchParams(window.location.search)
    if (options?.since) params.append('since', options.since)
    if (options?.warnings) params.append('warnings', 'true')
    const paramsString = params.toString()
    if (paramsString) {
      url += `?${paramsString}`
    }

    const data = await this.http<Schedule>('GET', url, null)
    return ScheduleSchema.parse(data)
  },

  async fetchAvailabilities(): Promise<Availability> {
    const config = getApiConfig()
    const url = `${config.baseUrl}${config.endpoints.availabilities}`
    const data = await this.http<Availability>('GET', url, null)
    return AvailabilitySchema.parse(data)
  },

  async fetchWarnings(): Promise<Warnings> {
    const config = getApiConfig()
    const url = `${config.baseUrl}${config.endpoints.warnings}`
    const data = await this.http<Warnings>('GET', url, null)
    return WarningsSchema.parse(data)
  },

  async saveTalk(talk: TalkPayload, { action = 'PATCH' }: { action?: string } = {}): Promise<Talk | void> {
    const config = getApiConfig()
    const talksBase = `${config.baseUrl}${config.endpoints.talks}`
    const urlPath = talk.id ? `${talksBase}${talk.id}/` : talksBase
    const params = new URLSearchParams(window.location.search)
    const url = params.toString() ? `${urlPath}?${params.toString()}` : urlPath

    let payload: HttpRequestBody = null
    if (action !== 'DELETE') {
      const roomId = typeof talk.room === 'object' ? talk.room.id : talk.room
      const roomValue = resolveMode() !== 'talks' ? (roomId ?? null) : roomId
      const duration = talk.duration ?? calculateDuration(talk.start, talk.end)

      const convertToUTC = (date: string | Moment | undefined): string | undefined => {
        if (!date) return undefined
        return typeof date === 'string'
          ? moment(date).utc().format()
          : date.utc().format()
      }

      payload = {
        room: roomValue,
        start: convertToUTC(talk.start),
        end: convertToUTC(talk.end),
        duration,
        title: talk.title,
        description: talk.description,
      }

      if (resolveMode() !== 'talks') {
        payload.roles = talk.roles
      }
    }

    const response = await this.http<Talk>(action, url, payload)

    if (action !== 'DELETE') {
      if (response && typeof response === 'object' && 'id' in response && 'title' in response) {
        return TalkSchema.parse(response)
      }
      return response
    }
  },

  async deleteTalk(talk: { id: number }): Promise<void> {
    await this.saveTalk({ id: talk.id }, { action: 'DELETE' })
  },

  async createTalk(talk: Omit<TalkPayload, 'id'>): Promise<Talk> {
    const response = await this.saveTalk(talk, { action: 'POST' })
    if (!response) {
      throw new Error('Failed to create talk: No response from server')
    }
    return response
  },

  async fetchMembers(roleId: number): Promise<MembersResponse> {
    const config = getApiConfig()
    const url = `${config.baseUrl}${config.endpoints.members}?role=${roleId}`
    return this.http<MembersResponse>('GET', url, null)
  },

  async assignMember(shiftId: number, roleId: number, userId: number): Promise<AssignmentResponse> {
    const config = getApiConfig()
    const url = `${config.baseUrl}${config.endpoints.assignments}`
    return this.http<AssignmentResponse>('POST', url, { shift_id: shiftId, role_id: roleId, user_id: userId })
  },

  async unassignMember(shiftId: number, roleId: number, userId: number): Promise<AssignmentResponse> {
    const config = getApiConfig()
    const url = `${config.baseUrl}${config.endpoints.assignments}?shift_id=${shiftId}&role_id=${roleId}&user_id=${userId}`
    return this.http<AssignmentResponse>('DELETE', url, null)
  },
}

export default api
