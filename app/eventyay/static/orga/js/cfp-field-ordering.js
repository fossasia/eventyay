document.addEventListener('DOMContentLoaded', () => {
    const sessionOrder = window.sessionFieldOrder || [];
    const speakerOrder = window.speakerFieldOrder || [];
    
    function reorderRows(tbody, order) {
        if (!order || order.length === 0) return;
        
        const rows = Array.from(tbody.querySelectorAll('tr[dragsort-id]'));
        const rowMap = new Map();
        
        rows.forEach(row => {
            const id = row.getAttribute('dragsort-id');
            if (id) rowMap.set(id, row);
        });
        
        const fragment = document.createDocumentFragment();
        order.forEach(id => {
            const row = rowMap.get(id);
            if (row) {
                fragment.appendChild(row);
            }
        });
        
        if (fragment.childNodes.length > 0) {
            tbody.appendChild(fragment);
        }
    }
    
    const proposalTbody = document.querySelector('#proposal-information')?.closest('fieldset')?.querySelector('tbody[dragsort-url]');
    const speakerTbody = document.querySelector('#speaker-information')?.closest('fieldset')?.querySelector('tbody[dragsort-url]');
    
    if (proposalTbody && sessionOrder.length > 0) {
        reorderRows(proposalTbody, sessionOrder);
    }
    if (speakerTbody && speakerOrder.length > 0) {
        reorderRows(speakerTbody, speakerOrder);
    }
});
