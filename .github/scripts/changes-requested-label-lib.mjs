// Keeps the "changes requested" label in sync with review state.
// Used by .github/workflows/changes-requested-label.yml; tested by
// changes-requested-label-lib.test.mjs (run with `node --test .github/scripts/*.test.mjs`).

export const LABEL_NAME = 'changes requested';
export const LABEL_COLOR = 'D06834';
export const LABEL_DESCRIPTION = 'Changes requested by reviewer';

// Retry helper with exponential backoff for transient API failures.
export async function withRetry(fn, { retries = 3, baseDelay = 500 } = {}) {
  let attempt = 0;
  while (true) {
    try {
      return await fn();
    } catch (error) {
      attempt++;
      const status = error.status || error.response?.status;
      const isTransient =
        status === 429 ||
        (status >= 500 && status <= 504) ||
        error.code === 'ECONNRESET' ||
        error.code === 'ETIMEDOUT';
      if (attempt >= retries || !isTransient) {
        throw error;
      }
      const delay = baseDelay * Math.pow(2, attempt - 1);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}

// Ensures the label exists in the repository before attempting to add it.
export async function ensureLabelExists(github, owner, repo, name = LABEL_NAME, color = LABEL_COLOR, description = LABEL_DESCRIPTION) {
  try {
    await github.rest.issues.getLabel({ owner, repo, name });
  } catch (error) {
    if (error.status === 404) {
      try {
        await github.rest.issues.createLabel({
          owner,
          repo,
          name,
          color,
          description,
        });
      } catch (createError) {
        if (createError.status !== 422) throw createError;
      }
    } else {
      throw error;
    }
  }
}

// Attempts to extract the exact PR number from the trigger workflow run's job logs.
export async function extractPrNumberFromTriggerLogs(github, owner, repo, runId) {
  try {
    const { data } = await github.rest.actions.listJobsForWorkflowRun({
      owner,
      repo,
      run_id: runId,
    });
    for (const job of (data.jobs || [])) {
      try {
        const logRes = await github.rest.actions.downloadJobLogsForWorkflowRun({
          owner,
          repo,
          job_id: job.id,
        });
        const logText = typeof logRes.data === 'string' ? logRes.data : '';
        const match = logText.match(/Review \w+ on PR #(\d+)/);
        if (match) {
          const prNum = Number(match[1]);
          if (Number.isInteger(prNum) && prNum > 0) {
            return prNum;
          }
        }
      } catch {
        // Ignore single job log download failure
      }
    }
  } catch {
    // Ignore actions API listing failures
  }
  return null;
}

// Returns the PR numbers to sync for this run, or null when the input is invalid.
export async function resolvePrNumbers({ github, context }) {
  const { owner, repo } = context.repo;
  if (context.eventName === 'workflow_dispatch') {
    const n = Number(context.payload.inputs?.['pr-number']);
    return Number.isInteger(n) && n > 0 ? [n] : null;
  }

  const run = context.payload.workflow_run;
  if (!run) return [];

  // 1. Try to extract the exact reviewed PR number from the trigger run's job logs.
  if (run.id && github.rest.actions?.listJobsForWorkflowRun) {
    const prFromLogs = await extractPrNumberFromTriggerLogs(github, owner, repo, run.id);
    if (prFromLogs) {
      return [prFromLogs];
    }
  }

  // 2. Check same-repo PRs associated with the run.
  const sameRepo = (run.pull_requests ?? [])
    .filter(p => p.base.repo.id === run.repository.id)
    .map(p => p.number);
  if (sameRepo.length > 0) return sameRepo;

  // 3. Fallback for fork PRs: constrain lookup by head AND base repository default branch.
  if (run.head_repository) {
    const baseBranch = run.repository?.default_branch || 'dev';
    const prs = await github.paginate(github.rest.pulls.list, {
      owner, repo, state: 'open',
      head: `${run.head_repository.owner.login}:${run.head_branch}`,
      base: baseBranch,
      per_page: 100,
    });
    if (prs.length > 0) {
      return prs.map(p => p.number);
    }
  }

  return [];
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

// Synchronizes the "changes requested" label on a single pull request.
export async function syncSinglePr({ github, context, core, prNumber }) {
  const { owner, repo } = context.repo;

  const { data: pr } = await withRetry(() =>
    github.rest.pulls.get({ owner, repo, pull_number: prNumber })
  );
  if (pr.state !== 'open') {
    core.info(`#${prNumber} is ${pr.state}, skipping`);
    return;
  }

  const reviews = await withRetry(() =>
    github.paginate(github.rest.pulls.listReviews, {
      owner, repo, pull_number: prNumber, per_page: 100,
    })
  );

  const needsLabel = hasChangesRequested(reviews, pr.user.login);
  const currentLabels = (pr.labels || []).map(l => l.name);
  const hasLabel = currentLabels.includes(LABEL_NAME);

  if (needsLabel && !hasLabel) {
    await ensureLabelExists(github, owner, repo);
    await withRetry(() =>
      github.rest.issues.addLabels({ owner, repo, issue_number: prNumber, labels: [LABEL_NAME] })
    );
    core.info(`#${prNumber}: added "${LABEL_NAME}"`);
  } else if (!needsLabel && hasLabel) {
    try {
      await withRetry(() =>
        github.rest.issues.removeLabel({ owner, repo, issue_number: prNumber, name: LABEL_NAME })
      );
      core.info(`#${prNumber}: removed "${LABEL_NAME}"`);
    } catch (error) {
      if (error.status !== 404) throw error; // already gone
    }
  } else {
    core.info(`#${prNumber}: label already ${needsLabel ? 'present' : 'absent'}, no change`);
  }
}

export async function runChangesRequestedLabel({ github, context, core }) {
  const prNumbers = await resolvePrNumbers({ github, context });
  if (prNumbers === null) {
    core.setFailed(`Invalid PR number: ${context.payload.inputs?.['pr-number']}`);
    return;
  }
  if (prNumbers.length === 0) {
    core.info('No open pull request found for this run, nothing to do');
    return;
  }

  const failed = [];
  for (const n of prNumbers) {
    try {
      await syncSinglePr({ github, context, core, prNumber: n });
    } catch (error) {
      core.error(`#${n}: ${error.message}`);
      failed.push(n);
    }
  }
  if (failed.length) {
    core.setFailed(`Could not sync changes-requested label for: ${failed.map(n => `#${n}`).join(', ')}`);
  }
}
