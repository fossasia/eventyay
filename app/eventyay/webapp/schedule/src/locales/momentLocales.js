import moment from 'moment'

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
 * WHITELIST of allowed locales
 * Only these locales can be set in the application
 * Prevents invalid/untested locales from being used
 */
const MOMENT_LOCALE_WHITELIST = [
  'en',        // English
  'pt',        // Portuguese
  'es',        // Spanish
  'fr',        // French
  'de',        // German
  'ru',        // Russian
  'zh-cn',     // Chinese (Simplified)
  'ja',        // Japanese
  'ko',        // Korean
  'it',        // Italian
  'pl',        // Polish
  'tr'         // Turkish
];

/**
 * Check if a locale is in the whitelist
 */
export function isWhitelistedLocale(locale) {
  return MOMENT_LOCALE_WHITELIST.includes(locale.toLowerCase());
}

/**
 * Get the whitelist as array
 */
export function getLocaleWhitelist() {
  return [...MOMENT_LOCALE_WHITELIST];  // Return copy
}

/**
 * Validate that a locale is in the whitelist
 */
export function validateWhitelist() {
  const requiredLocales = ['en', 'pt'];
  const missingLocales = requiredLocales.filter(
    locale => !MOMENT_LOCALE_WHITELIST.includes(locale)
  );

  if (missingLocales.length > 0) {
    throw new Error(
      `Whitelist incomplete. Missing required locales: [${missingLocales.join(', ')}]`
    );
  }

  return {
    valid: true,
    whitelistSize: MOMENT_LOCALE_WHITELIST.length,
    requiredCount: requiredLocales.length,
    optionalCount: MOMENT_LOCALE_WHITELIST.length - requiredLocales.length
  };
}

/**
 * Locale Security Checker for audit logging
 */
class LocaleSecurityChecker {
  constructor() {
    this.attempts = [];
    this.maxAttempts = 100;
    this.alertThreshold = 10;
  }

  logAttempt(locale, success, error = null) {
    const attempt = {
      timestamp: new Date().toISOString(),
      locale,
      success,
      error: error?.message || null
    };

    this.attempts.push(attempt);

    if (this.attempts.length > this.maxAttempts) {
      this.attempts.shift();
    }

    const recentFailures = this.attempts
      .slice(-10)
      .filter(a => !a.success);

    if (recentFailures.length >= this.alertThreshold) {
      console.error(
        `🚨 [LocaleSecurity] High rate of locale failures detected. ` +
        `Possible attack or misconfiguration. ` +
        `Recent attempts:`,
        recentFailures
      );
    }
  }

  getAuditLog() {
    return {
      totalAttempts: this.attempts.length,
      successCount: this.attempts.filter(a => a.success).length,
      failureCount: this.attempts.filter(a => !a.success).length,
      recentAttempts: this.attempts.slice(-20),
      suspiciousActivity: this.detectSuspiciousPatterns()
    };
  }

  detectSuspiciousPatterns() {
    const patterns = [];

    const rapidFailures = this.attempts
      .slice(-5)
      .filter(a => !a.success);
    if (rapidFailures.length === 5) {
      patterns.push('Multiple rapid failures');
    }

    const invalidAttempts = {};
    this.attempts.forEach(a => {
      if (!a.success) {
        invalidAttempts[a.locale] = (invalidAttempts[a.locale] || 0) + 1;
      }
    });

    Object.entries(invalidAttempts).forEach(([locale, count]) => {
      if (count > 3) {
        patterns.push(`Repeated attempts for invalid locale: ${locale}`);
      }
    });

    return patterns;
  }

  clearAuditLog() {
    this.attempts = [];
  }
}

const localeSecurityChecker = new LocaleSecurityChecker();

/**
 * Set moment.js locale with whitelist validation
 * 
 * @param {string} locale - Locale code to set (e.g., 'pt', 'en')
 * @param {Object} options - Configuration options
 * @param {boolean} options.throwOnInvalid - Throw error if not whitelisted (default: false)
 * @param {boolean} options.logValidation - Log validation details (default: true)
 * @param {boolean} options.updateI18n - Update i18n instance (default: false)
 * @param {Object} options.i18nInstance - Vue i18n instance reference
 * @param {string} options.fallbackLocale - Fallback locale (default: 'en')
 * @returns {Object} Result object with success status, locale, and timestamp
 * @throws {Error} If throwOnInvalid is true and locale is not whitelisted
 */
