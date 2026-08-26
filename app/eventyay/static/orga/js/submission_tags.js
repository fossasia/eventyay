const getDescriptionText = (description) => {
    if (!description) return ''
    if (typeof description === 'string') return description.trim()
    if (typeof description === 'object') {
        const values = Object.values(description).filter((value) => typeof value === 'string' && value.trim())
        return values[0] ? values[0].trim() : ''
    }
    return ''
}

const parseEmbeddedTags = (raw) => {
    if (!raw) return []
    try {
        const parsed = JSON.parse(raw)
        return Array.isArray(parsed) ? parsed : []
    } catch (error) {
        console.error('Failed to parse embedded submission tags', error)
        return []
    }
}

const readCookie = (name) => {
    if (typeof getCookie === 'function') {
        return getCookie(name)
    }
    if (!document.cookie) return null
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i++) {
        const cookie = cookies[i].trim()
        if (cookie.substring(0, name.length + 1) === `${name}=`) {
            return decodeURIComponent(cookie.substring(name.length + 1))
        }
    }
    return null
}

const initSubmissionTags = () => {
    const tagsDropdown = document.getElementById('tags-dropdown')
    if (!tagsDropdown) return

    const tagsApi = tagsDropdown.dataset.tagsApi
    const submissionApi = tagsDropdown.dataset.submissionApi
    const noTagsLabel = tagsDropdown.dataset.noTagsLabel || 'No tags'
    const noMatchLabel = tagsDropdown.dataset.noMatchLabel || 'No matching tags found'
    const defaultColor = tagsDropdown.dataset.defaultColor || '#17a2b8'

    const tagsSearchInput = document.getElementById('tags-search-input')
    const tagsListContainer = document.getElementById('tags-list')
    const createTagContainer = document.getElementById('create-tag-container')
    const createTagName = document.getElementById('create-tag-name')
    const createTagBtn = document.getElementById('create-tag-btn')
    const tagsDisplayContainer = document.getElementById('submission-tags-display')
    const tagsDataEl = document.getElementById('submission-tags-data')
    const tagsErrorEl = document.getElementById('tags-error')
    const dropdownPanel = tagsDropdown.querySelector('.tags-dropdown-menu')

    if (
        !tagsApi ||
        !submissionApi ||
        !tagsSearchInput ||
        !tagsListContainer ||
        !createTagContainer ||
        !createTagName ||
        !createTagBtn ||
        !tagsDisplayContainer ||
        !dropdownPanel
    ) {
        console.error('Submission tags dropdown is missing required elements or API URLs')
        return
    }

    let allTags = parseEmbeddedTags(tagsDataEl ? tagsDataEl.textContent : '[]')
    let assignedTagIds = new Set()
    let currentQuery = ''
    let requestInFlight = false

    tagsDisplayContainer.querySelectorAll('.badge[data-tag-id]').forEach((badge) => {
        const id = Number.parseInt(badge.getAttribute('data-tag-id'), 10)
        if (!Number.isNaN(id)) {
            assignedTagIds.add(id)
        }
    })

    const showError = (message) => {
        if (!tagsErrorEl) return
        if (!message) {
            tagsErrorEl.hidden = true
            tagsErrorEl.textContent = ''
            return
        }
        tagsErrorEl.hidden = false
        tagsErrorEl.textContent = message
    }

    const csrfHeaders = () => {
        const csrfToken =
            tagsDropdown.dataset.csrfToken ||
            readCookie('eventyay_csrftoken') ||
            readCookie('csrftoken')
        const headers = {
            Accept: 'application/json',
            'Content-Type': 'application/json',
        }
        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken
        } else {
            console.error('CSRF token missing for submission tags request')
        }
        return headers
    }

    const renderTagsDisplay = () => {
        tagsDisplayContainer.innerHTML = ''
        if (assignedTagIds.size === 0) {
            const noTags = document.createElement('span')
            noTags.className = 'text-muted'
            noTags.id = 'no-tags-text'
            noTags.textContent = tagsDisplayContainer.dataset.noTagsLabel || noTagsLabel
            tagsDisplayContainer.appendChild(noTags)
            return
        }

        Array.from(assignedTagIds)
            .map((id) => allTags.find((tag) => Number(tag.id) === Number(id)))
            .filter(Boolean)
            .sort((a, b) => a.tag.localeCompare(b.tag))
            .forEach((tag) => {
                const badge = document.createElement('span')
                badge.className = 'badge mr-1 mb-1'
                badge.setAttribute('data-tag-id', String(tag.id))
                badge.textContent = tag.tag
                if (tag.color) {
                    badge.style.setProperty('--tag-color', tag.color)
                    if (tag.foreground_color === 'white') {
                        badge.classList.add('text-white')
                    } else if (tag.foreground_color === 'black') {
                        badge.classList.add('text-dark')
                    }
                }
                tagsDisplayContainer.appendChild(badge)
            })
    }

    const updateCreateVisibility = (query) => {
        const trimmed = query.trim()
        const exactMatch = allTags.some((tag) => tag.tag.toLowerCase() === trimmed.toLowerCase())
        if (trimmed && !exactMatch) {
            createTagName.textContent = trimmed
            createTagContainer.hidden = false
        } else {
            createTagContainer.hidden = true
            createTagName.textContent = ''
        }
    }

    const renderTagsDropdown = (tagsToRender) => {
        tagsListContainer.innerHTML = ''

        if (!Array.isArray(tagsToRender) || tagsToRender.length === 0) {
            const noResults = document.createElement('div')
            noResults.className = 'tags-dropdown-empty text-muted'
            noResults.textContent = noMatchLabel
            tagsListContainer.appendChild(noResults)
            updateCreateVisibility(currentQuery)
            return
        }

        tagsToRender.forEach((tag) => {
            const tagId = Number(tag.id)
            const item = document.createElement('label')
            item.className = 'tag-dropdown-item'

            const checkbox = document.createElement('input')
            checkbox.type = 'checkbox'
            checkbox.className = 'tag-checkbox'
            checkbox.value = String(tagId)
            checkbox.checked = assignedTagIds.has(tagId)

            checkbox.addEventListener('click', (event) => {
                // Keep the details dropdown open while toggling.
                event.stopPropagation()
            })

            checkbox.addEventListener('change', () => {
                if (requestInFlight) {
                    checkbox.checked = assignedTagIds.has(tagId)
                    return
                }
                const previous = new Set(assignedTagIds)
                if (checkbox.checked) {
                    assignedTagIds.add(tagId)
                } else {
                    assignedTagIds.delete(tagId)
                }
                showError('')
                renderTagsDisplay()
                updateSubmissionTags().catch(() => {
                    assignedTagIds = previous
                    checkbox.checked = assignedTagIds.has(tagId)
                    renderTagsDisplay()
                    filterAndRender()
                })
            })

            const colorCircle = document.createElement('span')
            colorCircle.className = 'tag-color-circle'
            colorCircle.style.setProperty('--tag-color', tag.color || '#cccccc')
            colorCircle.setAttribute('aria-hidden', 'true')

            const textWrap = document.createElement('span')
            textWrap.className = 'tag-dropdown-text'

            const tagText = document.createElement('span')
            tagText.className = 'tag-dropdown-name'
            tagText.textContent = tag.tag
            textWrap.appendChild(tagText)

            const description = getDescriptionText(tag.description)
            if (description) {
                const descriptionEl = document.createElement('span')
                descriptionEl.className = 'tag-dropdown-description text-muted'
                descriptionEl.textContent = description
                textWrap.appendChild(descriptionEl)
            }

            item.appendChild(checkbox)
            item.appendChild(colorCircle)
            item.appendChild(textWrap)
            tagsListContainer.appendChild(item)
        })

        updateCreateVisibility(currentQuery)
    }

    const filterAndRender = () => {
        const query = currentQuery.trim().toLowerCase()
        const filteredTags = !query
            ? allTags
            : allTags.filter((tag) => tag.tag.toLowerCase().includes(query))
        renderTagsDropdown(filteredTags)
    }

    /**
     * @throws {Error} when the submission tags update request fails
     */
    const updateSubmissionTags = () => {
        requestInFlight = true
        const payload = { tags: Array.from(assignedTagIds) }
        return fetch(submissionApi, {
            method: 'PATCH',
            credentials: 'same-origin',
            headers: csrfHeaders(),
            body: JSON.stringify(payload),
        })
            .then(async (response) => {
                if (!response.ok) {
                    const errorBody = await response.text()
                    throw new Error(`Failed to update submission tags (${response.status}): ${errorBody}`)
                }
                return response.json()
            })
            .then(() => {
                showError('')
                renderTagsDisplay()
            })
            .catch((error) => {
                console.error('Error updating submission tags:', error)
                showError('Could not update tags. Please try again.')
                throw error
            })
            .finally(() => {
                requestInFlight = false
            })
    }

    const createTag = async () => {
        const newTagName = (createTagName.textContent || tagsSearchInput.value || '').trim()
        if (!newTagName || requestInFlight) return

        createTagBtn.disabled = true
        requestInFlight = true
        showError('')
        try {
            const response = await fetch(tagsApi, {
                method: 'POST',
                credentials: 'same-origin',
                headers: csrfHeaders(),
                body: JSON.stringify({
                    tag: newTagName,
                    color: defaultColor,
                }),
            })
            const tag = await response.json().catch(() => null)
            if (!response.ok) {
                throw new Error(
                    `Failed to create tag (${response.status}): ${JSON.stringify(tag)}`
                )
            }

            const tagId = Number(tag.id)
            tag.id = tagId
            allTags.push(tag)
            allTags.sort((a, b) => a.tag.localeCompare(b.tag))
            assignedTagIds.add(tagId)
            tagsSearchInput.value = ''
            currentQuery = ''
            createTagContainer.hidden = true
            createTagName.textContent = ''
            renderTagsDisplay()
            requestInFlight = false
            try {
                await updateSubmissionTags()
            } catch (assignError) {
                assignedTagIds.delete(tagId)
                renderTagsDisplay()
                throw assignError
            }
            filterAndRender()
        } catch (error) {
            console.error('Error creating tag:', error)
            showError('Could not create tag. Please try again.')
            filterAndRender()
        } finally {
            requestInFlight = false
            createTagBtn.disabled = false
        }
    }

    // Keep interactions inside the panel from closing the details dropdown.
    dropdownPanel.addEventListener('click', (event) => {
        event.stopPropagation()
    })
    dropdownPanel.addEventListener('pointerdown', (event) => {
        event.stopPropagation()
    })

    // Render immediately from server-provided tags, then refresh from API.
    allTags = allTags.map((tag) => ({ ...tag, id: Number(tag.id) }))
    allTags.sort((a, b) => a.tag.localeCompare(b.tag))
    filterAndRender()

    fetch(tagsApi, {
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
    })
        .then(async (response) => {
            if (!response.ok) {
                throw new Error(`Failed to fetch tags (${response.status})`)
            }
            return response.json()
        })
        .then((data) => {
            const fetched = Array.isArray(data.results) ? data.results : Array.isArray(data) ? data : []
            if (fetched.length || allTags.length === 0) {
                allTags = fetched.map((tag) => ({ ...tag, id: Number(tag.id) }))
                allTags.sort((a, b) => a.tag.localeCompare(b.tag))
                filterAndRender()
            }
        })
        .catch((error) => {
            console.error('Error fetching tags:', error)
            if (allTags.length === 0) {
                renderTagsDropdown([])
            }
        })

    tagsDropdown.addEventListener('toggle', () => {
        if (tagsDropdown.open) {
            showError('')
            tagsSearchInput.focus()
        }
    })

    tagsSearchInput.addEventListener('input', (event) => {
        currentQuery = event.target.value
        showError('')
        filterAndRender()
    })

    tagsSearchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault()
            event.stopPropagation()
            if (!createTagContainer.hidden) {
                createTag()
            }
        }
    })

    createTagBtn.addEventListener('click', (event) => {
        event.preventDefault()
        event.stopPropagation()
        createTag()
    })
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSubmissionTags)
} else {
    initSubmissionTags()
}
