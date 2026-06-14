/**
 * Shared PR process reminder logic for GitHub Actions and local tests.
 */

const MARKER = '<!-- pr-process-reminder -->';
const REMINDER_MARKER_PATTERN = /<!-- (?:[\w-]+-)?pr-process-reminder -->/;
const MERGE_PERMISSIONS = new Set(['admin', 'maintain', 'write']);
const AI_REVIEWER_PATTERN = /copilot|codex|openai|claude|cursor|bugbot|devin|chatgpt/i;
const EXCLUDED_AI_PATTERN = /sourcery/i;
const AI_FAILURE_PATTERN =
  /usage limits?|rate limit|reached your (?:weekly )?limit|try again later|upgrade to continue|quota exceeded|cannot (?:complete|perform|provide) (?:this )?review|unable to review|could not review|service unavailable|temporarily unavailable|billing.*limit|limit.*(?:reached|exceeded)/i;

function hasReminderMarker(body) {
  return REMINDER_MARKER_PATTERN.test(body || '');
}

function isAiReviewFailure(body) {
  if (!body?.trim()) return false;
  return AI_FAILURE_PATTERN.test(body);
}

function extractFailureReason(body) {
  const lines = body.trim().replace(/\r\n/g, '\n').split('\n').map((line) => line.trim()).filter(Boolean);
  const keyLine = lines.find((line) => isAiReviewFailure(line)) || lines[0] || body.trim();
  const cleaned = keyLine.replace(/^sorry[^,]*,\s*/i, '').trim();
  return cleaned.length > 240 ? `${cleaned.slice(0, 237)}…` : cleaned;
}

function isTrackableAiBot(login) {
  return isAiReviewer(login) || isExcludedReviewer(login);
}

const CHECKLIST = {
  visual: { label: 'Show what changed', detail: 'a screenshot or short screen recording of the updated functionality' },
  structure: {
    label: 'Map structural updates',
    detail:
      'for architectural work, new directories, or file reorganization, include a diagram in the PR description (component, flow, or directory tree). Optional — only when your PR includes those kinds of changes',
  },
  aiReview: {
    label: 'Request AI feedback',
    detail: 'request or receive review from GitHub Copilot, Codex, or other automated reviewers you use',
  },
};

function checkbox(checked, key) {
  const item = CHECKLIST[key];
  return `- [${checked ? 'x' : ' '}] **${item.label}** — ${item.detail}`;
}

function parseCheckboxStates(commentBody) {
  const states = { visual: false, structure: false, aiReview: false };
  if (!commentBody) return states;
  for (const line of commentBody.split('\n')) {
    const isChecked = /^-\s*\[x\]/i.test(line);
    if (/Show what changed/i.test(line)) states.visual = isChecked;
    if (/Map structural updates/i.test(line)) states.structure = isChecked;
    if (/Request AI feedback/i.test(line)) states.aiReview = isChecked;
  }
  return states;
}

function isVideoUrl(url) {
  return /\.(mp4|webm|mov)(\?|$)/i.test(url);
}