export function setMomentLocale(locale, options = {}) {
  const {
    throwOnInvalid = false,
    logValidation = true,
    updateI18n = false,
    i18nInstance = null,
    fallbackLocale = 'en'
  } = options;

  // VALIDATION STEP 1: Type check
  let resolvedLocale = locale;
  let resolvedNormalizedLocale = typeof locale === 'string' ? locale.toLowerCase().trim() : fallbackLocale;

  if (typeof resolvedLocale !== 'string') {
    const error = new Error(
      `[setMomentLocale] Invalid type: expected string, got ${typeof resolvedLocale}`
    );

    if (logValidation) {
      console.error('❌ Type validation failed:', error);
    }

    localeSecurityChecker.logAttempt(resolvedLocale, false, error);

    if (throwOnInvalid) {
      throw error;
    }

    // Return failure for invalid type
    return {
      success: false,
      requestedLocale: locale,
      error: error.message,
      fallback: fallbackLocale,
      timestamp: new Date().toISOString()
    };
  }

  // VALIDATION STEP 2: Normalize locale (lowercase)
  resolvedNormalizedLocale = resolvedLocale.toLowerCase().trim();

  // VALIDATION STEP 3: Check whitelist
  const isWhitelisted = isWhitelistedLocale(resolvedNormalizedLocale);

  if (!isWhitelisted) {
    const error = new Error(
      `[setMomentLocale] Locale not whitelisted: "${resolvedLocale}". ` +
      `Allowed locales: [${MOMENT_LOCALE_WHITELIST.join(', ')}]`
    );

    if (logValidation) {
      console.error('❌ Whitelist validation failed:', {
        requested: resolvedLocale,
        normalized: resolvedNormalizedLocale,
        allowedLocales: MOMENT_LOCALE_WHITELIST,
        fallback: fallbackLocale,
        error: error.message
      });
    }

    localeSecurityChecker.logAttempt(resolvedLocale, false, error);

    if (throwOnInvalid) {
      throw error;
    }

    // Return failure result for non-whitelisted locale (not falling back silently)
    return {
      success: false,
      requestedLocale: locale,
      normalizedLocale: resolvedNormalizedLocale,
      error: error.message,
      allowedLocales: MOMENT_LOCALE_WHITELIST,
      fallback: fallbackLocale,
      timestamp: new Date().toISOString()
    };
  }

  // VALIDATION STEP 4: Actual moment locale setup
  try {
    // Get the actual moment locale name from map
    const momentLocaleCode = MOMENT_LOCALE_MAP[resolvedNormalizedLocale] || resolvedNormalizedLocale;

    // Set moment locale
    moment.locale(momentLocaleCode);

    // Verify it was actually set
    const currentMomentLocale = moment.locale();

    if (currentMomentLocale !== momentLocaleCode && currentMomentLocale !== resolvedNormalizedLocale) {
      console.warn(
        `⚠️ [setMomentLocale] Moment locale may not be available: ` +
        `requested ${momentLocaleCode}, got ${currentMomentLocale}`
      );
    }

    // STEP 5: Update i18n if requested
    if (updateI18n && i18nInstance) {
      i18nInstance.locale = resolvedNormalizedLocale;
      if (logValidation) {
        console.debug(`✅ i18n locale updated to: ${resolvedNormalizedLocale}`);
      }
    }

    // STEP 6: Return success result
    const result = {
      success: true,
      requestedLocale: locale,
      normalizedLocale: resolvedNormalizedLocale,
      momentLocale: momentLocaleCode,
      currentMomentLocale: moment.locale(),
      timestamp: new Date().toISOString(),
      whitelisted: true
    };

    if (logValidation) {
      console.log(`✅ [setMomentLocale] Success:`, result);
    }

    localeSecurityChecker.logAttempt(locale, true);
    return result;
  } catch (error) {
    console.error('❌ [setMomentLocale] Failed to set locale:', error);
    localeSecurityChecker.logAttempt(locale, false, error);

    if (throwOnInvalid) {
      throw error;
    }

    return {
      success: false,
      requestedLocale: locale,
      error: error.message,
      fallback: fallbackLocale,
      timestamp: new Date().toISOString()
    };
  }
}

/**
 * Get locale security audit log
 */
export function getLocaleSecurityAudit() {
  return localeSecurityChecker.getAuditLog();
}

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
    logLevel = 'warn',
    checkWhitelist = true  // NEW: validate against whitelist
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

  // VALIDATION STEP 2: Check whitelist if enabled
  if (checkWhitelist && !isWhitelistedLocale(languageCode)) {
    const availableLocales = Object.keys(MOMENT_LOCALE_MAP);
    const didYouMean = findSimilarLocale(languageCode, availableLocales);
    
    const errorMsg = 
      `[getMomentLocale] Locale not whitelisted: "${languageCode}". ` +
      `Whitelisted: [${MOMENT_LOCALE_WHITELIST.join(', ')}]` +
      (didYouMean ? `. Did you mean: ${didYouMean}?` : '');

    validator.log('error', 'getMomentLocale', errorMsg, {
      requested: languageCode,
      whitelist: MOMENT_LOCALE_WHITELIST,
      suggestion: didYouMean,
      fallback: 'en'
    });

    if (strictMode || throwOnUnknown) {
      throw new RangeError(errorMsg);
    }

    return 'en';
  }

  // VALIDATION STEP 3: Check if locale exists
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

  // VALIDATION STEP 4: Success
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

  // Check whitelist
  if (!isWhitelistedLocale(languageCode)) {
    result.errors.push(`Locale "${languageCode}" not whitelisted`);
    
    const suggestion = findSimilarLocale(languageCode, MOMENT_LOCALE_WHITELIST);
    if (suggestion) {
      result.suggestions.push(suggestion);
    }
    
    result.valid = false
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