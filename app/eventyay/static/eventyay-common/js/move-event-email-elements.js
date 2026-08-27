document.addEventListener('DOMContentLoaded', () => {
    moveElement('email-send_grid_api_key', 'email-email_vendor', 0)
    moveGmailPanel('email-email_vendor', 2)
    moveElement('email-smtp_host', 'email-email_vendor', 1)
    moveElement('email-smtp_port', 'email-email_vendor', 1)
    moveElement('email-smtp_username', 'email-email_vendor', 1)
    moveElement('email-smtp_password', 'email-email_vendor', 1)
    moveElement('email-smtp_use_tls', 'email-email_vendor', 1)
    moveElement('email-smtp_use_ssl', 'email-email_vendor', 1)

    function toggleGmailPanel() {
        const selected = document.querySelector('input[name="email-email_vendor"]:checked')
        const panel = document.querySelector('.gmail-connection-panel')
        if (!panel) {
            return
        }
        panel.style.display = selected && selected.value === 'gmail_api' ? '' : 'none'
    }

    const vendors = document.querySelectorAll('input[name="email-email_vendor"]')
    vendors.forEach(vendor => vendor.addEventListener('change', toggleGmailPanel))
    toggleGmailPanel()
})

function findParent(el, returnParent, max = 0) {
    if (max > 5 || !el || !el.parentNode) {
        return null
    }
    if (el.parentNode.className === 'form-group') {
        return returnParent ? el.parentNode : el
    }
    return findParent(el.parentNode, returnParent, max + 1)
}

function moveElement(elName, target, targetPos) {
    try {
        const el = document.getElementsByName(elName)[0]
        if (!el) return
        const rootOfGroup = findParent(el, true, 0)
        const des = document.getElementsByName(target)[targetPos]
        const rootOfDes = des.parentNode.parentNode
        
        if (rootOfGroup && rootOfGroup.parentNode) {
            rootOfGroup.parentNode.removeChild(rootOfGroup)
            rootOfDes.appendChild(rootOfGroup)
        }
    } catch (e) {
        console.error('move-event-email-elements', e)
    }
}

function moveGmailPanel(target, targetPos) {
    try {
        const panel = document.querySelector('.gmail-connection-panel')
        if (!panel) {
            return
        }
        const des = document.getElementsByName(target)[targetPos]
        const rootOfDes = des.parentNode.parentNode
        
        if (panel.parentNode) {
            panel.parentNode.removeChild(panel)
            rootOfDes.appendChild(panel)
        }
    } catch (e) {
        console.error('move-event-email-elements', e)
    }
}

