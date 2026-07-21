/**
 * Open the browser print dialog for a badge PDF preview iframe.
 */

function printBadgeFrame(frame) {
  if (!frame) {
    window.print();
    return;
  }
  try {
    frame.contentWindow.focus();
    frame.contentWindow.print();
  } catch (error) {
    console.error('badge-print: iframe print failed, falling back to window.print', error);
    window.print();
  }
}

function setupBadgePrint() {
  const frame = document.querySelector('[data-badge-print-frame]');
  const trigger = document.querySelector('[data-badge-print-trigger]');
  let printed = false;

  function triggerPrint() {
    if (printed) {
      return;
    }
    printed = true;
    printBadgeFrame(frame);
  }

  if (trigger) {
    trigger.addEventListener('click', () => {
      printed = false;
      printBadgeFrame(frame);
    });
  }

  if (!frame) {
    triggerPrint();
    return;
  }

  if (frame.contentDocument && frame.contentDocument.readyState === 'complete') {
    window.setTimeout(triggerPrint, 300);
  } else {
    frame.addEventListener('load', () => {
      window.setTimeout(triggerPrint, 300);
    });
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupBadgePrint);
} else {
  setupBadgePrint();
}
