document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('cfp-field-order-data');
    if (!container) return;

    function parseJsonDataset(value, fieldName) {
        if (!value) {
            return [];
        }
        try {
            return JSON.parse(value);
        } catch (error) {
            console.error(`Failed to parse JSON from dataset field ${fieldName}:`, value, error);
            return [];
        }
    }
    
    const sessionOrder = parseJsonDataset(container.dataset.sessionFieldOrder, 'sessionFieldOrder');
    const speakerOrder = parseJsonDataset(container.dataset.speakerFieldOrder, 'speakerFieldOrder');
    const reviewerOrder = parseJsonDataset(container.dataset.reviewerFieldOrder, 'reviewerFieldOrder');
    
    function reorderRows(tbody, order) {
        if (!order || order.length === 0) return;
        
        const rows = Array.from(tbody.querySelectorAll('tr[dragsort-id]'));
        const rowMap = new Map();
        const usedIds = new Set();
        
        rows.forEach(row => {
            const id = row.getAttribute('dragsort-id');
            if (id) rowMap.set(id, row);
        });
        
        const fragment = document.createDocumentFragment();
        
        order.forEach(id => {
            const row = rowMap.get(id);
            if (row) {
                fragment.appendChild(row);
                usedIds.add(id);
            }
        });
        
        rows.forEach(row => {
            const id = row.getAttribute('dragsort-id');
            if (id && !usedIds.has(id)) {
                fragment.appendChild(row);
            }
        });
        
        while (tbody.firstChild) {
            tbody.removeChild(tbody.firstChild);
        }
        tbody.appendChild(fragment);
    }
    
    const proposalTbody = document.querySelector('#proposal-information')?.closest('fieldset')?.querySelector('tbody[dragsort-url]');
    const speakerTbody = document.querySelector('#speaker-information')?.closest('fieldset')?.querySelector('tbody[dragsort-url]');
    const reviewerTbody = document.querySelector('#reviewer-information')?.closest('fieldset')?.querySelector('tbody[dragsort-url]');
    
    if (proposalTbody && sessionOrder.length > 0) {
        reorderRows(proposalTbody, sessionOrder);
    }
    if (speakerTbody && speakerOrder.length > 0) {
        reorderRows(speakerTbody, speakerOrder);
    }
    if (reviewerTbody && reviewerOrder.length > 0) {
        reorderRows(reviewerTbody, reviewerOrder);
    }
});
