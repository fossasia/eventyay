/**
 * Centralized moment.js locale configuration
 * All locales imported once and cached by Webpack
 */

// Map of locale codes to moment.js locale names
export const MOMENT_LOCALE_MAP = {
  en: 'en',
  pt: 'pt',
  es: 'es',
  fr: 'fr',
  de: 'de',
  ru: 'ru',
  'zh-cn': 'zh-cn',
  ja: 'ja',
  ko: 'ko',
  it: 'it',
  pl: 'pl',
  tr: 'tr',
  he: 'he',
  th: 'th',
  vi: 'vi',
  da: 'da',
  no: 'no',
  fi: 'fi',
  tl: 'tl',
  et: 'et',
  lv: 'lv',
  sl: 'sl',
  sk: 'sk',
  hu: 'hu',
  cs: 'cs',
  el: 'el',
  ro: 'ro',
  bg: 'bg',
  hr: 'hr',
  sr: 'sr',
  mk: 'mk',
  sq: 'sq',
  mt: 'mt',
  is: 'is',
  fa: 'fa',
  ur: 'ur',
  ps: 'ps',
  ku: 'ku',
  ar: 'ar',
  bn: 'bn',
  gu: 'gu',
  mr: 'mr',
  ta: 'ta',
  te: 'te',
  ml: 'ml',
  kn: 'kn'
};

// Import all moment locales - runs once when module loads
const loadMomentLocales = () => {
  Object.values(MOMENT_LOCALE_MAP).forEach(locale => {
    try {
      require(`moment/locale/${locale}`);
    } catch (error) {
      console.warn(`⚠️ Moment locale not found: ${locale}`);
    }
  });
};

// Load on module initialization
loadMomentLocales();


/**
 * Get moment locale for a given language code
 * @param {string} languageCode - Language code (e.g., 'pt', 'en')
 * @returns {string} Moment locale name
 */
export function getMomentLocale(languageCode) {
  return MOMENT_LOCALE_MAP[languageCode] || 'en';
}

/**
 * Get all available locales
 * @returns {Array<string>} Array of locale codes
 */
export function getAvailableLocales() {
  return Object.keys(MOMENT_LOCALE_MAP);
}

export default MOMENT_LOCALE_MAP;
