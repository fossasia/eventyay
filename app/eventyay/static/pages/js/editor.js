/* global Quill */
'use strict'

const form = document.querySelector('.tabbed-form form')
if (form) {
    initSlugGeneration(form)
    initQuillEditors(form)
}

function initSlugGeneration(form) {
    const slugInput = document.getElementById('id_slug')
    if (!slugInput) return

    let slugGenerated = !form.dataset.id

    slugInput.addEventListener('input', function () {
        slugGenerated = false
    })

    document.querySelectorAll('input[id^=id_title_]').forEach(function (input) {
        input.addEventListener('input', function () {
            if (!slugGenerated) return

            const firstNonEmpty = Array.from(document.querySelectorAll('input[id^=id_title_]'))
                .find(function (el) { return el.value })
            if (!firstNonEmpty) return

            slugInput.value = firstNonEmpty.value
                .toLowerCase()
                .replace(/\s+/g, '-')
                .replace(/[^\w-]+/g, '')
                .replace(/--+/g, '-')
                .replace(/^-+/, '')
                .replace(/-+$/, '')
                .substring(0, 150)
        })
    })
}

function initQuillEditors(form) {
    const textFields = document.getElementById('page-text-fields')
    if (!textFields) return

    const editors = form.querySelectorAll('.editor[data-lng]')
    if (!editors.length) return

    editors.forEach(function (editorEl) {
        const lng = editorEl.dataset.lng
        const textarea = textFields.querySelector('textarea[lang="' + lng + '"]')

        // Content is sanitized server-side with nh3 before storage
        const initialContent = textarea && textarea.value ? textarea.value : ''

        const quill = new Quill(editorEl, {
            theme: 'snow',
            formats: [
                'bold', 'italic', 'link', 'strike', 'code', 'underline', 'script',
                'list', 'align', 'code-block', 'header', 'image'
            ],
            modules: {
                toolbar: [
                    [{ header: [3, 4, 5, false] }],
                    ['bold', 'italic', 'underline', 'strike'],
                    ['link'],
                    ['image'],
                    [{ align: [] }],
                    [{ list: 'ordered' }, { list: 'bullet' }],
                    [{ script: 'sub' }, { script: 'super' }],
                    ['clean']
                ]
            }
        })

        if (initialContent) {
            quill.clipboard.dangerouslyPasteHTML(initialContent)
        }
    })

    form.addEventListener('submit', function () {
        editors.forEach(function (editorEl) {
            const lng = editorEl.dataset.lng
            const textarea = textFields.querySelector('textarea[lang="' + lng + '"]')
            if (textarea) {
                const qlEditor = editorEl.querySelector('.ql-editor')
                if (!qlEditor) return
                const html = qlEditor.innerHTML
                // Normalize empty Quill content to empty string
                textarea.value = html.replace(/<p><br><\/p>/g, '').trim() ? html : ''
            }
        })
    })
}