function isGithubBareAttachmentUrl(url) {
  return /github\.com\/user-attachments\/assets\/[a-f0-9-]+(?:\?|#|$|\s|>)/i.test(url);
}

function inferMediaType(url, source = 'unknown', alt = '') {
  if (source === 'img') return 'image';
  if (source === 'video') return 'video';
  if (isVideoUrl(url)) return 'video';
  if (/\.(png|jpe?g|gif|webp)(\?|$)/i.test(url)) return 'image';

  const altLower = alt.toLowerCase();
  if (/screen\s*record|screenshare|screen\s*share|\bvideo\b|\bclip\b/.test(altLower)) return 'video';
  if (/screenshot|screen\s*shot/.test(altLower)) return 'image';

  if (source === 'bare' && isGithubBareAttachmentUrl(url)) return 'video';

  return 'image';
}

function defaultMediaAlt(type, alt = '') {
  if (alt) return alt;
  return type === 'video' ? 'Screen recording' : 'Screenshot';
}

function normalizeMediaKey(url) {
  const withoutFragment = url.split('#')[0];
  const withoutQuery = withoutFragment.split('?')[0];
  const assetId = withoutQuery.match(/user-attachments\/assets\/([a-f0-9-]+)/i)?.[1];
  if (assetId) return `github-asset:${assetId}`;
  return withoutQuery;
}

function isMediaUrl(url) {
  return (
    /user-attachments\/assets\//i.test(url) ||
    /user-images\.githubusercontent\.com\//i.test(url) ||
    /\.(png|jpe?g|gif|webp|mp4|webm|mov)(\?|$)/i.test(url)
  );
}

function addUniqueMedia(items, seen, entry) {
  const key = normalizeMediaKey(entry.url);
  if (seen.has(key)) return;
  seen.add(key);
  items.push(entry);
}

function extractVisualMediaFromDescription(description) {
  if (!description) return [];
  const items = [];
  const seen = new Set();

  for (const match of description.matchAll(/!\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
    const url = match[2];
    if (!isMediaUrl(url)) continue;
    const alt = match[1]?.trim() || '';
    const type = inferMediaType(url, 'markdown', alt);
    addUniqueMedia(items, seen, { type, alt: defaultMediaAlt(type, alt), url });
  }

  for (const match of description.matchAll(/(?<!!)\[([^\]]*)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
    const url = match[2];
    if (!isMediaUrl(url)) continue;
    const alt = match[1]?.trim() || '';
    const type = inferMediaType(url, 'markdown', alt);
    addUniqueMedia(items, seen, { type, alt: defaultMediaAlt(type, alt), url });
  }

  for (const match of description.matchAll(/<img\b[^>]*>/gi)) {
    const tag = match[0];
    const url = tag.match(/\bsrc=["']([^"']+)["']/i)?.[1];
    if (!url || !isMediaUrl(url)) continue;
    const alt = tag.match(/\balt=["']([^"']*)["']/i)?.[1]?.trim() || '';
    const type = inferMediaType(url, 'img', alt);
    addUniqueMedia(items, seen, { type, alt: defaultMediaAlt(type, alt), url });
  }

  for (const match of description.matchAll(/<video\b[^>]*>/gi)) {
    const tag = match[0];
    const url = tag.match(/\bsrc=["']([^"']+)["']/i)?.[1];
    if (!url || !isMediaUrl(url)) continue;
    addUniqueMedia(items, seen, { type: 'video', alt: defaultMediaAlt('video'), url });
  }

  const strippedDescription = description
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    .replace(/\[[^\]]*\]\([^)]+\)/g, '')
    .replace(/<(?:img|video)\b[^>]*>/gi, '');

  for (const match of strippedDescription.matchAll(
    /https?:\/\/(?:github\.com\/user-attachments\/assets\/[^\s)>]+|user-images\.githubusercontent\.com\/[^\s)>]+)/gi,
  )) {
    const url = match[0];
    const type = inferMediaType(url, 'bare');
    addUniqueMedia(items, seen, { type, alt: defaultMediaAlt(type), url });
  }

  for (const match of strippedDescription.matchAll(
    /https?:\/\/[^\s)>]+\.(?:mp4|webm|mov|gif|webp|png|jpe?g)(?:\?[^\s)>]*)?/gi,
  )) {
    const url = match[0];
    const type = inferMediaType(url, 'bare');
    addUniqueMedia(items, seen, { type, alt: defaultMediaAlt(type), url });
  }

  return items;
}

function hasVisualMediaInDescription(description) {
  return extractVisualMediaFromDescription(description).length > 0;
}

function formatIndentedEntry(text) {
  return `> ${text}`;
}

function formatCompletedAgentsSection(completedAgents) {
  const lines = [`**✅ Completed (${completedAgents.length})**`, ''];
  for (const agent of completedAgents) {
    lines.push(formatIndentedEntry(`**${agent.label}** (\`@${agent.login}\`) — ${agent.kind}`), '');
  }
  return lines.join('\n').trimEnd();
}

