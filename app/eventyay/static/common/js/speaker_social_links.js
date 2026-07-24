/**
 * Update social-link URL prefixes when the platform select changes.
 * Works alongside jquery.formset used for add/remove of form rows.
 */

function updateSocialLinkPrefix(row, prefixes) {
    if (!row) return
    const select = row.querySelector('select[name$="-network"]')
    const prefix = row.querySelector('[data-social-prefix]')
    if (!select || !prefix) return
    prefix.textContent = prefixes[select.value] || 'https://'
}

function initSocialLinkRow(row, prefixes) {
    if (!row) return
    if (row.dataset.socialPrefixBound === 'true') {
        updateSocialLinkPrefix(row, prefixes)
        return
    }
    const select = row.querySelector('select[name$="-network"]')
    if (select) {
        select.addEventListener('change', () => updateSocialLinkPrefix(row, prefixes))
    }
    row.dataset.socialPrefixBound = 'true'
    updateSocialLinkPrefix(row, prefixes)
}

function parsePrefixes(formset) {
    if (!formset.dataset.socialLinkPrefixes) return {}
    try {
        return JSON.parse(formset.dataset.socialLinkPrefixes)
    } catch (error) {
        console.error('Failed to parse social link prefixes', error)
        return {}
    }
}

export function initSpeakerSocialLinksFormset(root = document) {
    const formset = root.getElementById?.('social-links-formset') || root.querySelector?.('#social-links-formset')
    if (!formset) return

    const prefixes = parsePrefixes(formset)

    const bindRows = () => {
        formset.querySelectorAll('[data-social-link-row]').forEach((row) => {
            initSocialLinkRow(row, prefixes)
        })
    }

    bindRows()

    const body = formset.querySelector('[data-formset-body]')
    if (body) {
        const observer = new MutationObserver(bindRows)
        observer.observe(body, { childList: true })
    }
}

initSpeakerSocialLinksFormset()
