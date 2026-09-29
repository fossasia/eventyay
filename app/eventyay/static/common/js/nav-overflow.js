'use strict';

/**
 * Responsive "More" overflow menu for public event header navigation.
 * Moves tabs that do not fit into a More dropdown on all viewport sizes.
 */

const OVERFLOW_INIT_FLAG = 'eventyayNavOverflowInit';
const MEASURING_CLASS = 'nav-overflow-measuring';
const READY_CLASS = 'nav-overflow-ready';

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
    const hasActiveChild = overflowItems.querySelector(
      '.header-tab.active, .header-tab.underline'
    );
    overflowTrigger.classList.toggle('active', Boolean(hasActiveChild));
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
      overflowTrigger.classList.remove('active');
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

    // Opening the More menu can trigger ResizeObserver; never rebuild while open.
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
    if (measured.totalTabsWidth > measured.containerWidth) {
      const availableForTabs = Math.max(
        0,
        measured.containerWidth - measured.moreWidth
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
    if (!overflowMenu.open && needsReflowAfterClose) {
      lastWidth = null;
      scheduleReflow();
    }
  });

  reflow();

  if (typeof ResizeObserver !== 'undefined') {
    const observer = new ResizeObserver(scheduleReflow);
    observer.observe(scrollContainer);
  } else {
    window.addEventListener('resize', scheduleReflow);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initNavOverflow);
} else {
  initNavOverflow();
}