function formatExcludedAgentsSection(excludedAgents) {
  const lines = ['**ℹ️ Does not count toward the checklist**', ''];
  for (const agent of excludedAgents) {
    lines.push(formatIndentedEntry(`**${agent.label}** (\`@${agent.login}\`) — ${agent.kind}`), '');
  }
  return lines.join('\n').trimEnd();
}

function mediaLabelForType(item, indexAmongType, type) {
  const alt = item.alt?.trim();
  if (alt && !/^screenshot$/i.test(alt) && !/^screen recording$/i.test(alt)) return alt;
  return type === 'video' ? `Screen recording ${indexAmongType + 1}` : `Screenshot ${indexAmongType + 1}`;
}

function getUnresolvedIcon(labelStem) {
  if (labelStem === 'AI review') return '🤖';
  if (labelStem === 'maintainer review') return '🛡️';
  return '👤';
}

function formatVisualMediaCollapsible(mediaItems) {
  if (!mediaItems.length) return '';
  const images = mediaItems.filter((item) => item.type !== 'video');
  const videos = mediaItems.filter((item) => item.type === 'video');
  const count = mediaItems.length;
  const lines = [
    `### 📎 Attached media (${count})`,
    '',
    '<details>',
    '<summary>Screenshots and screen recordings</summary>',
    '',
    '>',
    '',
  ];

  if (images.length) {
    lines.push('> **🖼️ Screenshots**', '>');
    images.forEach((item, index) => {
      const label = mediaLabelForType(item, index, 'image');
      lines.push(`> ![${label}](${item.url})`, '>');
    });
    lines.push('');
  }

  if (videos.length) {
    lines.push('> **🎬 Screen recordings**', '>');
    videos.forEach((item, index) => {
      const label = mediaLabelForType(item, index, 'video');
      lines.push(`> [${label}](${item.url})`, '>');
    });
    lines.push('');
  }

  lines.push('</details>');
  return lines.join('\n');
}

function isExcludedReviewer(name) {
  return Boolean(name && EXCLUDED_AI_PATTERN.test(name));
}

function isAiReviewer(name) {
  if (!name || isExcludedReviewer(name)) return false;
  return AI_REVIEWER_PATTERN.test(name);
}

function normalizeAgentDisplayName(login) {
  const name = login.toLowerCase();
  if (/copilot/.test(name)) return 'GitHub Copilot';
  if (/codex|chatgpt/.test(name)) return 'Codex';
  if (/claude/.test(name)) return 'Claude';
  if (/cursor/.test(name)) return 'Cursor';
  if (/bugbot/.test(name)) return 'Bugbot';
  if (/devin/.test(name)) return 'Devin';
  if (/openai/.test(name)) return 'OpenAI';
  return login.replace(/\[bot\]$/i, '');
}

function getAgentKind(login) {
  const name = login.toLowerCase();
  if (/copilot/.test(name)) return 'GitHub Copilot PR reviewer';
  if (/codex|chatgpt/.test(name)) return 'OpenAI Codex connector';
  if (/claude/.test(name)) return 'Anthropic Claude reviewer';
  if (/cursor/.test(name)) return 'Cursor AI reviewer';
  if (/bugbot/.test(name)) return 'Cursor Bugbot reviewer';
  if (/devin/.test(name)) return 'Devin AI software engineer';
  if (/openai/.test(name)) return 'OpenAI reviewer';
  return 'Automated AI reviewer';
}

function addCompletedAgent(agentsByLabel, login) {
  const label = normalizeAgentDisplayName(login);
  const entry = { label, login, kind: getAgentKind(login) };
  const existing = agentsByLabel.get(label);
  if (!existing || login.includes('[bot]')) {
    agentsByLabel.set(label, entry);
  }
}

