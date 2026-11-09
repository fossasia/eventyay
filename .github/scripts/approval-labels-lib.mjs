// Keeps the "approvals: k/N" labels in sync with approvals from reviewers who have
// write access. Used by .github/workflows/approval-labels.yml; tested by
// approval-labels-lib.test.mjs (run with `node --test .github/scripts/*.test.mjs`).

const WRITE_ROLES = ['admin', 'maintain', 'write'];
const DECISIVE_STATES = ['APPROVED', 'CHANGES_REQUESTED', 'DISMISSED'];

const escapeRegExp = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Returns the PR numbers to sync for this run, or null when the input is invalid.
export async function resolvePrNumbers({ github, context }) {
  const { owner, repo } = context.repo;
  if (context.eventName === 'workflow_dispatch') {
    const n = Number(context.payload.inputs['pr-number']);
    return Number.isInteger(n) && n > 0 ? [n] : null;
  }
  const run = context.payload.workflow_run;
  // Filled for same-repo PRs; empty for forks.
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

// Logins whose latest decisive review is APPROVED (reviews come oldest first).
// A later COMMENTED review does not cancel an approval; the author is ignored.
export function latestApprovers(reviews, author) {
  const latest = new Map();
  for (const r of reviews) {
    if (!r.user || r.user.login === author) continue;
    if (DECISIVE_STATES.includes(r.state)) latest.set(r.user.login, r.state);
  }
  return [...latest].filter(([, state]) => state === 'APPROVED').map(([login]) => login);
}

// The single managed label a PR should carry, or null for none.
export function wantedLabel(count, required, prefix) {
  return count > 0 && count < required ? `${prefix}${count}/${required}` : null;
}

export async function runApprovalLabels({ github, context, core, required = 3, prefix = 'approvals: ' }) {
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

  // Permission lookups are cached across PRs in this run.
  const permCache = new Map();
  const hasWriteAccess = async username => {
    if (!permCache.has(username)) {
      try {
        const { data } = await github.rest.repos.getCollaboratorPermissionLevel({ owner, repo, username });
        // role_name distinguishes "maintain"; the legacy `permission` field reports it as "write".
        permCache.set(username, WRITE_ROLES.includes(data.role_name) || WRITE_ROLES.includes(data.permission));
      } catch (error) {
        if (error.status !== 404) throw error;
        permCache.set(username, false); // not a collaborator
      }
    }
    return permCache.get(username);
  };

  const managed = new RegExp(`^${escapeRegExp(prefix)}\\d+/${required}$`);

  const syncPr = async n => {
    const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number: n });
    if (pr.state !== 'open') {
      core.info(`#${n} is ${pr.state}, skipping`);
      return;
    }

    const reviews = await github.paginate(github.rest.pulls.listReviews, {
      owner, repo, pull_number: n, per_page: 100,
    });
    const approvers = [];
    for (const login of latestApprovers(reviews, pr.user.login)) {
      if (await hasWriteAccess(login)) approvers.push(login);
    }
    core.info(`#${n}: ${approvers.length} qualifying approval(s) [${approvers.join(', ')}]`);

    const wanted = wantedLabel(approvers.length, required, prefix);
    const current = pr.labels.map(l => l.name);

    // Add the new label first so a failure never leaves the PR with none.
    if (wanted && !current.includes(wanted)) {
      await github.rest.issues.addLabels({ owner, repo, issue_number: n, labels: [wanted] });
      core.info(`#${n}: added "${wanted}"`);
    }
    for (const name of current) {
      if (managed.test(name) && name !== wanted) {
        try {
          await github.rest.issues.removeLabel({ owner, repo, issue_number: n, name });
          core.info(`#${n}: removed "${name}"`);
        } catch (error) {
          if (error.status !== 404) throw error; // already gone
        }
      }
    }
  };

  // One failing PR must not stop the others from being synced.
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
    core.setFailed(`Could not sync approval labels for: ${failed.map(n => `#${n}`).join(', ')}`);
  }
}
