/**
 * Normalizes session and talk resources for download/external link display.
 * Appends '#resource' to PDF resources (preserving query params/hashes) so
 * the in-browser PDF viewer opens correctly, while preserving link resources.
 */
export function normalizeDisplayResources (resources = []) {
	if (!Array.isArray(resources)) return []
	return resources.map((r) => {
		if (!r) return r
		const resPath = r.resource || r.link
		if (resPath) {
			const cleanPath = resPath.split(/[?#]/)[0]
			if (cleanPath.toLowerCase().endsWith('.pdf') && !resPath.includes('#')) {
				return {
					...r,
					resource: r.resource ? `${r.resource}#resource` : undefined,
					link: r.link ? `${r.link}#resource` : undefined,
				}
			}
		}
		return r
	})
}