function collectAiReviewActivity({ reviewRequests, reviews, reviewComments, issueComments = [] }) {
  const completedAgents = new Map();
  const failedAgents = new Map();
  const excludedAgents = new Map();
  const messagesByLogin = new Map();

  function addMessage(login, body) {
    if (!isTrackableAiBot(login) || !body?.trim()) return;
    if (!messagesByLogin.has(login)) messagesByLogin.set(login, []);
    messagesByLogin.get(login).push(body);
  }

  function recordFailure(login, body) {
    const label = isExcludedReviewer(login) ? 'Sourcery AI' : normalizeAgentDisplayName(login);
    const reason = extractFailureReason(body);
    const existing = failedAgents.get(label);
    if (!existing || reason.length > existing.reason.length) {
      failedAgents.set(label, {
        label,
        login,
        kind: isExcludedReviewer(login) ? 'Sourcery AI code review bot' : getAgentKind(login),
        reason,
      });
    }
  }

  for (const review of reviews) addMessage(review.user?.login, review.body);
  for (const comment of reviewComments) addMessage(comment.user?.login, comment.body);
  for (const comment of issueComments) addMessage(comment.user?.login, comment.body);

  for (const [login, bodies] of messagesByLogin) {
    for (const body of bodies) {
      if (isAiReviewFailure(body)) recordFailure(login, body);
    }

    const hasSuccessfulContent = bodies.some((body) => body?.trim() && !isAiReviewFailure(body));
    const hasSuccessfulInlineComment = reviewComments.some(
      (comment) => comment.user?.login === login && comment.body?.trim() && !isAiReviewFailure(comment.body),
    );
    const hadSuccessfulReview = hasSuccessfulContent || hasSuccessfulInlineComment;

    if (isExcludedReviewer(login)) {
      if (hadSuccessfulReview) {
        excludedAgents.set('Sourcery AI', {
          label: 'Sourcery AI',
          login,
          kind: 'Sourcery AI code review bot',
        });
      }
      continue;
    }

    if (isAiReviewer(login) && hadSuccessfulReview) {
      addCompletedAgent(completedAgents, login);
    }
  }

  for (const review of reviews) {
    const login = review.user?.login;
    if (!isAiReviewer(login) || isExcludedReviewer(login)) continue;
    if (isAiReviewFailure(review.body)) continue;
    if (review.state && review.state !== 'PENDING' && review.state !== 'DISMISSED') {
      addCompletedAgent(completedAgents, login);
    }
  }

  let hasQualifyingActivity = completedAgents.size > 0;
  for (const user of reviewRequests.users || []) {
    if (isAiReviewer(user.login)) hasQualifyingActivity = true;
  }
  for (const team of reviewRequests.teams || []) {
    if (isAiReviewer(team.slug) || isAiReviewer(team.name)) hasQualifyingActivity = true;
  }

  return {
    completedAgents: [...completedAgents.values()].sort((a, b) => a.label.localeCompare(b.label)),
    failedAgents: [...failedAgents.values()].sort((a, b) => a.label.localeCompare(b.label)),
    excludedAgents: [...excludedAgents.values()],
    hasQualifyingActivity,
  };
}

function formatUnresolvedThreadEntry(comment, authorLabel, requestedChanges = false) {
  const location = comment.path
    ? comment.line
      ? `\`${comment.path}:${comment.line}\``
      : `\`${comment.path}\``
    : null;
  const changesNote = requestedChanges ? ' _(requested changes)_' : '';
  const header = location
    ? `**${authorLabel}**${changesNote} on ${location} — [view comment](${comment.url})`
    : `**${authorLabel}**${changesNote} — [view comment](${comment.url})`;
  const bodyText = (comment.body || 'Review comment').trim().replace(/\r\n/g, '\n');

  return [header, '', ...bodyText.split('\n')].map((line) => `> ${line}`).join('\n');
}

function formatUnresolvedCommentsCollapsible(threads, labelStem) {
  if (!threads.length) return '';
  const count = threads.length;
  const commentWord = count === 1 ? 'comment' : 'comments';
  const icon = getUnresolvedIcon(labelStem);
  const lines = ['<details>', `<summary>${icon} ⚠️ ${count} unresolved ${labelStem} ${commentWord}</summary>`, '', '>', ''];
  threads.forEach((thread, index) => {
    if (index > 0) lines.push('>', '');
    lines.push(formatUnresolvedThreadEntry(thread.comment, thread.label, thread.requestedChanges), '');
  });
  lines.push('</details>');
  return lines.join('\n');
}

