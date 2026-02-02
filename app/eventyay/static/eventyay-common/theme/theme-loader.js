/**
 * Eventyay Theme Loader
 * Applies theme tokens as CSS variables at runtime
 */

export async function loadTheme({
  baseUrl = '/static/eventyay-common/theme/default.json',
  overrides = {},
  mode = 'light'
} = {}) {
  const response = await fetch(baseUrl);
  const baseTheme = await response.json();

  const mergedTheme = mergeThemes(baseTheme.tokens, overrides);

  applyThemeTokens(mergedTheme);
  applyMode(mode);
}

function mergeThemes(base, overrides) {
  const result = JSON.parse(JSON.stringify(base));

  function deepMerge(target, source) {
    for (const key in source) {
      if (
        typeof source[key] === 'object' &&
        !Array.isArray(source[key]) &&
        target[key]
      ) {
        deepMerge(target[key], source[key]);
      } else {
        target[key] = source[key];
      }
    }
  }

  deepMerge(result, overrides);
  return result;
}

function applyThemeTokens(tokens) {
  const root = document.documentElement;

  Object.entries(tokens).forEach(([category, values]) => {
    Object.entries(values).forEach(([name, value]) => {
      const cssVar = `--${category}-${name}`;
      root.style.setProperty(cssVar, value);
    });
  });
}

function applyMode(mode) {
  document.documentElement.setAttribute('data-theme', mode);
}
