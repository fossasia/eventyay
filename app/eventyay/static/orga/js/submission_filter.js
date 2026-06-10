onReady(() => {
    const stateSelect = document.querySelector('#id_state')
    if (stateSelect) {
        const choicesEl = stateSelect.closest('.choices')
        const dropdown = choicesEl?.querySelector('.choices__list--dropdown')
        const pendingDiv = document.getElementById('pending')

        if (pendingDiv && dropdown) {
            pendingDiv.classList.add('choices-exclude-pending')
            dropdown.prepend(pendingDiv)

            new MutationObserver(() => {
                if (!dropdown.contains(pendingDiv)) dropdown.prepend(pendingDiv)
            }).observe(dropdown, { childList: true })
        }
    }

    const multiSelects = [
        { selector: '#id_state',           singular: '1 state',    plural: (n) => `${n} states` },
        { selector: '#id_content_locale',  singular: '1 language', plural: (n) => `${n} languages` },
        { selector: '#id_tags',            singular: '1 tag',      plural: (n) => `${n} tags` },
        { selector: '#id_track',           singular: '1 track',    plural: (n) => `${n} tracks` },
        { selector: '#id_submission_type', singular: '1 type',     plural: (n) => `${n} types` },
    ]

    multiSelects.forEach(({ selector, singular, plural }) => {
        const select = document.querySelector(selector)
        if (!select) return

        const choicesEl = select.closest('.choices')
        if (!choicesEl) return

        const inner = choicesEl.querySelector('.choices__inner')
        if (!inner) return

        const badge = document.createElement('span')
        badge.className = 'state-count-badge'
        badge.hidden = true
        inner.prepend(badge)

        const update = () => {
            const count = Array.from(select.selectedOptions).length
            const chips = inner.querySelectorAll('.choices__item.choices__item--selectable')

            if (count > 0) {
                badge.textContent = count === 1 ? singular : plural(count)
                badge.hidden = false
                chips.forEach(chip => { chip.hidden = true })
            } else {
                badge.hidden = true
                chips.forEach(chip => { chip.hidden = false })
            }
        }

        select.addEventListener('change', update)

        new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.addedNodes.length) { update(); break }
            }
        }).observe(inner, { childList: true })

        update()
    })
})