function formatFailedAgentsCollapsible(failedAgents) {
  if (!failedAgents.length) return '';
  const count = failedAgents.length;
  const reviewerWord = count === 1 ? 'reviewer' : 'reviewers';
  const lines = ['<details>', `<summary>❌ ${count} failed or rate-limited AI ${reviewerWord}</summary>`, '', '>', ''];
  failedAgents.forEach((agent, index) => {
    if (index > 0) lines.push('>', '');
    lines.push(`> **${agent.label}** (\`@${agent.login}\`)`, '>', `> ${agent.reason}`, '');
  });
  lines.push('</details>');
  return lines.join('\n');
}

function formatHumanReviewerLabel(login, latestReviewByUser) {
  return {
    label: `@${login}`,
    requestedChanges: latestReviewByUser.get(login) === 'CHANGES_REQUESTED',
  };
}

function isHumanReviewer(login) {
  if (!login || login.endsWith('[bot]') || isAiReviewer(login) || isExcludedReviewer(login)) return false;
  return true;
}

async function analyzeReviewThreads(reviewThreads, latestReviewByUser = new Map(), getPermission = async () => 'none') {
  const aiUnresolved = [];
  const maintainerUnresolved = [];
  const reviewerUnresolved = [];

  for (const thread of reviewThreads) {
    const comments = thread.comments?.nodes || [];
    if (!comments.length) continue;

    const primaryComment = comments[0];
    const authorLogin = primaryComment.author?.login;
    if (!authorLogin || thread.isResolved || thread.isOutdated) continue;

    if (isAiReviewer(authorLogin)) {
      if (isAiReviewFailure(primaryComment.body)) continue;
      aiUnresolved.push({
        label: normalizeAgentDisplayName(authorLogin),
        login: authorLogin,
        comment: primaryComment,
      });
      continue;
    }

    if (!isHumanReviewer(authorLogin)) continue;

    const permission = await getPermission(authorLogin);
    if (MERGE_PERMISSIONS.has(permission)) {
      maintainerUnresolved.push({
        label: `@${authorLogin}`,
        login: authorLogin,
        comment: primaryComment,
      });
      continue;
    }

    reviewerUnresolved.push({
      ...formatHumanReviewerLabel(authorLogin, latestReviewByUser),
      login: authorLogin,
      comment: primaryComment,
    });
  }

  return { aiUnresolved, maintainerUnresolved, reviewerUnresolved };
}

function formatAiFeedbackResolutionStatus(hasQualifyingActivity, aiUnresolved) {
  if (!hasQualifyingActivity) return '';
  if (aiUnresolved.length) return formatUnresolvedCommentsCollapsible(aiUnresolved, 'AI review');
  return '✅ All AI review feedback is resolved.';
}

function formatMaintainerReviewSection(maintainerUnresolved) {
  if (!maintainerUnresolved.length) return '';
  return ['### 🛡️ Maintainer reviews', '', formatUnresolvedCommentsCollapsible(maintainerUnresolved, 'maintainer review')].join('\n');
}

function formatReviewerFeedbackSection(reviewerUnresolved) {
  if (!reviewerUnresolved.length) return '';
  return ['### 👤 Reviewer feedback', '', formatUnresolvedCommentsCollapsible(reviewerUnresolved, 'reviewer')].join('\n');
}

function appendFeedbackSection(parts, section) {
  if (!section) return;
  if (parts.length) parts.push('---', '');
  parts.push(section, '');
}

