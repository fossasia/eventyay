import { test } from 'node:test';
import assert from 'node:assert/strict';

import { hasChangesRequested, resolvePrNumbers, runChangesRequestedLabel } from './changes-requested-label-lib.mjs';

const review = (login, state) => ({ user: { login }, state });

function fakeGithub({ prs = {}, forkPrs = [] } = {}) {
  const calls = [];
  const listReviews = async () => {};
  const list = async () => {};
  const github = {
    calls,
    paginate: async (fn, params) => {
      if (fn === listReviews) return prs[params.pull_number].reviews;
      if (fn === list) {
        calls.push(`list ${params.head}`);
        return forkPrs.map(number => ({ number }));
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

async function sync(pr) {
  const github = fakeGithub({ prs: { 1: pr } });
  const core = fakeCore();
  await runChangesRequestedLabel({ github, context: dispatch(1), core });
  return { calls: github.calls, core };
}

test('hasChangesRequested detects changes_requested from any reviewer', () => {
  const reviews = [review('a', 'APPROVED'), review('b', 'CHANGES_REQUESTED')];
  assert.equal(hasChangesRequested(reviews, 'author'), true);
});

test('hasChangesRequested returns false when reviewer re-approves', () => {
  const reviews = [review('a', 'CHANGES_REQUESTED'), review('a', 'APPROVED')];
  assert.equal(hasChangesRequested(reviews, 'author'), false);
});

test('hasChangesRequested returns false when review is dismissed', () => {
  const reviews = [review('a', 'CHANGES_REQUESTED'), review('a', 'DISMISSED')];
  assert.equal(hasChangesRequested(reviews, 'author'), false);
});

test('hasChangesRequested ignores author self-review', () => {
  const reviews = [review('author', 'CHANGES_REQUESTED')];
  assert.equal(hasChangesRequested(reviews, 'author'), false);
});

test('hasChangesRequested ignores deleted users', () => {
  const reviews = [{ user: null, state: 'CHANGES_REQUESTED' }];
  assert.equal(hasChangesRequested(reviews, 'author'), false);
});

test('hasChangesRequested: comment does not cancel changes_requested', () => {
  const reviews = [review('a', 'CHANGES_REQUESTED'), review('a', 'COMMENTED')];
  assert.equal(hasChangesRequested(reviews, 'author'), true);
});

test('hasChangesRequested returns false when no reviews', () => {
  assert.equal(hasChangesRequested([], 'author'), false);
});

test('adds label when changes requested', async () => {
  const { calls } = await sync({ labels: [], reviews: [review('a', 'CHANGES_REQUESTED')] });
  assert.deepEqual(calls, ['#1 +changes requested']);
});

test('removes label when all reviews approved', async () => {
  const { calls } = await sync({
    labels: ['changes requested'],
    reviews: [review('a', 'CHANGES_REQUESTED'), review('a', 'APPROVED')],
  });
  assert.deepEqual(calls, ['#1 -changes requested']);
});

test('no change when label already present and still needed', async () => {
  const { calls } = await sync({ labels: ['changes requested'], reviews: [review('a', 'CHANGES_REQUESTED')] });
  assert.deepEqual(calls, []);
});

test('no change when label absent and not needed', async () => {
  const { calls } = await sync({ labels: [], reviews: [review('a', 'APPROVED')] });
  assert.deepEqual(calls, []);
});

test('closed PRs are skipped', async () => {
  const { calls } = await sync({ state: 'closed', labels: ['changes requested'], reviews: [] });
  assert.deepEqual(calls, []);
});

test('invalid manual PR number fails the run', async () => {
  const core = fakeCore();
  await runChangesRequestedLabel({ github: fakeGithub(), context: dispatch('abc'), core });
  assert.match(core.failed, /Invalid PR number/);
});

test('same-repo PR from workflow_run', async () => {
  const github = fakeGithub();
  const run = {
    repository: { id: 10 },
    head_repository: { owner: { login: 'o' } },
    head_branch: 'feature',
    pull_requests: [{ number: 7, base: { repo: { id: 10 } } }],
  };
  assert.deepEqual(await resolvePrNumbers({ github, context: workflowRun(run) }), [7]);
});

test('fork PR is found by head owner and branch', async () => {
  const github = fakeGithub({ forkPrs: [42] });
  const run = { repository: { id: 10 }, head_repository: { owner: { login: 'contrib' } }, head_branch: 'fix', pull_requests: [] };
  assert.deepEqual(await resolvePrNumbers({ github, context: workflowRun(run) }), [42]);
});

test('one failing PR does not stop others', async () => {
  const github = fakeGithub({
    forkPrs: [1, 2],
    prs: {
      1: { failGet: true, labels: [], reviews: [] },
      2: { labels: [], reviews: [review('a', 'CHANGES_REQUESTED')] },
    },
  });
  const core = fakeCore();
  const run = { repository: { id: 10 }, head_repository: { owner: { login: 'contrib' } }, head_branch: 'fix', pull_requests: [] };
  await runChangesRequestedLabel({ github, context: workflowRun(run), core });
  assert.ok(github.calls.includes('#2 +changes requested'));
  assert.equal(core.errors.length, 1);
  assert.match(core.failed, /#1/);
});
