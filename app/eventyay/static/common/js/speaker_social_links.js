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
    const prefix = formset.dataset.formsetPrefix
    const totalForms = formset.querySelector(`input[name="${prefix}-TOTAL_FORMS"]`)
    const maxForms = formset.querySelector(`input[name="${prefix}-MAX_NUM_FORMS"]`)
    const formsetBody = formset.querySelector('[data-formset-body]')
    const emptyFormTemplate = formset.querySelector('[data-formset-empty-form]')
    const addButton = formset.querySelector('[data-formset-add]')

    if (!totalForms || !formsetBody || !emptyFormTemplate || !addButton) return

    const bindRow = (row) => {
        initSocialLinkRow(row, prefixes)
        const deleteButton = row.querySelector('[data-formset-delete-button]')
        if (deleteButton) {
            deleteButton.addEventListener('click', () => {
                row.remove()
                updateFormIndexes()
            })
        }
    }

    const updateFormIndexes = () => {
        const rows = formsetBody.querySelectorAll('[data-social-link-row]')
        rows.forEach((row, index) => {
            row.innerHTML = row.innerHTML.replace(new RegExp(`${prefix}-\\d+-`, 'g'), `${prefix}-${index}-`)
            row.innerHTML = row.innerHTML.replace(new RegExp(`${prefix}_\\d+_`, 'g'), `${prefix}_${index}_`)
        })
        totalForms.value = rows.length
        
        if (maxForms && maxForms.value) {
            addButton.disabled = rows.length >= parseInt(maxForms.value, 10)
        }
    }

    addButton.addEventListener('click', () => {
        if (maxForms && maxForms.value && parseInt(totalForms.value, 10) >= parseInt(maxForms.value, 10)) {
            return
        }
        
        const templateHtml = emptyFormTemplate.innerHTML
        const newRowIndex = totalForms.value
        const newHtml = templateHtml
            .replace(new RegExp(`${prefix}-__prefix__-`, 'g'), `${prefix}-${newRowIndex}-`)
            .replace(new RegExp(`${prefix}___prefix___`, 'g'), `${prefix}_${newRowIndex}_`)

        const tempDiv = document.createElement('div')
        tempDiv.innerHTML = newHtml
        const newRow = tempDiv.firstElementChild
        
        formsetBody.appendChild(newRow)
        bindRow(newRow)
        updateFormIndexes()
    })

    formsetBody.querySelectorAll('[data-social-link-row]').forEach(bindRow)
    updateFormIndexes()
}

initSpeakerSocialLinksFormset()
