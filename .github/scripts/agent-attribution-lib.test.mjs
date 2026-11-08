import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  AI_LABEL,
  parseExistingAttribution,
  detectAgentDetails,
  formatAttributionLine,
  appendAttributionToBody,
  runAgentAttribution,
} from './agent-attribution-lib.mjs';

test('parseExistingAttribution parses t3code style line', () => {
  const line = 'Created with Claude Opus 5.5 in Claude Code, run from T3 Code.';
  const parsed = parseExistingAttribution(`Some text\n\n${line}`);
  assert.deepEqual(parsed, {
    raw: line,
    model: 'Claude Opus 5.5',
    harness: 'Claude Code',
    environment: 'T3 Code',
  });
});

test('parseExistingAttribution parses without run from', () => {
  const line = 'Created with Composer in Cursor.';
  const parsed = parseExistingAttribution(`Body\n\n${line}`);
  assert.deepEqual(parsed, {
    raw: line,
    model: 'Composer',
    harness: 'Cursor',
    environment: undefined,
  });
});

test('parseExistingAttribution returns null when absent', () => {
  assert.equal(parseExistingAttribution('Just normal text here.'), null);
});

test('detectAgentDetails detects Claude Code from Co-authored-by trailer', () => {
  const texts = ['feat: new feature\n\nCo-authored-by: Claude <noreply@anthropic.com>'];
  const detected = detectAgentDetails(texts);
  assert.deepEqual(detected, {
    model: 'Claude',
    harness: 'Claude Code',
    environment: null,
    explicit: false,
  });
});

test('detectAgentDetails detects Copilot from trailer', () => {
  const texts = ['fix: button\n\nCo-authored-by: Copilot <copilot@github.com>'];
  const detected = detectAgentDetails(texts);
  assert.deepEqual(detected, {
    model: 'AI Model',
    harness: 'GitHub Copilot',
    environment: null,
    explicit: false,
  });
});

test('detectAgentDetails detects Antigravity and Gemini from commit message', () => {
  const texts = ['feat: implement caching with Gemini 2.0 Flash in Antigravity'];
  const detected = detectAgentDetails(texts);
  assert.deepEqual(detected, {
    model: 'Gemini 2.0 Flash',
    harness: 'Antigravity',
    environment: null,
    explicit: false,
  });
});

test('detectAgentDetails returns null when no AI signals present', () => {
  const texts = ['feat: normal commit by human developer\n\nSigned-off-by: Dev <dev@example.com>'];
  assert.equal(detectAgentDetails(texts), null);
});

test('formatAttributionLine formats correctly with and without environment', () => {
  assert.equal(
    formatAttributionLine({ model: 'Claude Opus 4.6', harness: 'Claude Code', environment: 'T3 Code' }),
    'Created with Claude Opus 4.6 in Claude Code, run from T3 Code.',
  );
  assert.equal(
    formatAttributionLine({ model: 'Composer', harness: 'Cursor', environment: null }),
    'Created with Composer in Cursor.',
  );
});

test('appendAttributionToBody appends cleanly and avoids duplicates', () => {
  const body = '## Problem\nBug fix';
  const line = 'Created with Claude in Claude Code.';
  const appended = appendAttributionToBody(body, line);
  assert.equal(appended, '## Problem\nBug fix\n\nCreated with Claude in Claude Code.\n');

  // Should not duplicate if already present
  assert.equal(appendAttributionToBody(appended, line), appended.trimEnd());
});

test('runAgentAttribution updates PR body and adds label', async () => {
  const calls = [];
  const fakeGithub = {
    paginate: async () => [
      { commit: { message: 'feat: add stuff\n\nCo-authored-by: Claude <noreply@anthropic.com>' } },
    ],
    rest: {
      pulls: {
        get: async () => ({
          data: {
            state: 'open',
            body: '## Problem\nFix something',
            labels: [],
          },
        }),
        update: async ({ pull_number, body }) => {
          calls.push(`update PR #${pull_number} body: ${body.trim().split('\n').pop()}`);
        },
      },
      issues: {
        getLabel: async () => ({ data: { name: AI_LABEL } }),
        addLabels: async ({ issue_number, labels }) => {
          calls.push(`add labels to #${issue_number}: ${labels.join(', ')}`);
        },
      },
    },
  };

  const core = { info() {}, warning() {}, setFailed() {} };
  const context = {
    repo: { owner: 'fossasia', repo: 'eventyay' },
    payload: { pull_request: { number: 42 } },
  };

  await runAgentAttribution({ github: fakeGithub, context, core });

  assert.ok(calls.includes('update PR #42 body: Created with Claude in Claude Code.'));
  assert.ok(calls.includes('add labels to #42: ai-assisted'));
});

test('runAgentAttribution does not overwrite existing attribution in body', async () => {
  const calls = [];
  const fakeGithub = {
    paginate: async () => [
      { commit: { message: 'feat: add stuff' } },
    ],
    rest: {
      pulls: {
        get: async () => ({
          data: {
            state: 'open',
            body: '## Problem\nFix\n\nCreated with Claude Opus 5.5 in Claude Code, run from T3 Code.',
            labels: [{ name: AI_LABEL }],
          },
        }),
        update: async () => {
          calls.push('update called');
        },
      },
      issues: {
        getLabel: async () => ({ data: { name: AI_LABEL } }),
        addLabels: async () => {
          calls.push('addLabels called');
        },
      },
    },
  };

  const core = { info() {}, warning() {}, setFailed() {} };
  const context = {
    repo: { owner: 'fossasia', repo: 'eventyay' },
    payload: { pull_request: { number: 99 } },
  };

  await runAgentAttribution({ github: fakeGithub, context, core });

  // Update should NOT be called since attribution was already present
  assert.equal(calls.includes('update called'), false);
  // Add labels should NOT be called since label is already present
  assert.equal(calls.includes('addLabels called'), false);
});
