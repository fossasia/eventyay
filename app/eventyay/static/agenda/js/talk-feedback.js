document.addEventListener("DOMContentLoaded", function() {
    const replyBtns = document.querySelectorAll('.reply-btn');
    replyBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const formId = this.getAttribute('data-form-id') || this.getAttribute('data-id');
            const parentId = this.getAttribute('data-parent-id') || this.getAttribute('data-id');
            const formContainer = document.getElementById('reply-form-' + formId);
            if (formContainer) {
                const replyItem = this.closest('.reply-item');
                if (replyItem) {
                    replyItem.parentNode.insertBefore(formContainer, replyItem.nextSibling);
                } else {
                    const actionsContainer = this.closest('.comment-actions');
                    if (actionsContainer) {
                        actionsContainer.parentNode.insertBefore(formContainer, actionsContainer.nextSibling);
                    }
                }
                const parentInput = formContainer.querySelector('input[name="parent"]');
                if (parentInput && parentId) {
                    parentInput.value = parentId;
                }
                formContainer.classList.remove('d-none');
                formContainer.style.display = 'block';
                const textarea = formContainer.querySelector('textarea');
                if (textarea) textarea.focus();
            }
        });
    });

    const reactBtns = document.querySelectorAll('.react-btn');
    reactBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const action = this.getAttribute('data-action');
            const url = this.getAttribute('data-url');
            const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            const container = this.closest('.d-flex');

            const formData = new FormData();
            formData.append('action', action);

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                container.querySelector('.upvote-count').textContent = data.upvotes;
                container.querySelector('.downvote-count').textContent = data.downvotes;
            })
            .catch(error => {
                console.error('Error:', error);
            });
        });
    });

    // Star rating interaction
    const starContainers = document.querySelectorAll('.youtube-rating-stars');
    starContainers.forEach(container => {
        const labels = Array.from(container.querySelectorAll('.star-label'));
        
        function updateStars(index) {
            labels.forEach((lbl, i) => {
                if (i <= index) {
                    lbl.classList.add('active');
                } else {
                    lbl.classList.remove('active');
                }
            });
        }
        
        labels.forEach((label, index) => {
            label.addEventListener('mouseover', () => {
                updateStars(index);
            });
            
            label.addEventListener('click', () => {
                labels.forEach(lbl => lbl.classList.remove('selected'));
                label.classList.add('selected');
                const radio = label.querySelector('input[type="radio"]');
                if(radio) radio.checked = true;
            });
        });
        
        container.addEventListener('mouseleave', () => {
            labels.forEach(lbl => lbl.classList.remove('active'));
            // Restore selected state if any
            const selectedIndex = labels.findIndex(lbl => lbl.classList.contains('selected'));
            if (selectedIndex !== -1) {
                updateStars(selectedIndex);
            }
        });
        
        // Initialize selected
        const initialSelected = labels.findIndex(lbl => lbl.classList.contains('selected'));
        if (initialSelected !== -1) {
            updateStars(initialSelected);
        }
    });

    // hide all reply forms initially
    const forms = document.querySelectorAll('.reply-form-container');
    forms.forEach(function(f) {
        f.style.display = 'none';
    });

    // Read more toggles
    const textContents = document.querySelectorAll('.comment-text-collapsed');
    textContents.forEach(function(content) {
        if (content.scrollHeight > content.clientHeight) {
            const btn = content.nextElementSibling;
            if (btn && btn.classList.contains('read-more-btn')) {
                btn.classList.remove('d-none');
                btn.addEventListener('click', function() {
                    const expanded = this.getAttribute('data-expanded') === 'true';
                    const readMoreText = this.getAttribute('data-read-more');
                    const showLessText = this.getAttribute('data-show-less');
                    
                    if (expanded) {
                        content.classList.add('comment-text-collapsed');
                        this.textContent = readMoreText;
                        this.setAttribute('data-expanded', 'false');
                    } else {
                        content.classList.remove('comment-text-collapsed');
                        this.textContent = showLessText;
                        this.setAttribute('data-expanded', 'true');
                    }
                });
            }
        }
    });

    // Replies toggles
    const repliesToggles = document.querySelectorAll('.replies-toggle-btn');
    repliesToggles.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const target = document.getElementById(targetId);
            if (target) {
                target.classList.toggle('d-none');
                const expanded = this.getAttribute('data-expanded') === 'true';
                const icon = this.querySelector('i');
                if (expanded) {
                    this.setAttribute('data-expanded', 'false');
                    icon.classList.remove('fa-caret-up');
                    icon.classList.add('fa-caret-down');
                } else {
                    this.setAttribute('data-expanded', 'true');
                    icon.classList.remove('fa-caret-down');
                    icon.classList.add('fa-caret-up');
                }
            }
        });
    });
});
