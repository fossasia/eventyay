import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const webappDir = path.resolve(__dirname, '..');
const localesDir = path.join(webappDir, 'locales');
const enJsonPath = path.join(localesDir, 'en.json');

const searchDirs = [
  path.join(webappDir, 'schedule/src'),
  path.join(webappDir, 'schedule-editor/src'),
  path.join(webappDir, 'video/src'),
  path.join(webappDir, 'i18n')
];

function getSourceFiles(dir) {
  let results = [];
  if (!fs.existsSync(dir)) return results;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== 'node_modules' && entry.name !== 'dist' && entry.name !== 'tests') {
        results = results.concat(getSourceFiles(full));
      }
    } else if (/\.(vue|js|ts)$/.test(entry.name) && !entry.name.endsWith('.test.js')) {
      results.push(full);
    }
  }
  return results;
}

function unescapeStr(str) {
  return str
    .replace(/\\n/g, '\n')
    .replace(/\\t/g, '\t')
    .replace(/\\r/g, '\r')
    .replace(/\\'/g, "'")
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, '\\');
}

export function extractWebappStrings() {
  const files = searchDirs.flatMap(getSourceFiles);
  const extractedKeys = new Set();
  const quotedPattern = /(?:^|[^a-zA-Z0-9_])(?:(?:\$|this\.\$|this\.|i18n\.)?t|translate)\s*\(\s*(['"])((?:\\.|(?!\1)[^\\])*)\1/g;
  const backtickPattern = /(?:^|[^a-zA-Z0-9_])(?:(?:\$|this\.\$|this\.|i18n\.)?t|translate)\s*\(\s*`([^`$]*)`/g;

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    let match;

    quotedPattern.lastIndex = 0;
    while ((match = quotedPattern.exec(content)) !== null) {
      const str = unescapeStr(match[2]);
      if (str && !str.startsWith('http') && str.trim()) {
        extractedKeys.add(str);
      }
    }

    backtickPattern.lastIndex = 0;
    while ((match = backtickPattern.exec(content)) !== null) {
      const str = unescapeStr(match[1]);
      if (str && !str.includes('${') && !str.startsWith('http') && str.trim()) {
        extractedKeys.add(str);
      }
    }
  }

  let enData = {};
  if (fs.existsSync(enJsonPath)) {
    try {
      enData = JSON.parse(fs.readFileSync(enJsonPath, 'utf8'));
    } catch (e) {
      console.warn(`[webapp:i18n] Could not parse existing en.json: ${e.message}`);
    }
  }

  let newKeysCount = 0;
  for (const key of extractedKeys) {
    if (!(key in enData)) {
      enData[key] = key;
      newKeysCount++;
    }
  }

  // Ensure all keys map to themselves in en.json if empty
  for (const [k, v] of Object.entries(enData)) {
    if (!v) enData[k] = k;
  }

  // Sort keys alphabetically for clean, deterministic git diffs
  const sortedData = {};
  for (const key of Object.keys(enData).sort()) {
    sortedData[key] = enData[key];
  }

  fs.mkdirSync(localesDir, { recursive: true });
  fs.writeFileSync(enJsonPath, JSON.stringify(sortedData, null, 2) + '\n', 'utf8');

  console.log(`[webapp:i18n] Scanned ${files.length} files across webapps.`);
  console.log(`[webapp:i18n] Extracted ${extractedKeys.size} UI strings.`);
  console.log(`[webapp:i18n] Updated en.json with ${Object.keys(sortedData).length} total keys (${newKeysCount} new).`);
  return { filesCount: files.length, totalKeys: Object.keys(sortedData).length, newKeysCount };
}

if (process.argv[1] === __filename) {
  extractWebappStrings();
}
