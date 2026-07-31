(function ($) {

    $(document).ready(function () {
        moveElement('email-send_grid_api_key', 'email-email_vendor', 0)
        moveGmailPanel('email-email_vendor', 2)
        moveElement('email-smtp_host', 'email-email_vendor', 1)
        moveElement('email-smtp_port', 'email-email_vendor', 1)
        moveElement('email-smtp_username', 'email-email_vendor', 1)
        moveElement('email-smtp_password', 'email-email_vendor', 1)
        moveElement('email-smtp_use_tls', 'email-email_vendor', 1)
        moveElement('email-smtp_use_ssl', 'email-email_vendor', 1)

        function toggleGmailPanel() {
            var selected = document.querySelector('input[name="email-email_vendor"]:checked')
            var panel = document.querySelector('.gmail-connection-panel')
            if (!panel) {
                return
            }
            panel.style.display = selected && selected.value === 'gmail_api' ? '' : 'none'
        }

        $('input[name="email-email_vendor"]').on('change', toggleGmailPanel)
        toggleGmailPanel()
        $('input[name="email-email_vendor"]:checked').trigger('change')
    })

    function findParent(el, returnParent, max) {
        if (max > 5) {
            return null
        }
        if (el.parentNode.className === 'form-group') {
            return returnParent ? el.parentNode : el
        }
        return findParent(el.parentNode, returnParent, max + 1)
    }

    function moveElement(elName, target, targetPos) {
        try {
            var el = document.getElementsByName(elName)[0]
            var rootOfGroup = findParent(el, true, 0)
            var des = document.getElementsByName(target)[targetPos]
            var rootOfDes = des.parentNode.parentNode
            $(rootOfGroup).detach()
            $(rootOfDes).append(rootOfGroup)
        } catch (e) {
            console.error('move-event-email-elements', e)
        }
    }

    function moveGmailPanel(target, targetPos) {
        try {
            var panel = document.querySelector('.gmail-connection-panel')
            if (!panel) {
                return
            }
            var des = document.getElementsByName(target)[targetPos]
            var rootOfDes = des.parentNode.parentNode
            $(panel).detach()
            $(rootOfDes).append(panel)
        } catch (e) {
            console.error('move-event-email-elements', e)
        }
    }
})(jQuery)
