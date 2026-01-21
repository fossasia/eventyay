// Partner Settings - Drag and drop sorting for sponsor groups and partners

document.addEventListener('DOMContentLoaded', function() {
    const sponsorGroupsList = document.getElementById('sponsor-groups-list');
    
    // Initialize group sorting
    if (sponsorGroupsList) {
        new Sortable(sponsorGroupsList, {
            handle: '.handle',
            animation: 150,
            onEnd: function(evt) {
                // Collect group IDs in new order
                const groupIds = [];
                const items = sponsorGroupsList.querySelectorAll('.sponsor-group-item');
                items.forEach(item => {
                    groupIds.push(parseInt(item.dataset.groupId));
                });
                
                // Send AJAX request to update order
                const reorderUrl = sponsorGroupsList.dataset.reorderUrl;
                fetch(reorderUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({group_ids: groupIds})
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Group order updated successfully
                    } else {
                        console.error('Failed to update group order:', data.message);
                        alert(sponsorGroupsList.dataset.errorMessage || 'Failed to update group order. Please refresh and try again.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert(sponsorGroupsList.dataset.errorMessage || 'An error occurred. Please refresh and try again.');
                });
            }
        });
    }
    
    // Initialize inline partner sorting for each group
    const partnerContainers = document.querySelectorAll('.partner-inline-sortable');
    partnerContainers.forEach(container => {
        // Show drag handles on hover
        container.addEventListener('mouseenter', function() {
            this.querySelectorAll('.partner-drag-handle').forEach(handle => {
                handle.style.display = 'block';
            });
        });
        container.addEventListener('mouseleave', function() {
            this.querySelectorAll('.partner-drag-handle').forEach(handle => {
                handle.style.display = 'none';
            });
        });
        
        new Sortable(container, {
            handle: '.partner-drag-handle',
            animation: 150,
            ghostClass: 'partner-sortable-ghost',
            onEnd: function(evt) {
                const groupId = container.dataset.groupId;
                const partnerIds = [];
                container.querySelectorAll('.partner-item-inline').forEach(item => {
                    partnerIds.push(parseInt(item.dataset.partnerId));
                });
                
                // Get reorder URL from data attribute
                const reorderUrl = container.dataset.reorderUrl;
                
                // Send AJAX request to update partner order
                fetch(reorderUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                    },
                    body: JSON.stringify({
                        group_id: groupId,
                        partner_ids: partnerIds
                    })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Partner order updated successfully
                        // Remove any existing feedback first
                        const existingFeedback = container.querySelector('.order-saved-feedback');
                        if (existingFeedback) {
                            existingFeedback.remove();
                        }
                        // Show success feedback
                        const feedback = document.createElement('span');
                        feedback.className = 'order-saved-feedback';
                        feedback.textContent = ' ✓ Order saved';
                        feedback.style.color = '#5cb85c';
                        feedback.style.marginLeft = '10px';
                        feedback.style.fontSize = '12px';
                        container.appendChild(feedback);
                        setTimeout(() => feedback.remove(), 2000);
                    } else {
                        console.error('Failed to update partner order:', data.message);
                        alert(container.dataset.errorMessage || 'Failed to update partner order. Please refresh and try again.');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert(container.dataset.errorMessage || 'An error occurred. Please refresh and try again.');
                });
            }
        });
    });
    
    // Handle navigation to partner tab if hash is present
    function activatePartnerTab() {
        if (window.location.hash === '#partner-tab') {
            // Find and click the Bootstrap tab link for the partner tab
            const partnerTabLink = document.querySelector('a[href="#partner-tab"]');
            if (partnerTabLink) {
                // Activate the Bootstrap tab
                $(partnerTabLink).tab('show');
                
                // Scroll to the tab content
                setTimeout(() => {
                    const partnerTab = document.getElementById('partner-tab');
                    if (partnerTab) {
                        partnerTab.scrollIntoView({behavior: 'smooth', block: 'start'});
                    }
                }, 100);
            }
        }
    }
    
    // Run on page load (after tabs are initialized)
    setTimeout(activatePartnerTab, 200);
    
    // Also run when hash changes (e.g., when clicking back button)
    window.addEventListener('hashchange', activatePartnerTab);
});
