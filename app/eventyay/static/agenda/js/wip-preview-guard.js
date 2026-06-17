const WIP_PATH_MARKER = '/schedule/v/wip/' // keep in sync with talk_rules.agenda.WIP_AGENDA_URL_PATH
const DIALOG_ID = 'agenda-wip-preview-leave-dialog'

function isWipPreviewPath(pathname) {
	return pathname.includes(WIP_PATH_MARKER)
}

function navigationStaysInWipPreview(href) {
	const url = new URL(href, window.location.href)
	if (url.origin !== window.location.origin) {
		return true
	}
	return isWipPreviewPath(url.pathname)
}

function shouldInterceptLinkClick(event, link) {
	if (!link || link.target === '_blank' || link.hasAttribute('download')) {
		return false
	}
	if (event.defaultPrevented || event.button !== 0) {
		return false
	}
	if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
		return false
	}
	const href = link.getAttribute('href')
	if (!href || href.startsWith('#')) {
		return false
	}
	return !navigationStaysInWipPreview(href)
}

function confirmLeavePreview() {
	const dialog = document.getElementById(DIALOG_ID)
	if (!dialog || typeof dialog.showModal !== 'function') {
		return Promise.resolve(false)
	}

	return new Promise((resolve) => {
		const stayButton = dialog.querySelector('[data-wip-preview-action="stay"]')
		const leaveButton = dialog.querySelector('[data-wip-preview-action="leave"]')
		if (!stayButton || !leaveButton) {
			resolve(false)
			return
		}

		const finish = (confirmed) => {
			stayButton.removeEventListener('click', onStay)
			leaveButton.removeEventListener('click', onLeave)
			dialog.removeEventListener('cancel', onStay)
			dialog.removeEventListener('click', onBackdropClick)
			if (dialog.open) {
				dialog.close()
			}
			resolve(confirmed)
		}
		const onStay = () => finish(false)
		const onLeave = () => finish(true)
		const onBackdropClick = (event) => {
			if (event.target === dialog) {
				finish(false)
			}
		}

		stayButton.addEventListener('click', onStay)
		leaveButton.addEventListener('click', onLeave)
		dialog.addEventListener('cancel', onStay)
		dialog.addEventListener('click', onBackdropClick)
		dialog.showModal()
		stayButton.focus()
	})
}

function initWipPreviewGuard() {
	if (!isWipPreviewPath(window.location.pathname)) {
		return
	}
	if (!document.getElementById(DIALOG_ID)) {
		return
	}

	document.addEventListener('click', (event) => {
		const link = event.target.closest('a[href]')
		if (!shouldInterceptLinkClick(event, link)) {
			return
		}

		event.preventDefault()
		event.stopImmediatePropagation()

		const destination = link.href
		confirmLeavePreview().then((confirmed) => {
			if (confirmed) {
				window.location.assign(destination)
			}
		})
	}, true)
}

if (document.readyState === 'loading') {
	document.addEventListener('DOMContentLoaded', initWipPreviewGuard)
} else {
	initWipPreviewGuard()
}
