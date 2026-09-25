/**
 * Frontend theme management utilities.
 *
 * Handles theme switching, CSS variable injection, and persistence.
 */

/**
 * Color mode type definition
 */
export type ColorMode = 'light' | 'dark' | 'auto';

/**
 * Theme configuration for an event or organization
 */
export interface ThemeConfig {
  colorMode: ColorMode;
  customTokens?: Record<string, any>;
  [key: string]: any;
}

/**
 * Theme context containing merged tokens and metadata
 */
export interface ThemeContext {
  tokens: Record<string, any>;
  isDark: boolean;
  colorMode: ColorMode;
}

class ThemeManager {
  private static instance: ThemeManager;
  private colorMode: ColorMode = 'auto';
  private tokens: Record<string, any> = {};
  private isDark = false;
  private storageKey = 'eventyay-theme-mode';
  private tokenPrefix = '--';
  private appliedVariables: Set<string> = new Set();

  private constructor() {
    this.initializeColorMode();
    this.observeSystemThemeChanges();
  }

  static getInstance(): ThemeManager {
    if (!ThemeManager.instance) {
      ThemeManager.instance = new ThemeManager();
    }
    return ThemeManager.instance;
  }

  private toKebabCase(segment: string): string {
    return String(segment).replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
  }

  private getNormalizedVarName(path: string[]): string {
    if (!path.length) {
      return this.tokenPrefix;
    }
    if (path[0] === 'colors' && path.length > 1) {
      const rest = path.slice(1).map((s) => this.toKebabCase(s)).join('-');
      return `${this.tokenPrefix}color-${rest}`;
    }
    const normalizedPath = path.map((s) => this.toKebabCase(s)).join('-');
    return `${this.tokenPrefix}${normalizedPath}`;
  }

  /**
   * Initialize color mode from storage or system preference
   */
  private initializeColorMode(): void {
    const stored = localStorage.getItem(this.storageKey) as ColorMode | null;
    if (stored && ['light', 'dark', 'auto'].includes(stored)) {
      this.colorMode = stored;
    }
    this.updateDarkMode();
  }

  /**
   * Observe system color scheme preference changes
   */
  private observeSystemThemeChanges(): void {
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
      mediaQuery.addEventListener('change', () => {
        if (this.colorMode === 'auto') {
          this.updateDarkMode();
        }
      });
    }
  }

  /**
   * Update dark mode flag based on color mode setting
   */
  private updateDarkMode(): void {
    if (this.colorMode === 'dark') {
      this.isDark = true;
    } else if (this.colorMode === 'light') {
      this.isDark = false;
    } else {
      this.isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    this.applyTheme();
  }

  /**
   * Set color mode (light, dark, auto)
   */
  setColorMode(mode: ColorMode): void {
    if (['light', 'dark', 'auto'].includes(mode)) {
      this.colorMode = mode;
      localStorage.setItem(this.storageKey, mode);
      this.updateDarkMode();
    }
  }

  /**
   * Get current color mode
   */
  getColorMode(): ColorMode {
    return this.colorMode;
  }

  /**
   * Check if currently in dark mode
   */
  isDarkMode(): boolean {
    return this.isDark;
  }

  /**
   * Load and apply theme tokens to the document
   */
  loadTheme(tokens: Record<string, any>): void {
    this.tokens = tokens;
    this.applyTheme();
  }

  /**
   * Apply theme tokens as CSS variables to document root
   */
  private applyTheme(): void {
    const root = document.documentElement;

    // Clear previously applied CSS variables
    for (const prop of this.appliedVariables) {
      root.style.removeProperty(prop);
    }
    this.appliedVariables.clear();

    const themePath = this.isDark ? ['darkMode'] : [];

    this.flattenAndApplyTokens(this.tokens, [], themePath);

    // Apply theme data attribute for CSS selectors
    root.setAttribute('data-theme', this.isDark ? 'dark' : 'light');
  }

  /**
   * Recursively flatten and apply tokens as CSS variables
   */
  private flattenAndApplyTokens(
    tokens: Record<string, any>,
    currentPath: string[],
    themePath: string[],
  ): void {
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
        // Apply both legacy and normalized variable names
        const legacyVarName = `${this.tokenPrefix}${path.join('-')}`;
        const normalizedVarName = this.getNormalizedVarName(path);
        root.style.setProperty(legacyVarName, String(value));
        this.appliedVariables.add(legacyVarName);
        if (normalizedVarName !== legacyVarName) {
          root.style.setProperty(normalizedVarName, String(value));
          this.appliedVariables.add(normalizedVarName);
        }
      }
    }
  }

  /**
   * Update a single token value at runtime
   */
  updateToken(path: string, value: string): void {
    const root = document.documentElement;
    const tokenPath = path.split('.');
    const varName = `${this.tokenPrefix}${path.replace(/\./g, '-')}`;
    const normalizedVarName = this.getNormalizedVarName(tokenPath);
    root.style.setProperty(varName, value);
    this.appliedVariables.add(varName);
    if (normalizedVarName !== varName) {
      root.style.setProperty(normalizedVarName, value);
      this.appliedVariables.add(normalizedVarName);
    }

    // Update internal tokens object
    const keys = path.split('.');
    let current = this.tokens;
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
  getToken(path: string): string | number | null {
    const keys = path.split('.');
    let current: any = this.tokens;
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
  getThemeContext(): ThemeContext {
    return {
      tokens: this.tokens,
      isDark: this.isDark,
      colorMode: this.colorMode,
    };
  }

  /**
   * Reset theme to defaults
   */
  reset(): void {
    const root = document.documentElement;
    for (const prop of this.appliedVariables) {
      root.style.removeProperty(prop);
    }
    this.appliedVariables.clear();

    this.colorMode = 'auto';
    localStorage.removeItem(this.storageKey);
    this.tokens = {};
    this.updateDarkMode();
  }
}

/**
 * Global theme manager instance
 */
export const themeManager = ThemeManager.getInstance();

/**
 * React/Vue-like hook for using theme in components
 * Usage: const {isDark, tokens} = useTheme()
 */
export function useTheme(): ThemeContext {
  return themeManager.getThemeContext();
}

/**
 * Fetch and load theme for a specific event
 */
export async function loadEventTheme(organizerSlug: string, eventSlug: string): Promise<void> {
  try {
    const response = await fetch(`/api/v1/organizers/${organizerSlug}/events/${eventSlug}/theme/`);
    if (response.ok) {
      const data = await response.json();
      if (data.isActive === false || data.is_active === false) {
        themeManager.reset();
        return;
      }
      themeManager.loadTheme(data.tokens || {});
      if (data.colorMode) {
        themeManager.setColorMode(data.colorMode);
      }
    }
  } catch (error) {
    console.error('Failed to load event theme:', error);
  }
}

/**
 * Fetch and load theme for a specific organizer
 */
export async function loadOrganizerTheme(organizerSlug: string): Promise<void> {
  try {
    const response = await fetch(`/api/v1/organizers/${organizerSlug}/themes/`);
    if (response.ok) {
      const data = await response.json();
      if (data.isActive === false || data.is_active === false) {
        themeManager.reset();
        return;
      }
      themeManager.loadTheme(data.tokens || {});
      if (data.colorMode) {
        themeManager.setColorMode(data.colorMode);
      }
    }
  } catch (error) {
    console.error('Failed to load organizer theme:', error);
  }
}

/**
 * Export theme configuration as JSON
 */
export function exportTheme(): Record<string, any> {
  return {
    colorMode: themeManager.getColorMode(),
    tokens: themeManager.getThemeContext().tokens,
  };
}
