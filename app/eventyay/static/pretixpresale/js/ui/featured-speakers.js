document.addEventListener('DOMContentLoaded', function() {
    const showMoreBtn = document.getElementById('show-more-speakers-btn');
    const btnContainer = document.getElementById('more-speakers-btn-container');
    
    if (showMoreBtn) {
        showMoreBtn.addEventListener('click', function() {
            // Show all hidden speakers
            const hiddenSpeakers = document.querySelectorAll('.hidden-speaker');
            hiddenSpeakers.forEach(function(speaker) {
                speaker.classList.remove('hidden-speaker');
            });
            
            // Hide the button
            btnContainer.style.display = 'none';
        });
    }
});
