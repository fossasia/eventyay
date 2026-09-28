const SAFE = /^[A-Za-z0-9._:-]{1,128}$/

export function logOperational({
  component = 'talk',
  action,
  outcome,
  error_code,
  backend,
  status,
}: {
  component?: string
  action: string
  outcome: 'success' | 'failure'
  error_code?: string
  backend?: string
  status?: number
}): void {
  const record: Record<string, string | number> = {
    datetime: new Date().toISOString(),
    component,
    action,
    outcome,
  }
  if (typeof error_code === 'string' && SAFE.test(error_code)) record.error_code = error_code
  if (typeof backend === 'string' && SAFE.test(backend)) record.backend = backend
  if (typeof status === 'number' && Number.isFinite(status)) record.status = status
  const line = Object.entries(record).map(([key, value]) => `${key}=${value}`).join(' ')
  if (outcome === 'failure') {
    console.warn('[eventyay]', line)
  } else {
    console.info('[eventyay]', line)
  }
}
