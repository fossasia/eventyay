import { themeManager, loadEventTheme, loadOrganizerTheme } from './theme.js';

// Initialize theme system
(async () => {
  let inlineTokens = null;
  let inlineColorMode = null;
  let initialOrganizer = null;
  let initialEvent = null;

  const configEl = document.getElementById('eventyay-theme-config');
  if (configEl) {
    try {
      const config = JSON.parse(configEl.textContent || '{}');
      inlineTokens = config.inlineTokens;
      inlineColorMode = config.inlineColorMode;
      initialOrganizer = config.organizer;
      initialEvent = config.event;
    } catch (e) {
      console.error('Failed to parse theme configuration:', e);
    }
  }

  // Apply inline context tokens first so public pages render with saved theme
  // even if API is temporarily unavailable.
  if (inlineTokens && typeof inlineTokens === 'object') {
    themeManager.loadTheme(inlineTokens);
    if (inlineColorMode) {
      themeManager.setColorMode(inlineColorMode);
    }
  }

  const getContext = () => {
    const organizer = initialOrganizer || document.body?.dataset?.organizerSlug || null;
    const event = initialEvent || document.body?.dataset?.eventSlug || null;
    return { organizer, event };
  };

  const { organizer, event } = getContext();

  // Load event/organizer-specific theme if available
  if (organizer && event) {
    try {
      await loadEventTheme(organizer, event);
    } catch (error) {
      console.error('Failed to load theme from API:', error);
    }
  } else if (organizer) {
    try {
      // Organizer pages do not have an event slug.
      await loadOrganizerTheme(organizer);
    } catch (error) {
      console.error('Failed to load organizer theme from API:', error);
    }
  }

  // Check for theme toggle in UI
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('change', (e) => {
      const mode = e.target.checked ? 'dark' : 'light';
      themeManager.setColorMode(mode);
    });
  }

  // Watch for navigation and reload theme if needed.
  let lastOrganizer = organizer;
  let lastEvent = event;

  const checkAndReloadTheme = async () => {
    const { organizer: currentOrganizer, event: currentEvent } = getContext();

    if ((currentOrganizer !== lastOrganizer || currentEvent !== lastEvent) && currentOrganizer) {
      lastOrganizer = currentOrganizer;
      lastEvent = currentEvent;
      if (currentEvent) {
        await loadEventTheme(currentOrganizer, currentEvent);
      } else {
        await loadOrganizerTheme(currentOrganizer);
      }
    }
  };

  // Check on popstate/back-forward cache restoration.
  window.addEventListener('popstate', checkAndReloadTheme);
  window.addEventListener('pageshow', checkAndReloadTheme);
})();
