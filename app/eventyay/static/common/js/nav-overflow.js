'use strict';

/**
 * Responsive "More" overflow menu for public event header navigation.
 * Trailing tabs move into More. Visible tabs stay stable across pages —
 * the active page inside More marks the More trigger, not the main bar.
 */

const OVERFLOW_INIT_FLAG = 'eventyayNavOverflowInit';
const MEASURING_CLASS = 'nav-overflow-measuring';
const READY_CLASS = 'nav-overflow-ready';
const WIDTH_TOLERANCE = 1;

const initNavOverflow = () => {
  if (document.documentElement.dataset[OVERFLOW_INIT_FLAG] === '1') {
    return;
  }
  document.documentElement.dataset[OVERFLOW_INIT_FLAG] = '1';

  const scrollContainer = document.querySelector('.presale-tabs-scroll');
  if (!scrollContainer) {
    return;
  }

  const overflowMenu = scrollContainer.querySelector('.nav-overflow-menu');
  if (!overflowMenu) {
    scrollContainer.classList.add(READY_CLASS);
    return;
  }

  const overflowItems = overflowMenu.querySelector('.nav-overflow-items');
  const overflowTrigger = overflowMenu.querySelector('.nav-overflow-trigger');
  if (!overflowItems || !overflowTrigger) {
    scrollContainer.classList.add(READY_CLASS);
    return;
  }

  const allTabs = [];
  scrollContainer.querySelectorAll(':scope > .header-tab').forEach((tab, index) => {
    tab.dataset.navIndex = String(index);
    allTabs.push(tab);
  });

  if (allTabs.length === 0) {
    scrollContainer.classList.add(READY_CLASS);
    return;
  }

  let rafId = null;
  let lastWidth = null;
  let needsReflowAfterClose = false;

  const horizontalMargin = (element) => {
    const style = getComputedStyle(element);
    return parseFloat(style.marginLeft) + parseFloat(style.marginRight);
  };

  const restoreTabs = () => {
    allTabs.forEach((tab) => {
      if (tab.parentNode !== scrollContainer) {
        scrollContainer.insertBefore(tab, overflowMenu);
      }
    });
  };

  const updateActiveState = () => {
    const activeChild = overflowItems.querySelector(
      '.header-tab.active, .header-tab.underline'
    );
    const inMore = Boolean(activeChild);
    overflowTrigger.classList.toggle('active', inMore);
    overflowMenu.classList.toggle('active', inMore);
  };

  const positionDropdown = () => {
    const panel = overflowItems;

    if (!overflowMenu.open) {
      panel.style.top = '';
      panel.style.left = '';
      panel.style.width = '';
      return;
    }

    void panel.offsetWidth;

    const triggerRect = overflowTrigger.getBoundingClientRect();
    const width = Math.min(
      Math.max(panel.scrollWidth, 220),
      window.innerWidth - 16
    );
    let left = triggerRect.left;
    if (left + width > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - width - 8);
    }
    if (left < 8) {
      left = 8;
    }

    let top = triggerRect.bottom + 4;
    const maxHeight = Math.min(window.innerHeight * 0.7, 420);
    if (top + Math.min(panel.scrollHeight, maxHeight) > window.innerHeight - 8) {
      const above = triggerRect.top - 4 - Math.min(panel.scrollHeight, maxHeight);
      if (above > 8) {
        top = above;
      }
    }

    panel.style.top = `${Math.round(top)}px`;
    panel.style.left = `${Math.round(left)}px`;
    panel.style.width = `${Math.round(width)}px`;
  };

  const measureWidths = () => {
    restoreTabs();
    overflowMenu.hidden = true;

    void scrollContainer.offsetWidth;

    overflowMenu.hidden = false;
    const moreWidth = overflowMenu.offsetWidth + horizontalMargin(overflowMenu);
    overflowMenu.hidden = true;

    const tabWidths = allTabs.map(
      (tab) => tab.offsetWidth + horizontalMargin(tab)
    );

    return {
      containerWidth: scrollContainer.clientWidth,
      moreWidth,
      tabWidths,
      totalTabsWidth: tabWidths.reduce((sum, width) => sum + width, 0),
    };
  };

  const applyCutoff = (cutoffIndex) => {
    restoreTabs();
    if (cutoffIndex < 0 || cutoffIndex >= allTabs.length) {
      overflowMenu.hidden = true;
      overflowMenu.open = false;
      overflowTrigger.classList.remove('active');
      overflowMenu.classList.remove('active');
      return;
    }

    for (let i = cutoffIndex; i < allTabs.length; i += 1) {
      overflowItems.appendChild(allTabs[i]);
    }
    overflowMenu.hidden = false;
    updateActiveState();
  };

  const reflow = () => {
    rafId = null;

    if (overflowMenu.open) {
      needsReflowAfterClose = true;
      return;
    }

    const width = scrollContainer.clientWidth;
    if (
      lastWidth !== null &&
      width === lastWidth &&
      scrollContainer.classList.contains(READY_CLASS)
    ) {
      return;
    }

    scrollContainer.classList.add(MEASURING_CLASS);

    const measured = measureWidths();
    lastWidth = measured.containerWidth;

    let cutoffIndex = -1;
    if (measured.totalTabsWidth > measured.containerWidth + WIDTH_TOLERANCE) {
      const availableForTabs = Math.max(
        0,
        measured.containerWidth - measured.moreWidth + WIDTH_TOLERANCE
      );
      let cumulativeWidth = 0;
      cutoffIndex = allTabs.length;
      for (let i = 0; i < allTabs.length; i += 1) {
        if (cumulativeWidth + measured.tabWidths[i] > availableForTabs) {
          cutoffIndex = i;
          break;
        }
        cumulativeWidth += measured.tabWidths[i];
      }
    }

    applyCutoff(cutoffIndex);
    scrollContainer.classList.remove(MEASURING_CLASS);
    scrollContainer.classList.add(READY_CLASS);
    needsReflowAfterClose = false;
  };

  const scheduleReflow = () => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
    }
    rafId = requestAnimationFrame(reflow);
  };

  overflowMenu.addEventListener('toggle', () => {
    if (overflowMenu.open) {
      requestAnimationFrame(() => {
        positionDropdown();
        requestAnimationFrame(positionDropdown);
      });
    } else if (needsReflowAfterClose) {
      lastWidth = null;
      scheduleReflow();
    }
  });

  window.addEventListener(
    'scroll',
    () => {
      if (overflowMenu.open) {
        positionDropdown();
      }
    },
    true
  );

  reflow();

  if (typeof ResizeObserver !== 'undefined') {
    const observer = new ResizeObserver(scheduleReflow);
    observer.observe(scrollContainer);
  } else {
    window.addEventListener('resize', scheduleReflow);
  }

  window.addEventListener('hashchange', () => {
    lastWidth = null;
    scheduleReflow();
  });
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNavOverflow);
} else {
  initNavOverflow();
}
