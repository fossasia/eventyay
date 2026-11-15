import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { latestApprovers, resolvePrNumbers, runApprovalLabels, wantedLabel } from './approval-labels-lib.mjs';

const review = (login, state) => ({ user: { login }, state });

// Minimal fake of the github-script client. `prs` maps PR number -> { labels, reviews,
// author?, state?, failGet? }; `perms` maps login -> role (missing = not a collaborator).
function fakeGithub({ prs = {}, perms = {}, forkPrs = [], openPrs = [] } = {}) {
  const calls = [];
  const listReviews = async () => {};
  const list = async () => {};
  const github = {
    calls,
    paginate: async (fn, params) => {
      if (fn === listReviews) return prs[params.pull_number].reviews;
      if (fn === list) {
        if (params.head) {
          calls.push(`list ${params.head}`);
          return forkPrs.map(number => ({ number }));
        }
        calls.push('list open');
        return openPrs;
      }
      throw new Error('unexpected paginate');
    },
    rest: {
      pulls: {
        listReviews,
        list,
        get: async ({ pull_number }) => {
          const pr = prs[pull_number];
          if (pr.failGet) throw Object.assign(new Error('boom'), { status: 500 });
          return {
            data: {
              state: pr.state ?? 'open',
              user: { login: pr.author ?? 'author' },
              labels: pr.labels.map(name => ({ name })),
            },
          };
        },
      },
      repos: {
        getCollaboratorPermissionLevel: async ({ username }) => {
          const role = perms[username];
          if (!role) throw Object.assign(new Error('Not Found'), { status: 404 });
          // Mirror the API: legacy `permission` maps maintain -> write, triage -> read.
          const permission = { maintain: 'write', triage: 'read' }[role] ?? role;
          return { data: { permission, role_name: role } };
        },
      },
      issues: {
        addLabels: async ({ issue_number, labels }) => calls.push(`#${issue_number} +${labels[0]}`),
        removeLabel: async ({ issue_number, name }) => calls.push(`#${issue_number} -${name}`),
      },
    },
  };
  return github;
}

function fakeCore() {
  return { failed: null, errors: [], info() {}, error(m) { this.errors.push(m); }, setFailed(m) { this.failed = m; } };
}

const dispatch = n => ({ eventName: 'workflow_dispatch', payload: { inputs: { 'pr-number': String(n) } }, repo: { owner: 'o', repo: 'r' } });

const workflowRun = run => ({ eventName: 'workflow_run', payload: { workflow_run: run }, repo: { owner: 'o', repo: 'r' } });

async function sync(pr, perms) {
  const github = fakeGithub({ prs: { 1: pr }, perms });
  const core = fakeCore();
  await runApprovalLabels({ github, context: dispatch(1), core });
  return { calls: github.calls, core };
}

test('latestApprovers keeps only the latest decisive review per reviewer', () => {
  const reviews = [
    review('a', 'APPROVED'), review('a', 'COMMENTED'),            // comment keeps approval
    review('b', 'APPROVED'), review('b', 'CHANGES_REQUESTED'),    // overridden
    review('c', 'CHANGES_REQUESTED'), review('c', 'APPROVED'),    // re-approved
    review('d', 'APPROVED'), review('d', 'DISMISSED'),            // dismissed
    review('author', 'APPROVED'),                                 // author ignored
    { user: null, state: 'APPROVED' },                            // deleted user
  ];
  assert.deepEqual(latestApprovers(reviews, 'author'), ['a', 'c']);
});

test('wantedLabel maps approval counts to labels', () => {
  assert.equal(wantedLabel(0, 3, 'approvals: '), null);
  assert.equal(wantedLabel(1, 3, 'approvals: '), 'approvals: 1/3');
  assert.equal(wantedLabel(2, 3, 'approvals: '), 'approvals: 2/3');
  assert.equal(wantedLabel(3, 3, 'approvals: '), null);
  assert.equal(wantedLabel(4, 3, 'approvals: '), null);
});

test('first approval adds 1/3', async () => {
  const { calls } = await sync({ labels: [], reviews: [review('a', 'APPROVED')] }, { a: 'write' });
  assert.deepEqual(calls, ['#1 +approvals: 1/3']);
});

test('second approval adds 2/3 before removing 1/3', async () => {
  const { calls } = await sync(
    { labels: ['approvals: 1/3', 'backend'], reviews: [review('a', 'APPROVED'), review('b', 'APPROVED')] },
    { a: 'write', b: 'admin' },
  );
  assert.deepEqual(calls, ['#1 +approvals: 2/3', '#1 -approvals: 1/3']);
});

test('third approval removes 2/3', async () => {
  const { calls } = await sync(
    { labels: ['approvals: 2/3'], reviews: ['a', 'b', 'c'].map(l => review(l, 'APPROVED')) },
    { a: 'write', b: 'write', c: 'maintain' },
  );
  assert.deepEqual(calls, ['#1 -approvals: 2/3']);
});

