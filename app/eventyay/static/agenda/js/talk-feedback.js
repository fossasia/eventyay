document.addEventListener("DOMContentLoaded", function() {
    const replyBtns = document.querySelectorAll('.reply-btn');
    replyBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const id = this.getAttribute('data-id');
            const formContainer = document.getElementById('reply-form-' + id);
            if (formContainer) {
                formContainer.classList.remove('d-none');
                formContainer.style.display = 'block';
            }
        });
    });

    const cancelBtns = document.querySelectorAll('.cancel-reply-btn');
    cancelBtns.forEach(function(btn) {
        btn.addEventListener('click', function() {
            const id = this.getAttribute('data-id');
            const formContainer = document.getElementById('reply-form-' + id);
            if (formContainer) {
                formContainer.classList.add('d-none');
                formContainer.style.display = 'none';
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
    
    // Main comment input focus to show actions
    const mainCommentInput = document.querySelector('.main-comment-input');
    const mainActionContainer = document.querySelector('.comment-action-container');
    const mainCancelBtn = document.querySelector('.comment-action-container button[type="reset"]');
    
    if (mainCommentInput && mainActionContainer) {
        mainCommentInput.addEventListener('focus', function() {
            mainActionContainer.classList.remove('d-none');
            mainActionContainer.classList.add('d-flex');
        });
        if (mainCancelBtn) {
            mainCancelBtn.addEventListener('click', function() {
                mainCommentInput.value = '';
                mainActionContainer.classList.add('d-none');
                mainActionContainer.classList.remove('d-flex');
            });
        }
    }

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
});
