/**
 * Centralized moment.js locale configuration with comprehensive input validation
 * Locale imports remain in App.vue where Vite can resolve them
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
  nb: 'nb',
  fi: 'fi',
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
  kn: 'kn',
};

/**
 * Validation configuration for locale functions
 */
const VALIDATION_CONFIG = {
  LOG_LEVEL: {
    DEBUG: 'debug',
    INFO: 'info',
    WARN: 'warn',
    ERROR: 'error'
  },
  REQUIRED_FIELDS: ['en', 'pt'],
  MAX_LOCALE_LENGTH: 10,
  ALLOWED_CHARS: /^[a-z]{2}(-[a-z]{2})?$/i
};

/**
 * Logger for validation events
 */
class LocaleValidator {
  constructor() {
    this.validationLog = [];
    this.isProduction = typeof process !== 'undefined' && process.env?.NODE_ENV === 'production';
  }

  log(level, context, message, additionalData = {}) {
    const logEntry = {
      timestamp: new Date().toISOString(),
      level,
      context,
      message,
      additionalData,
      stackTrace: new Error().stack
    };

    this.validationLog.push(logEntry);
    if (this.validationLog.length > 100) {
      this.validationLog.shift();
    }

    const logFn = {
      debug: console.debug,
      info: console.info,
      warn: console.warn,
      error: console.error
    }[level] || console.log;

    logFn(
      `[${context}] ${message}`,
      {
        details: additionalData,
        timestamp: logEntry.timestamp
      }
    );

    if (this.isProduction && level === 'error') {
      this.reportToServer(logEntry);
    }
  }

  reportToServer(logEntry) {
    try {
      fetch('/api/logs/validation-errors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logEntry)
      }).catch(() => {
        console.warn('Failed to report validation error');
      });
    } catch (error) {
      console.warn('Could not send validation report:', error.message);
    }
  }

  getHistory() {
    return [...this.validationLog];
  }

  clearHistory() {
    this.validationLog = [];
  }
}

const validator = new LocaleValidator();

/**
 * Check if input is valid language code type
 */
function isValidLanguageCodeType(value) {
  if (typeof value !== 'string') {
    return {
      valid: false,
      reason: `Expected string, got ${typeof value}`,
      received: value
    };
  }

  if (value.trim() === '') {
    return {
      valid: false,
      reason: 'Language code cannot be empty',
      received: value
    };
  }

  if (value.length > VALIDATION_CONFIG.MAX_LOCALE_LENGTH) {
    return {
      valid: false,
      reason: `Language code too long (max ${VALIDATION_CONFIG.MAX_LOCALE_LENGTH} chars)`,
      received: value
    };
  }

  return { valid: true };
}

/**
 * Check if language code exists in map
 */
function isKnownLocale(languageCode) {
  return MOMENT_LOCALE_MAP.hasOwnProperty(languageCode);
}

/**
 * Check if locale is required
 */
function isRequiredLocale(languageCode) {
  return VALIDATION_CONFIG.REQUIRED_FIELDS.includes(languageCode);
}

/**
 * Find similar locale using Levenshtein distance
 */
function findSimilarLocale(input, available, maxDistance = 2) {
  const distances = available.map(locale => ({
    locale,
    distance: levenshteinDistance(input.toLowerCase(), locale.toLowerCase())
  }));

  const closest = distances
    .filter(item => item.distance <= maxDistance)
    .sort((a, b) => a.distance - b.distance)[0];

  return closest ? closest.locale : null;
}

/**
 * Calculate Levenshtein distance between two strings
 */
function levenshteinDistance(a, b) {
  const matrix = [];

  for (let i = 0; i <= b.length; i++) {
    matrix[i] = [i];
  }

  for (let j = 0; j <= a.length; j++) {
    matrix[0][j] = j;
  }

  for (let i = 1; i <= b.length; i++) {
    for (let j = 1; j <= a.length; j++) {
      if (b.charAt(i - 1) === a.charAt(j - 1)) {
        matrix[i][j] = matrix[i - 1][j - 1];
      } else {
        matrix[i][j] = Math.min(
          matrix[i - 1][j - 1] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j] + 1
        );
      }
    }
  }

  return matrix[b.length][a.length];
}

/**
 * Get moment.js locale for a given language code
 * 
 * @param {string} languageCode - Language code (e.g., 'pt', 'en', 'zh-cn')
 * @param {Object} options - Configuration options
 * @param {boolean} options.strictMode - Throw error on invalid input
 * @param {boolean} options.throwOnUnknown - Throw instead of fallback
 * @param {string} options.logLevel - 'error', 'warn', 'info', 'debug'
 * @returns {string} Moment locale name
 * @throws {Error} If languageCode is invalid and strict mode enabled
 */
