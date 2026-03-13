/**
 * Frontend theme management utilities.
 *
 * Handles theme switching, CSS variable injection, and persistence.
 */

class ThemeManager {
  #colorMode = 'auto';
  #tokens = {};
  #isDark = false;
  #storageKey = 'eventyay-theme-mode';
  #tokenPrefix = '--';

  static #instance = null;

  constructor() {
    this.initializeColorMode();
    this.observeSystemThemeChanges();
  }

  static getInstance() {
    if (!ThemeManager.#instance) {
      ThemeManager.#instance = new ThemeManager();
    }
    return ThemeManager.#instance;
  }

  /**
   * Initialize color mode from storage or system preference
   */
  initializeColorMode() {
    const stored = localStorage.getItem(this.#storageKey);
    if (stored && ['light', 'dark', 'auto'].includes(stored)) {
      this.#colorMode = stored;
    }
    this.updateDarkMode();
  }

  /**
   * Observe system color scheme preference changes
   */
  observeSystemThemeChanges() {
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      mediaQuery.addEventListener('change', () => {
        if (this.#colorMode === 'auto') {
          this.updateDarkMode();
        }
      });
    }
  }

  /**
   * Update dark mode flag based on color mode setting
   */
  updateDarkMode() {
    if (this.#colorMode === 'dark') {
      this.#isDark = true;
    } else if (this.#colorMode === 'light') {
      this.#isDark = false;
    } else {
      this.#isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    this.applyTheme();
  }

  /**
   * Set color mode (light, dark, auto)
   */
  setColorMode(mode) {
    if (['light', 'dark', 'auto'].includes(mode)) {
      this.#colorMode = mode;
      localStorage.setItem(this.#storageKey, mode);
      this.updateDarkMode();
    }
  }

  /**
   * Get current color mode
   */
  getColorMode() {
    return this.#colorMode;
  }

  /**
   * Check if currently in dark mode
   */
  isDarkMode() {
    return this.#isDark;
  }

  /**
   * Load and apply theme tokens to the document
   */
  loadTheme(tokens) {
    this.#tokens = tokens;
    this.applyTheme();
  }

  /**
   * Apply theme tokens as CSS variables to document root
   */
  applyTheme() {
    const root = document.documentElement;
    const themePath = this.#isDark ? ['darkMode'] : [];

    this.flattenAndApplyTokens(this.#tokens, [], themePath);

    // Apply theme data attribute for CSS selectors
    root.setAttribute('data-theme', this.#isDark ? 'dark' : 'light');
  }

  /**
   * Recursively flatten and apply tokens as CSS variables
   */
  flattenAndApplyTokens(tokens, currentPath = [], themePath = []) {
    const root = document.documentElement;
    let source = tokens;

    // Navigate to theme-specific path if provided
    for (const segment of themePath) {
      if (source[segment]) {
        source = source[segment];
      }
    }

    for (const [key, value] of Object.entries(source)) {
      const path = [...currentPath, key];

      if (value === null || value === undefined) {
        continue;
      }

      if (typeof value === 'object' && !Array.isArray(value)) {
        // Recurse for nested objects
        this.flattenAndApplyTokens(value, path, []);
      } else if (typeof value === 'string' || typeof value === 'number') {
        // Apply both legacy and normalized variable names for compatibility.
        const legacyVarName = `${this.#tokenPrefix}${path.join('-')}`;
        const normalizedVarName = this.getNormalizedVarName(path);
        root.style.setProperty(legacyVarName, String(value));
        if (normalizedVarName !== legacyVarName) {
          root.style.setProperty(normalizedVarName, String(value));
        }
      }
    }
  }

  toKebabCase(segment) {
    return String(segment).replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
  }

  getNormalizedVarName(path) {
    if (!path.length) {
      return `${this.#tokenPrefix}`;
    }

    // Map `colors.primary` -> `--color-primary` (the variables used across Eventyay CSS).
    if (path[0] === 'colors' && path.length > 1) {
      const rest = path.slice(1).map((s) => this.toKebabCase(s)).join('-');
      return `${this.#tokenPrefix}color-${rest}`;
    }

    const normalizedPath = path.map((s) => this.toKebabCase(s)).join('-');
    return `${this.#tokenPrefix}${normalizedPath}`;
  }

  /**
   * Update a single token value at runtime
   */
  updateToken(path, value) {
    const root = document.documentElement;
    const tokenPath = path.split('.');
    const varName = `${this.#tokenPrefix}${path.replace(/\./g, '-')}`;
    const normalizedVarName = this.getNormalizedVarName(tokenPath);
    root.style.setProperty(varName, value);
    if (normalizedVarName !== varName) {
      root.style.setProperty(normalizedVarName, value);
    }

    // Update internal tokens object
    const keys = tokenPath;
    let current = this.#tokens;
    for (let i = 0; i < keys.length - 1; i++) {
      if (!current[keys[i]]) {
        current[keys[i]] = {};
      }
      current = current[keys[i]];
    }
    current[keys[keys.length - 1]] = value;
  }

  /**
   * Get a token value
   */
  getToken(path) {
    const keys = path.split('.');
    let current = this.#tokens;
    for (const key of keys) {
      if (current && typeof current === 'object' && key in current) {
        current = current[key];
      } else {
        return null;
      }
    }
    return current;
  }

  /**
   * Get current theme context
   */
  getThemeContext() {
    return {
      tokens: this.#tokens,
      isDark: this.#isDark,
      colorMode: this.#colorMode,
    };
  }

  /**
   * Reset theme to defaults
   */
  reset() {
    this.#colorMode = 'auto';
    localStorage.removeItem(this.#storageKey);
    this.#tokens = {};
    this.updateDarkMode();
  }
}

/**
 * Global theme manager instance
 */
export const themeManager = ThemeManager.getInstance();

/**
 * Use theme in components
 */
export function useTheme() {
  return themeManager.getThemeContext();
}

/**
 * Fetch and load theme for a specific event
 */
export async function loadEventTheme(organizerSlug, eventSlug) {
  try {
    const url = `/api/v1/organizers/${organizerSlug}/events/${eventSlug}/theme/`;
    console.log('Fetching theme from:', url);
    
    const response = await fetch(url);
    if (!response.ok) {
      console.warn(`Theme API returned ${response.status}: ${response.statusText}`);
      return false;
    }
    
    const data = await response.json();
    console.log('Theme data received:', data);
    
    // Load tokens from the API response
    const tokens = data.tokens || {};
    if (Object.keys(tokens).length > 0) {
      themeManager.loadTheme(tokens);
      console.log('Tokens loaded successfully');
    } else {
      console.warn('No tokens found in theme data');
    }
    
    // Handle both colorMode (camelCase) and color_mode (snake_case)
    const colorMode = data.colorMode || data.color_mode || 'auto';
    themeManager.setColorMode(colorMode);
    console.log('Color mode set to:', colorMode);
    
    // Store loaded theme in sessionStorage to persist across navigation
    try {
      sessionStorage.setItem(
        `theme-${organizerSlug}-${eventSlug}`,
        JSON.stringify({ tokens, colorMode })
      );
      console.log('Theme stored in sessionStorage');
    } catch (error) {
      console.warn('Could not store theme in sessionStorage:', error);
    }
    
    return true;
  } catch (error) {
    console.error('Failed to load event theme:', error);
    
    // Try to restore from sessionStorage if API fails
    try {
      const cached = sessionStorage.getItem(`theme-${organizerSlug}-${eventSlug}`);
      if (cached) {
        const { tokens, colorMode } = JSON.parse(cached);
        themeManager.loadTheme(tokens);
        themeManager.setColorMode(colorMode);
        console.log('Theme restored from sessionStorage cache');
        return true;
      }
    } catch (cacheError) {
      console.warn('Could not restore from cache:', cacheError);
    }
    
    return false;
  }
}

/**
 * Fetch and load organizer theme for organizer profile/public pages.
 */
export async function loadOrganizerTheme(organizerSlug) {
  try {
    const url = `/api/v1/organizers/${organizerSlug}/themes/`;
    console.log('Fetching organizer theme from:', url);

    const response = await fetch(url);
    if (!response.ok) {
      console.warn(`Organizer theme API returned ${response.status}: ${response.statusText}`);
      return false;
    }

    const data = await response.json();
    console.log('Organizer theme data received:', data);

    const tokens = data.tokens || {};
    if (Object.keys(tokens).length > 0) {
      themeManager.loadTheme(tokens);
      console.log('Organizer tokens loaded successfully');
    } else {
      console.warn('No tokens found in organizer theme data');
    }

    const colorMode = data.colorMode || data.color_mode || 'auto';
    themeManager.setColorMode(colorMode);
    console.log('Organizer color mode set to:', colorMode);

    return true;
  } catch (error) {
    console.error('Failed to load organizer theme:', error);
    return false;
  }
}

/**
 * Export theme configuration as JSON
 */
export function exportTheme() {
  return {
    colorMode: themeManager.getColorMode(),
    tokens: themeManager.getThemeContext().tokens,
  };
}
