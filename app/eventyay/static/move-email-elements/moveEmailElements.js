(function () {
    document.addEventListener("DOMContentLoaded", function () {
        moveElement('send_grid_api_key', 'email_vendor', 0);
        moveElement('gmail_client_id', 'email_vendor', 2);
        moveElement('gmail_client_secret', 'email_vendor', 2);
        moveGmailPanel('email_vendor', 2);
        moveElement('smtp_host', 'email_vendor', 1);
        moveElement('smtp_port', 'email_vendor', 1);
        moveElement('smtp_username', 'email_vendor', 1);
        moveElement('smtp_password', 'email_vendor', 1);
        moveElement('smtp_use_tls', 'email_vendor', 1);
        moveElement('smtp_use_ssl', 'email_vendor', 1);

        function toggleGmailPanel() {
            var selected = document.querySelector('input[name="email_vendor"]:checked');
            var panel = document.querySelector('.gmail-connection-panel');
            if (!panel) {
                return;
            }
            panel.style.display = selected && selected.value === 'gmail_api' ? '' : 'none';
        }

        var radios = document.querySelectorAll('input[name="email_vendor"]');
        radios.forEach(function(radio) {
            radio.addEventListener('change', toggleGmailPanel);
        });
        toggleGmailPanel();
    });

    /**
     * Find HTML element.
     * @param {*} el - The element - used to find it parent
     * @param {*} return_parent - Boolean variable used to decide whether to return the found element or its parent node.
     * @param {*} max - Maximun steps, return null if the maximum steps are reached without finding a matching element.
     * @returns 
     */
    function findParent(el, return_parent = false, max = 0) {
        if (max > 5) return null;
        if (el.parentNode && el.parentNode.classList && el.parentNode.classList.contains('form-group')) {
            return return_parent ? el.parentNode : el;
        } else {
            return findParent(el.parentNode, return_parent, max + 1);
        }
    }

    /**
     * Moves the specified HTML element to become a child of a radio button element.
     * @param {*} el_name - The element name to be moved.
     * @param {*} target - The radio button name - where `el_name` will be appended.
     * @param {*} target_pos - Position of radio button in radio button group.
     */
    function moveElement(el_name, target, target_pos) {
        try {
            var el = document.getElementsByName(el_name)[0];
            if (!el) return;
            var rootOfGroup = findParent(el, true);
            var des = document.getElementsByName(target)[target_pos];
            if (!des || !rootOfGroup) return;
            var rootOfDes = des.parentNode.parentNode;
            rootOfGroup.parentNode.removeChild(rootOfGroup);
            rootOfDes.appendChild(rootOfGroup);
        } catch (e) {
            console.error("==================", e);
        }
    }

    function moveGmailPanel(target, target_pos) {
        try {
            var panel = document.querySelector('.gmail-connection-panel');
            if (!panel) {
                return;
            }
            var des = document.getElementsByName(target)[target_pos];
            if (!des) return;
            var rootOfDes = des.parentNode.parentNode;
            panel.parentNode.removeChild(panel);
            rootOfDes.appendChild(panel);
        } catch (e) {
            console.error("==================", e);
        }
    }
})();