export function getMomentLocale(languageCode, options = {}) {
  const {
    strictMode = false,
    throwOnUnknown = false,
    logLevel = 'warn'
  } = options;

  // VALIDATION STEP 1: Check type and format
  const typeValidation = isValidLanguageCodeType(languageCode);
  
  if (!typeValidation.valid) {
    const errorMsg = 
      `[getMomentLocale] Invalid input: ${typeValidation.reason}. ` +
      `Received: ${JSON.stringify(languageCode)}`;

    validator.log('error', 'getMomentLocale', errorMsg, {
      expectedType: 'string',
      receivedType: typeof languageCode,
      receivedValue: typeValidation.received,
      availableLocales: Object.keys(MOMENT_LOCALE_MAP)
    });

    if (strictMode || throwOnUnknown) {
      throw new TypeError(errorMsg);
    }

    return 'en';
  }

  // VALIDATION STEP 2: Check if locale exists
  const localeExists = isKnownLocale(languageCode);
  
  if (!localeExists) {
    const availableLocales = Object.keys(MOMENT_LOCALE_MAP);
    const didYouMean = findSimilarLocale(languageCode, availableLocales);
    
    const errorMsg = 
      `[getMomentLocale] Unknown locale: "${languageCode}". ` +
      `Available: [${availableLocales.join(', ')}]` +
      (didYouMean ? `. Did you mean: ${didYouMean}?` : '');

    validator.log('error', 'getMomentLocale', errorMsg, {
      requested: languageCode,
      available: availableLocales,
      suggestion: didYouMean,
      fallback: 'en'
    });

    if (strictMode || throwOnUnknown) {
      throw new RangeError(errorMsg);
    }

    return 'en';
  }

  // VALIDATION STEP 3: Success
  const momentLocale = MOMENT_LOCALE_MAP[languageCode];
  
  validator.log('debug', 'getMomentLocale', 
    `Locale loaded: ${languageCode} → ${momentLocale}`, 
    {
      requested: languageCode,
      resolved: momentLocale
    }
  );

  return momentLocale;
}

/**
 * Get all available locales with metadata
 * 
 * @param {Object} options - Configuration options
 * @param {boolean} options.detailed - Return array of objects with metadata
 * @param {boolean} options.sortByName - Sort alphabetically
 * @param {boolean} options.includeRequired - Include only required locales
 * @returns {Array} Array of locale codes or objects
 */
export function getAvailableLocales(options = {}) {
  const {
    detailed = false,
    sortByName = false,
    includeRequired = true
  } = options;

  let locales = Object.keys(MOMENT_LOCALE_MAP);

  if (includeRequired) {
    locales = locales.filter(code => isRequiredLocale(code));
  }

  if (detailed) {
    locales = locales.map(code => ({
      code,
      momentLocale: MOMENT_LOCALE_MAP[code],
      isRequired: isRequiredLocale(code),
      name: code.toUpperCase()
    }));
  }

  if (sortByName) {
    locales.sort((a, b) => {
      const aName = typeof a === 'string' ? a : a.name;
      const bName = typeof b === 'string' ? b : b.name;
      return aName.localeCompare(bName);
    });
  }

  validator.log('debug', 'getAvailableLocales',
    `Retrieved ${locales.length} locale(s)`,
    { locales }
  );

  return locales;
}

/**
 * Validate language code without throwing errors
 * Returns validation result object
 */
export function validateLanguageCode(languageCode) {
  const result = {
    valid: false,
    code: languageCode,
    errors: [],
    warnings: [],
    suggestions: []
  };

  const typeValidation = isValidLanguageCodeType(languageCode);
  if (!typeValidation.valid) {
    result.errors.push(typeValidation.reason);
    result.valid = false;
    return result;
  }

  if (!isKnownLocale(languageCode)) {
    result.errors.push(`Locale "${languageCode}" not found`);
    
    const suggestion = findSimilarLocale(languageCode, Object.keys(MOMENT_LOCALE_MAP));
    if (suggestion) {
      result.suggestions.push(suggestion);
    }
    
    result.valid = false
    return result;
  }

  if (!isRequiredLocale(languageCode)) {
    result.warnings.push(`Locale "${languageCode}" is optional, not required`);
  }

  result.valid = true;
  result.resolvedLocale = MOMENT_LOCALE_MAP[languageCode];
  
  return result;
}

export default MOMENT_LOCALE_MAP;