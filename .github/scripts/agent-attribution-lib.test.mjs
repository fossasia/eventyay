import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import {
  AI_LABEL,
  MAX_BODY_LENGTH,
  parseExistingAttribution,
  detectAgentDetails,
  formatAttributionLine,
  appendAttributionToBody,
  runAgentAttribution,
} from './agent-attribution-lib.mjs';

const TEMPLATE = readFileSync(new URL('../pull_request_template.md', import.meta.url), 'utf8');

function makeGithub({ body, labels = [], commits = [], latestBody, labelError, updateError } = {}) {
  const calls = [];
  let getCount = 0;
  const github = {
    paginate: async () => commits.map((message) => ({ commit: { message } })),
    rest: {
      pulls: {
        get: async () => {
          getCount += 1;
          const current = getCount > 1 && latestBody !== undefined ? latestBody : body;
          return { data: { state: 'open', body: current, labels } };
        },
        update: async ({ pull_number, body: newBody }) => {
          if (updateError) throw updateError;
          calls.push({ type: 'update', pull_number, body: newBody });
        },
      },
      issues: {
        getLabel: async () => {
          if (labelError) throw labelError;
          return { data: { name: AI_LABEL } };
        },
        createLabel: async () => calls.push({ type: 'createLabel' }),
        addLabels: async ({ issue_number, labels: added }) => {
          calls.push({ type: 'addLabels', issue_number, labels: added });
        },
      },
    },
  };
  return { github, calls };
}

const core = { info() {}, warning() {}, setFailed() {} };
const context = (number) => ({
  repo: { owner: 'fossasia', repo: 'eventyay' },
  payload: { pull_request: { number } },
});

test('parseExistingAttribution parses full attribution line', () => {
  const line = 'Created with Claude Opus 5.5 in Claude Code, run from T3 Code.';
  assert.deepEqual(parseExistingAttribution(`Some text\n\n${line}`), {
    raw: line,
    action: 'Created',
    model: 'Claude Opus 5.5',
    harness: 'Claude Code',
    environment: 'T3 Code',
  });
});

test('parseExistingAttribution parses review attribution without environment', () => {
  const line = 'Reviewed with Gemini 2.0 Flash in Antigravity.';
  assert.deepEqual(parseExistingAttribution(`Review feedback\n\n${line}`), {
    raw: line,
    action: 'Reviewed',
    model: 'Gemini 2.0 Flash',
    harness: 'Antigravity',
    environment: null,
  });
});

test('parseExistingAttribution ignores HTML comments and prose', () => {
  assert.equal(parseExistingAttribution('Just normal text here.'), null);
  assert.equal(parseExistingAttribution(TEMPLATE), null);
  assert.equal(
    parseExistingAttribution('<!--\nCreated with Claude Opus 5.5 in Claude Code.\n-->'),
    null,
  );
});

test('detectAgentDetails detects Claude Code from Co-authored-by trailer', () => {
  const detected = detectAgentDetails({
    commitMessages: ['feat: x\n\nCo-authored-by: Claude Opus 5.5 <noreply@anthropic.com>'],
  });
  assert.deepEqual(detected, {
    model: 'Claude Opus 5.5',
    harness: 'Claude Code',
    environment: null,
    explicit: false,
  });
});

test('detectAgentDetails does not invent a model for harness-only trailers', () => {
  const detected = detectAgentDetails({
    commitMessages: ['fix: button\n\nCo-authored-by: Copilot <copilot@github.com>'],
  });
  assert.deepEqual(detected, {
    model: null,
    harness: 'GitHub Copilot',
    environment: null,
    explicit: false,
  });
  assert.equal(formatAttributionLine(detected), 'Created with GitHub Copilot.');
});

test('detectAgentDetails detects ChatGPT from a trailer', () => {
  const detected = detectAgentDetails({
    commitMessages: ['feat: y\n\nCo-authored-by: ChatGPT <noreply@openai.com>'],
  });
  assert.equal(detected.model, 'ChatGPT');
  assert.equal(formatAttributionLine(detected), 'Created with ChatGPT.');
});

test('detectAgentDetails recognises both Sonnet name orderings', () => {
  for (const name of ['Claude 3.5 Sonnet', 'Claude Sonnet 3.5']) {
    const detected = detectAgentDetails({
      commitMessages: [`feat\n\nCo-authored-by: ${name} <noreply@anthropic.com>`],
    });
    assert.equal(detected.model, 'Claude Sonnet 3.5');
  }
});

test('detectAgentDetails keeps unversioned Gemini names generic', () => {
  const detected = detectAgentDetails({
    commitMessages: ['feat\n\nCo-authored-by: Gemini Pro <gemini@antigravity.dev>'],
  });
  assert.equal(detected.model, 'Gemini');
  assert.equal(detected.harness, 'Antigravity');
});

test('detectAgentDetails uses explicit attribution from a commit message', () => {
  const detected = detectAgentDetails({
    commitMessages: ['feat: caching\n\nCreated with Gemini 2.0 Flash in Antigravity.'],
  });
  assert.deepEqual(detected, {
    model: 'Gemini 2.0 Flash',
    harness: 'Antigravity',
    environment: null,
    explicit: true,
  });
});

