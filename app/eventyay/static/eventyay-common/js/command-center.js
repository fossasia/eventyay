/**
 * Event Command Center ES Module (Issue #5092)
 * Handles interactive enhancements such as copyable public URL.
 */
export function initCommandCenter() {
  const copyBtn = document.getElementById('cc-copy-url-btn');
  const copyText = document.getElementById('cc-copy-btn-text');
  if (copyBtn && copyText) {
    copyBtn.addEventListener('click', async () => {
      const url = copyBtn.getAttribute('data-url');
      if (url) {
        try {
          await navigator.clipboard.writeText(url);
          const originalText = copyText.textContent;
          copyText.textContent = copyBtn.getAttribute('data-copied-text') || 'Copied!';
          setTimeout(() => {
            copyText.textContent = originalText;
          }, 2000);
        } catch (err) {
          console.error('Failed to copy public URL: ', err);
        }
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCommandCenter);
} else {
  initCommandCenter();
}