test('dismissed approval drops back from 1/3 to none', async () => {
  const { calls } = await sync(
    { labels: ['approvals: 1/3'], reviews: [review('a', 'APPROVED'), review('a', 'DISMISSED')] },
    { a: 'write' },
  );
  assert.deepEqual(calls, ['#1 -approvals: 1/3']);
});

test('approvals without write access do not count; maintain does', async () => {
  const { calls } = await sync(
    { labels: [], reviews: ['read', 'triage', 'outsider', 'maint'].map(l => review(l, 'APPROVED')) },
    { read: 'read', triage: 'triage', maint: 'maintain' },
  );
  assert.deepEqual(calls, ['#1 +approvals: 1/3']);
});

test('label already correct makes no API changes', async () => {
  const { calls } = await sync({ labels: ['approvals: 1/3'], reviews: [review('a', 'APPROVED')] }, { a: 'write' });
  assert.deepEqual(calls, []);
});

test('closed PRs are skipped', async () => {
  const { calls } = await sync({ state: 'closed', labels: ['approvals: 1/3'], reviews: [] }, {});
  assert.deepEqual(calls, []);
});

test('invalid manual PR number fails the run', async () => {
  const core = fakeCore();
  await runApprovalLabels({ github: fakeGithub(), context: dispatch('abc'), core });
  assert.match(core.failed, /Invalid PR number/);
});

test('same-repo PR is taken from workflow_run.pull_requests', async () => {
  const github = fakeGithub();
  const run = {
    repository: { id: 10 },
    head_repository: { owner: { login: 'o' } },
    head_branch: 'feature',
    pull_requests: [{ number: 7, base: { repo: { id: 10 } } }, { number: 99, base: { repo: { id: 11 } } }],
  };
  assert.deepEqual(await resolvePrNumbers({ github, context: workflowRun(run) }), [7]);
  assert.deepEqual(github.calls, []);
});

test('fork PR is found by head owner and branch', async () => {
  const github = fakeGithub({ forkPrs: [42] });
  const run = { repository: { id: 10 }, head_repository: { owner: { login: 'contrib' } }, head_branch: 'fix', pull_requests: [] };
  assert.deepEqual(await resolvePrNumbers({ github, context: workflowRun(run) }), [42]);
  assert.deepEqual(github.calls, ['list contrib:fix']);
});

test('one failing PR does not stop the others and fails the run', async () => {
  const github = fakeGithub({
    forkPrs: [1, 2],
    prs: {
      1: { failGet: true, labels: [], reviews: [] },
      2: { labels: [], reviews: [review('a', 'APPROVED')] },
    },
    perms: { a: 'write' },
  });
  const core = fakeCore();
  const run = { repository: { id: 10 }, head_repository: { owner: { login: 'contrib' } }, head_branch: 'fix', pull_requests: [] };
  await runApprovalLabels({ github, context: workflowRun(run), core });
  assert.ok(github.calls.includes('#2 +approvals: 1/3'));
  assert.equal(core.errors.length, 1);
  assert.match(core.failed, /#1/);
});

test('Sourcery approval is not counted toward the required approvals', async () => {
  const { calls } = await sync(
    {
      labels: ['approvals: 2/3'],
      reviews: [review('a', 'APPROVED'), review('b', 'APPROVED'), review('sourcery-ai[bot]', 'APPROVED')],
    },
    { a: 'write', b: 'write' },
  );
  assert.deepEqual(calls, []);
});

test('fork PR is resolved from artifact file when available', async () => {
  const tmpDir = mkdtempSync(join(tmpdir(), 'approval-test-'));
  const prFile = join(tmpDir, 'NR');
  try {
    writeFileSync(prFile, '123\n');
    const github = fakeGithub();
    const run = { repository: { id: 10 }, head_repository: { owner: { login: 'fossasia' }, id: 10 }, head_branch: 'fix', pull_requests: [] };
    const prs = await resolvePrNumbers({ github, context: workflowRun(run), prFile });
    assert.deepEqual(prs, [123]);
    assert.deepEqual(github.calls, []);
  } finally {
    rmSync(tmpDir, { recursive: true, force: true });
  }
});

test('fork PR is found when head_repository is base repo by matching head ref or sha', async () => {
  const github = fakeGithub({
    openPrs: [
      { number: 50, head: { ref: 'fix-other', sha: 'sha-other' } },
      { number: 51, head: { ref: 'feature-branch', sha: 'sha-51' } },
    ],
  });
  // In real workflow_run on review events from forks, head_repository is the base repo:
  const run = {
    repository: { id: 10 },
    head_repository: { owner: { login: 'fossasia' }, id: 10 },
    head_branch: 'feature-branch',
    head_sha: 'sha-51',
    pull_requests: [],
  };
  const prs = await resolvePrNumbers({ github, context: workflowRun(run), prFile: '/tmp/nonexistent-pr-file' });
  assert.deepEqual(prs, [51]);
  assert.deepEqual(github.calls, ['list open']);
});