test('detectAgentDetails ignores incidental tool names in prose', () => {
  assert.equal(
    detectAgentDetails({
      body: 'Fix cursor position in the editor and update composer.json. Copilot mentioned in docs.',
      commitMessages: [
        'fix: cursor jumps on focus',
        'chore: bump composer deps, mention claude and gemini',
        'feat: x\n\nSigned-off-by: Dev <dev@example.com>',
      ],
    }),
    null,
  );
});

test('detectAgentDetails ignores the untouched PR template', () => {
  assert.equal(detectAgentDetails({ body: TEMPLATE, commitMessages: ['feat: human work'] }), null);
});

test('formatAttributionLine formats correctly with and without environment', () => {
  assert.equal(
    formatAttributionLine({ model: 'Claude Opus 5.5', harness: 'Claude Code', environment: 'T3 Code' }),
    'Created with Claude Opus 5.5 in Claude Code, run from T3 Code.',
  );
  assert.equal(
    formatAttributionLine({ model: 'Composer', harness: 'Cursor', environment: null }),
    'Created with Composer in Cursor.',
  );
});

test('appendAttributionToBody appends cleanly and is idempotent', () => {
  const line = 'Created with Claude in Claude Code.';
  const appended = appendAttributionToBody('## Problem\nBug fix', line);
  assert.equal(appended, '## Problem\nBug fix\n\nCreated with Claude in Claude Code.\n');
  assert.equal(appendAttributionToBody(appended, line), appended);
});

test('appendAttributionToBody moves mid-description attribution to the end', () => {
  const line = 'Created with Claude in Claude Code.';
  const body = `## Problem\n\n${line}\n\n## Verification\nTests pass`;
  assert.equal(
    appendAttributionToBody(body, line),
    `## Problem\n\n## Verification\nTests pass\n\n${line}\n`,
  );
});

test('appendAttributionToBody keeps attribution above bot summaries', () => {
  const line = 'Created with Claude in Claude Code.';
  const bot = '## Summary by Sourcery\n\nStuff.\n';
  const body = `## Problem\nFix\n\n${bot}`;
  const updated = appendAttributionToBody(body, line);
  assert.equal(updated, `## Problem\nFix\n\n${line}\n\n${bot}`);
  assert.equal(appendAttributionToBody(updated, line), updated);
});

test('runAgentAttribution labels and appends attribution from a trailer', async () => {
  const { github, calls } = makeGithub({
    body: '## Problem\nFix something',
    commits: ['feat: add stuff\n\nCo-authored-by: Claude <noreply@anthropic.com>'],
  });
  await runAgentAttribution({ github, context: context(42), core });

  assert.deepEqual(calls.map((c) => c.type), ['addLabels', 'update']);
  assert.ok(calls[1].body.trimEnd().endsWith('Created with Claude in Claude Code.'));
});

test('runAgentAttribution keeps edits made after the first fetch', async () => {
  const { github, calls } = makeGithub({
    body: '## Problem\nOld',
    latestBody: '## Problem\nEdited by author',
    commits: ['feat\n\nCo-authored-by: Claude <noreply@anthropic.com>'],
  });
  await runAgentAttribution({ github, context: context(7), core });

  const update = calls.find((c) => c.type === 'update');
  assert.equal(update.body, '## Problem\nEdited by author\n\nCreated with Claude in Claude Code.\n');
});

test('runAgentAttribution does nothing when attribution and label are present', async () => {
  const { github, calls } = makeGithub({
    body: '## Problem\nFix\n\nCreated with Claude Opus 5.5 in Claude Code, run from T3 Code.',
    labels: [{ name: AI_LABEL }],
    commits: ['feat: add stuff'],
  });
  await runAgentAttribution({ github, context: context(99), core });
  assert.deepEqual(calls, []);
});

test('runAgentAttribution makes no changes for a human PR from the template', async () => {
  const { github, calls } = makeGithub({
    body: TEMPLATE,
    commits: ['fix: cursor position in composer view'],
  });
  await runAgentAttribution({ github, context: context(5), core });
  assert.deepEqual(calls, []);
});

test('runAgentAttribution still labels when the body is too long to update', async () => {
  const { github, calls } = makeGithub({
    body: 'x'.repeat(MAX_BODY_LENGTH),
    commits: ['feat\n\nCo-authored-by: Claude <noreply@anthropic.com>'],
  });
  await runAgentAttribution({ github, context: context(8), core });
  assert.deepEqual(calls.map((c) => c.type), ['addLabels']);
});

test('runAgentAttribution applies the label even if the body update fails', async () => {
  const { github, calls } = makeGithub({
    body: '## Problem',
    commits: ['feat\n\nCo-authored-by: Claude <noreply@anthropic.com>'],
    updateError: Object.assign(new Error('boom'), { status: 500 }),
  });
  await assert.rejects(runAgentAttribution({ github, context: context(9), core }));
  assert.deepEqual(calls.map((c) => c.type), ['addLabels']);
});