function formatAutoDetectedSection(
  completedAgents,
  failedAgents,
  excludedAgents,
  resolutionStatus,
  visualMedia,
  maintainerSection = '',
  reviewerSection = '',
) {
  const parts = [];
  const hasAiContent =
    completedAgents.length > 0 ||
    failedAgents.length > 0 ||
    excludedAgents.length > 0 ||
    resolutionStatus;

  if (hasAiContent) {
    parts.push('### 🤖 AI reviews', '');

    if (completedAgents.length) {
      parts.push(formatCompletedAgentsSection(completedAgents), '');
    }

    if (failedAgents.length) {
      parts.push(formatFailedAgentsCollapsible(failedAgents), '');
    }

    if (excludedAgents.length) {
      parts.push(formatExcludedAgentsSection(excludedAgents), '');
    }

    if (resolutionStatus) {
      if (resolutionStatus.startsWith('<details>')) {
        parts.push(resolutionStatus, '');
      } else {
        parts.push(`**Feedback status:** ${resolutionStatus}`, '');
      }
    }
  }

  appendFeedbackSection(parts, maintainerSection);
  appendFeedbackSection(parts, reviewerSection);

  if (visualMedia.length) {
    if (parts.length) parts.push('---', '');
    parts.push(formatVisualMediaCollapsible(visualMedia));
  }

  return parts.join('\n').trim();
}

function buildBody(
  states,
  completedAgents = [],
  failedAgents = [],
  excludedAgents = [],
  resolutionStatus = '',
  visualMedia = [],
  maintainerSection = '',
  reviewerSection = '',
) {
  const autoDetected = formatAutoDetectedSection(
    completedAgents,
    failedAgents,
    excludedAgents,
    resolutionStatus,
    visualMedia,
    maintainerSection,
    reviewerSection,
  );
  const sections = [
    MARKER,
    '### Thank you for contributing',
    '',
    'Please complete the checklist. Screenshots in the PR description and completed AI reviews are checked automatically.',
    '',
    checkbox(states.visual, 'visual'),
    checkbox(states.structure, 'structure'),
    checkbox(states.aiReview, 'aiReview'),
  ];

  if (autoDetected) sections.push('', '---', '', autoDetected);
  sections.push('', '---', '', 'Thank you for your contribution feel free to reach out if you have any questions.');
  return sections.join('\n');
}

async function fetchReviewThreads(github, owner, repo, pullNumber) {
  const query = `
    query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
      repository(owner: $owner, name: $repo) {
        pullRequest(number: $pr) {
          reviewThreads(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              isResolved
              isOutdated
              comments(first: 20) {
                nodes {
                  url
                  body
                  path
                  line
                  author {
                    login
                  }
                }
              }
            }
          }
        }
      }
    }
  `;

  const threads = [];
  let cursor = null;
  let hasNextPage = true;

  while (hasNextPage) {
    const result = await github.graphql(query, { owner, repo, pr: pullNumber, cursor });
    const connection = result.repository.pullRequest.reviewThreads;
    threads.push(...connection.nodes);
    hasNextPage = connection.pageInfo.hasNextPage;
    cursor = connection.pageInfo.endCursor;
  }

  return threads;
}

async function createPermissionResolver(github, owner, repo) {
  const cache = new Map();

  return async function getPermission(username) {
    if (cache.has(username)) return cache.get(username);

    try {
      const { data } = await github.rest.repos.getCollaboratorPermissionLevel({ owner, repo, username });
      cache.set(username, data.permission);
      return data.permission;
    } catch (error) {
      if (error.status === 404) {
        cache.set(username, 'none');
        return 'none';
      }
      throw error;
    }
  };
}

