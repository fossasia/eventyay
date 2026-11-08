// Keeps the "changes requested" label in sync with review state.
// Used by .github/workflows/changes-requested-label.yml; tested by
// changes-requested-label-lib.test.mjs (run with `node --test .github/scripts/*.test.mjs`).

const LABEL_NAME = 'changes requested';

// Returns the PR numbers to sync for this run, or null when the input is invalid.
// This is the same resolution logic as approval-labels-lib.mjs.
export async function resolvePrNumbers({ github, context }) {
  const { owner, repo } = context.repo;
  if (context.eventName === 'workflow_dispatch') {
    const n = Number(context.payload.inputs['pr-number']);
    return Number.isInteger(n) && n > 0 ? [n] : null;
  }
  const run = context.payload.workflow_run;
  const sameRepo = (run.pull_requests ?? [])
    .filter(p => p.base.repo.id === run.repository.id)
    .map(p => p.number);
  if (sameRepo.length > 0 || !run.head_repository) return sameRepo;
  const prs = await github.paginate(github.rest.pulls.list, {
    owner, repo, state: 'open',
    head: `${run.head_repository.owner.login}:${run.head_branch}`,
    per_page: 100,
  });
  return prs.map(p => p.number);
}

// Returns true if any reviewer's latest decisive review is CHANGES_REQUESTED.
// A later COMMENTED review does not cancel a changes_requested; only APPROVED or
// DISMISSED cancels it. The PR author's self-reviews are ignored.
export function hasChangesRequested(reviews, author) {
  const latest = new Map();
  for (const r of reviews) {
    if (!r.user || r.user.login === author) continue;
    const state = r.state;
    if (['APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'].includes(state)) {
      latest.set(r.user.login, state);
    }
  }
  return [...latest.values()].some(state => state === 'CHANGES_REQUESTED');
}

export async function runChangesRequestedLabel({ github, context, core }) {
  const { owner, repo } = context.repo;

  const prNumbers = await resolvePrNumbers({ github, context });
  if (prNumbers === null) {
    core.setFailed(`Invalid PR number: ${context.payload.inputs['pr-number']}`);
    return;
  }
  if (prNumbers.length === 0) {
    core.info('No open pull request found for this run, nothing to do');
    return;
  }

  const syncPr = async n => {
    const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number: n });
    if (pr.state !== 'open') {
      core.info(`#${n} is ${pr.state}, skipping`);
      return;
    }

    const reviews = await github.paginate(github.rest.pulls.listReviews, {
      owner, repo, pull_number: n, per_page: 100,
    });

    const needsLabel = hasChangesRequested(reviews, pr.user.login);
    const currentLabels = pr.labels.map(l => l.name);
    const hasLabel = currentLabels.includes(LABEL_NAME);

    if (needsLabel && !hasLabel) {
      await github.rest.issues.addLabels({ owner, repo, issue_number: n, labels: [LABEL_NAME] });
      core.info(`#${n}: added "${LABEL_NAME}"`);
    } else if (!needsLabel && hasLabel) {
      try {
        await github.rest.issues.removeLabel({ owner, repo, issue_number: n, name: LABEL_NAME });
        core.info(`#${n}: removed "${LABEL_NAME}"`);
      } catch (error) {
        if (error.status !== 404) throw error; // already gone
      }
    } else {
      core.info(`#${n}: label already ${needsLabel ? 'present' : 'absent'}, no change`);
    }
  };

  const failed = [];
  for (const n of prNumbers) {
    try {
      await syncPr(n);
    } catch (error) {
      core.error(`#${n}: ${error.message}`);
      failed.push(n);
    }
  }
  if (failed.length) {
    core.setFailed(`Could not sync changes-requested label for: ${failed.map(n => `#${n}`).join(', ')}`);
  }
}
