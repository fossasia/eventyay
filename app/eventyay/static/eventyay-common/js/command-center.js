/**
 * Event Command Center ES Module (Issue #5092)
 * Handles interactive enhancements such as copyable public URL.
 */

async function copyTextFallback(text) {
  const textArea = document.createElement('textarea');
  textArea.value = text;
  textArea.setAttribute('readonly', '');
  textArea.style.position = 'fixed';
  textArea.style.left = '-9999px';
  textArea.style.top = '0';
  textArea.style.opacity = '0';
  document.body.appendChild(textArea);
  textArea.focus();
  textArea.select();
  try {
    const successful = document.execCommand('copy');
    if (!successful) {
      throw new Error('execCommand copy returned false');
    }
  } finally {
    document.body.removeChild(textArea);
  }
}

async function writeClipboardText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      await copyTextFallback(text);
      return;
    }
  }
  await copyTextFallback(text);
}

export function initCommandCenter() {
  const copyBtn = document.getElementById('cc-copy-url-btn');
  const copyText = document.getElementById('cc-copy-btn-text');
  if (copyBtn && copyText) {
    const originalText = copyText.textContent;
    let resetTimer = null;

    copyBtn.addEventListener('click', async () => {
      const url = copyBtn.getAttribute('data-url');
      if (!url) return;

      try {
        await writeClipboardText(url);
        if (resetTimer) {
          clearTimeout(resetTimer);
        }
        copyText.textContent = copyBtn.getAttribute('data-copied-text') || 'Copied!';
        resetTimer = setTimeout(() => {
          copyText.textContent = originalText;
          resetTimer = null;
        }, 2000);
      } catch (err) {
        console.error('Failed to copy public URL: ', err);
      }
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initCommandCenter);
} else {
  initCommandCenter();
}