async function runPrProcessReminder({ github, context, core }) {
  const { owner, repo } = context.repo;
  const pr = context.payload.pull_request;

  const { data: pullDetails } = await github.rest.pulls.get({
    owner,
    repo,
    pull_number: pr.number,
  });

  if (pullDetails.merged) {
    core.info('Skipping reminder: PR is merged.');
    return;
  }

  const reviews = await github.paginate(github.rest.pulls.listReviews, {
    owner,
    repo,
    pull_number: pr.number,
    per_page: 100,
  });

  const reviewComments = await github.paginate(github.rest.pulls.listReviewComments, {
    owner,
    repo,
    pull_number: pr.number,
    per_page: 100,
  });

  const latestReviewByUser = new Map();
  for (const review of reviews) {
    if (!review.user?.login) continue;
    latestReviewByUser.set(review.user.login, review.state);
  }

  for (const [username, state] of latestReviewByUser) {
    if (state !== 'APPROVED') continue;

    try {
      const { data: permission } = await github.rest.repos.getCollaboratorPermissionLevel({
        owner,
        repo,
        username,
      });

      if (MERGE_PERMISSIONS.has(permission.permission)) {
        core.info(`Skipping reminder: approved by ${username} with merge access.`);
        return;
      }
    } catch (error) {
      if (error.status !== 404) throw error;
    }
  }

  const { data: reviewRequests } = await github.rest.pulls.listRequestedReviewers({
    owner,
    repo,
    pull_number: pr.number,
  });

  const { data: comments } = await github.rest.issues.listComments({
    owner,
    repo,
    issue_number: pr.number,
    per_page: 100,
  });

  const reminderComments = comments.filter((comment) => hasReminderMarker(comment.body));
  const [existingComment, ...duplicateComments] = reminderComments;

  await Promise.all(
    duplicateComments.map((comment) =>
      github.rest.issues.deleteComment({ owner, repo, comment_id: comment.id }),
    ),
  );

  const previousStates = parseCheckboxStates(existingComment?.body);
  const autoVisual = hasVisualMediaInDescription(pullDetails.body);
  const aiReviewActivity = collectAiReviewActivity({
    reviewRequests,
    reviews,
    reviewComments,
    issueComments: comments.filter((comment) => !hasReminderMarker(comment.body)),
  });

  let reviewThreads = [];
  try {
    reviewThreads = await fetchReviewThreads(github, owner, repo, pr.number);
  } catch (error) {
    core.warning(`Could not fetch review threads for AI feedback status: ${error.message}`);
  }

  const getPermission = await createPermissionResolver(github, owner, repo);
  const threadAnalysis = await analyzeReviewThreads(reviewThreads, latestReviewByUser, getPermission);
  const resolutionStatus = formatAiFeedbackResolutionStatus(
    aiReviewActivity.hasQualifyingActivity,
    threadAnalysis.aiUnresolved,
  );
  const maintainerSection = formatMaintainerReviewSection(threadAnalysis.maintainerUnresolved);
  const reviewerSection = formatReviewerFeedbackSection(threadAnalysis.reviewerUnresolved);
  const visualMedia = extractVisualMediaFromDescription(pullDetails.body);

  const states = {
    visual: autoVisual || previousStates.visual,
    structure: previousStates.structure,
    aiReview: aiReviewActivity.hasQualifyingActivity || previousStates.aiReview,
  };

  const body = buildBody(
    states,
    aiReviewActivity.completedAgents,
    aiReviewActivity.failedAgents,
    aiReviewActivity.excludedAgents,
    resolutionStatus,
    visualMedia,
    maintainerSection,
    reviewerSection,
  );

  if (existingComment) {
    if (existingComment.body === body) {
      core.info('Reminder checklist is already up to date.');
      return;
    }

    await github.rest.issues.updateComment({
      owner,
      repo,
      comment_id: existingComment.id,
      body,
    });
    core.info('Updated PR process reminder checklist.');
    return;
  }

  await github.rest.issues.createComment({ owner, repo, issue_number: pr.number, body });
  core.info('Posted PR process reminder checklist.');
}

export {
  MARKER,
  MERGE_PERMISSIONS,
  hasReminderMarker,
  parseCheckboxStates,
  hasVisualMediaInDescription,
  extractVisualMediaFromDescription,
  formatUnresolvedCommentsCollapsible,
  formatVisualMediaCollapsible,
  formatAiFeedbackResolutionStatus,
  formatMaintainerReviewSection,
  formatReviewerFeedbackSection,
  buildBody,
  collectAiReviewActivity,
  analyzeReviewThreads,
  runPrProcessReminder,
};
