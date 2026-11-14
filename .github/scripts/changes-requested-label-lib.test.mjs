import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  LABEL_NAME,
  hasChangesRequested,
  ensureLabelExists,
  withRetry,
  extractPrNumberFromTriggerLogs,
  resolvePrNumbers,
  syncSinglePr,
  runChangesRequestedLabel,
} from './changes-requested-label-lib.mjs';

const review = (login, state) => ({ user: { login }, state });

function fakeGithub({ prs = {}, forkPrs = [], jobs = [], logs = '' } = {}) {
  const calls = [];
  const listReviews = async () => {};
  const list = async () => {};
  const github = {
    calls,
    paginate: async (fn, params) => {
      if (fn === listReviews) return prs[params.pull_number]?.reviews || [];
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
          if (!pr) throw Object.assign(new Error('Not found'), { status: 404 });
          if (pr.failGet) throw Object.assign(new Error('boom'), { status: 500 });
          return {
            data: {
              state: pr.state ?? 'open',
              user: { login: pr.author ?? 'author' },
              labels: (pr.labels || []).map(name => ({ name })),
            },
          };
        },
      },
      issues: {
        getLabel: async ({ name }) => {
          calls.push(`getLabel ${name}`);
          return { data: { name } };
        },
        createLabel: async ({ name, color }) => {
          calls.push(`createLabel ${name} #${color}`);
          return { data: { name } };
        },
        addLabels: async ({ issue_number, labels }) => calls.push(`#${issue_number} +${labels[0]}`),
        removeLabel: async ({ issue_number, name }) => calls.push(`#${issue_number} -${name}`),
      },
      actions: {
        listJobsForWorkflowRun: async () => ({
          data: { jobs },
        }),
        downloadJobLogsForWorkflowRun: async () => ({
          data: logs,
        }),
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

test('ensureLabelExists creates label if 404', async () => {
  const calls = [];
  const github = {
    rest: {
      issues: {
        getLabel: async () => {
          throw Object.assign(new Error('Not found'), { status: 404 });
        },
        createLabel: async ({ name, color }) => {
          calls.push(`created ${name} ${color}`);
        },
      },
    },
  };
  await ensureLabelExists(github, 'o', 'r', LABEL_NAME, 'D06834');
  assert.deepEqual(calls, ['created changes requested D06834']);
});

test('withRetry succeeds on retry after transient failure', async () => {
  let attempts = 0;
  const result = await withRetry(async () => {
    attempts++;
    if (attempts === 1) {
      throw Object.assign(new Error('Server Error'), { status: 500 });
    }
    return 'ok';
  }, { retries: 2, baseDelay: 1 });
  assert.equal(result, 'ok');
  assert.equal(attempts, 2);
});

test('extractPrNumberFromTriggerLogs extracts PR number from trigger logs', async () => {
  const github = fakeGithub({
    jobs: [{ id: 123 }],
    logs: '2026-11-08T14:11:20Z Review submitted on PR #7135\n',
  });
  const prNum = await extractPrNumberFromTriggerLogs(github, 'o', 'r', 999);
  assert.equal(prNum, 7135);
});

test('resolvePrNumbers extracts PR number from trigger logs for fork runs', async () => {
  const github = fakeGithub({
    jobs: [{ id: 123 }],
    logs: 'Review submitted on PR #7135\n',
  });
  const run = { id: 999, repository: { id: 10 }, head_repository: { owner: { login: 'contrib' } }, head_branch: 'fix', pull_requests: [] };
  const prNumbers = await resolvePrNumbers({ github, context: workflowRun(run) });
  assert.deepEqual(prNumbers, [7135]);
});

test('resolvePrNumbers falls back to head and default branch query when no logs match', async () => {
  const github = fakeGithub({ forkPrs: [42] });
  const run = { id: 999, repository: { id: 10, default_branch: 'dev' }, head_repository: { owner: { login: 'contrib' } }, head_branch: 'fix', pull_requests: [] };
  const prNumbers = await resolvePrNumbers({ github, context: workflowRun(run) });
  assert.deepEqual(prNumbers, [42]);
  assert.deepEqual(github.calls, ['list contrib:fix']);
});

test('syncSinglePr adds label when changes requested', async () => {
  const github = fakeGithub({
    prs: { 1: { labels: [], reviews: [review('a', 'CHANGES_REQUESTED')] } },
  });
  const core = fakeCore();
  await syncSinglePr({ github, context: dispatch(1), core, prNumber: 1 });
  assert.ok(github.calls.includes('#1 +changes requested'));
});

test('syncSinglePr removes label when reviews approved', async () => {
  const github = fakeGithub({
    prs: {
      1: {
        labels: ['changes requested'],
        reviews: [review('a', 'CHANGES_REQUESTED'), review('a', 'APPROVED')],
      },
    },
  });
  const core = fakeCore();
  await syncSinglePr({ github, context: dispatch(1), core, prNumber: 1 });
  assert.ok(github.calls.includes('#1 -changes requested'));
});

test('syncSinglePr makes no change when label already correct', async () => {
  const github = fakeGithub({
    prs: {
      1: {
        labels: ['changes requested'],
        reviews: [review('a', 'CHANGES_REQUESTED')],
      },
    },
  });
  const core = fakeCore();
  await syncSinglePr({ github, context: dispatch(1), core, prNumber: 1 });
  assert.equal(github.calls.some(c => c.startsWith('#1 +') || c.startsWith('#1 -')), false);
});

test('syncSinglePr skips closed PRs', async () => {
  const github = fakeGithub({
    prs: {
      1: { state: 'closed', labels: ['changes requested'], reviews: [] },
    },
  });
  const core = fakeCore();
  await syncSinglePr({ github, context: dispatch(1), core, prNumber: 1 });
  assert.equal(github.calls.some(c => c.startsWith('#1 +') || c.startsWith('#1 -')), false);
});

test('invalid manual PR number fails the run', async () => {
  const core = fakeCore();
  await runChangesRequestedLabel({ github: fakeGithub(), context: dispatch('abc'), core });
  assert.match(core.failed, /Invalid PR number/);
});
