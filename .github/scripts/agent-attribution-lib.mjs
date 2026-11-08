// Detects AI models and harnesses/IDEs used to create a PR, matching the
// attribution convention seen in t3code ("Created with <Model> in <Harness>").
// Scans PR description, commit messages, and git trailers (e.g. Co-authored-by).
// If an agent is detected but attribution is missing in the PR body, it appends it,
// and ensures the "ai-assisted" label is applied.

export const AI_LABEL = 'ai-assisted';
export const ATTRIBUTION_PATTERN = /Created with ([\w\s.-]+?) in ([\w\s.-]+?)(?:,\s*run from ([\w\s.-]+?))?\s*\.?$/im;

export const KNOWN_MODELS = [
  { name: 'Claude Opus 4.6', regex: /\bclaude[- ](?:opus[- ])?4\.6\b/i },
  { name: 'Claude Opus 5.5', regex: /\bclaude[- ](?:opus[- ])?5\.5\b/i },
  { name: 'Claude Opus', regex: /\bclaude[- ]opus\b/i },
  { name: 'Claude Sonnet 4.6', regex: /\bclaude[- ](?:sonnet[- ])?4\.6\b/i },
  { name: 'Claude Sonnet 3.5', regex: /\bclaude[- ](?:sonnet[- ])?3\.5\b/i },
  { name: 'Claude Sonnet', regex: /\bclaude[- ]sonnet\b/i },
  { name: 'Claude Haiku', regex: /\bclaude[- ]haiku\b/i },
  { name: 'Claude', regex: /\bclaude\b/i },
  { name: 'GPT-4o', regex: /\bgpt-4o\b/i },
  { name: 'GPT-4', regex: /\bgpt-4\b/i },
  { name: 'Codex', regex: /\bcodex\b/i },
  { name: 'Gemini 2.0 Flash', regex: /\bgemini[- ](?:2\.0[- ])?flash\b/i },
  { name: 'Gemini 2.0 Pro', regex: /\bgemini[- ](?:2\.0[- ])?pro\b/i },
  { name: 'Gemini 1.5 Pro', regex: /\bgemini[- ](?:1\.5[- ])?pro\b/i },
  { name: 'Gemini', regex: /\bgemini\b/i },
  { name: 'Composer', regex: /\bcomposer\b/i },
  { name: 'DeepSeek-V3', regex: /\bdeepseek[- ]v3\b/i },
  { name: 'DeepSeek-R1', regex: /\bdeepseek[- ]r1\b/i },
];

export const KNOWN_HARNESSES = [
  { name: 'Claude Code', regex: /\bclaude[- ]code\b|Co-authored-by:\s*Claude\s*<noreply@anthropic\.com>/i },
  { name: 'Cursor', regex: /\bcursor\b/i },
  { name: 'GitHub Copilot', regex: /\b(?:github[- ])?copilot\b|Co-authored-by:\s*Copilot\s*<copilot@github\.com>/i },
  { name: 'Antigravity', regex: /\bantigravity\b/i },
  { name: 'Windsurf', regex: /\bwindsurf\b/i },
  { name: 'Aider', regex: /\baider\b/i },
  { name: 'T3 Code', regex: /\bt3[- ]code\b/i },
  { name: 'VS Code', regex: /\bvisual studio code\b|\bvs\s*code\b/i },
];

// Parses self-reported attribution if already present in text.
export function parseExistingAttribution(text) {
  if (!text) return null;
  const match = text.match(ATTRIBUTION_PATTERN);
  if (!match) return null;
  return {
    raw: match[0].trim(),
    model: match[1]?.trim(),
    harness: match[2]?.trim(),
    environment: match[3]?.trim(),
  };
}

// Detects model and harness from texts (commit messages, trailers, PR body).
export function detectAgentDetails(texts) {
  const combined = texts.filter(Boolean).join('\n');

  // Check if explicit attribution line is already in the texts
  const existing = parseExistingAttribution(combined);
  if (existing) {
    return {
      model: existing.model,
      harness: existing.harness,
      environment: existing.environment,
      explicit: true,
    };
  }

  let detectedModel = null;
  for (const m of KNOWN_MODELS) {
    if (m.regex.test(combined)) {
      detectedModel = m.name;
      break;
    }
  }

  let detectedHarness = null;
  for (const h of KNOWN_HARNESSES) {
    if (h.regex.test(combined)) {
      detectedHarness = h.name;
      break;
    }
  }

  if (detectedModel || detectedHarness) {
    return {
      model: detectedModel || 'AI Model',
      harness: detectedHarness || 'Coding Agent',
      environment: null,
      explicit: false,
    };
  }

  return null;
}

// Formats attribution line following t3code style: "Created with <Model> in <Harness>, run from <Environment>."
export function formatAttributionLine({ model, harness, environment }) {
  if (environment) {
    return `Created with ${model} in ${harness}, run from ${environment}.`;
  }
  return `Created with ${model} in ${harness}.`;
}

// Appends the attribution line to PR body if not already present.
export function appendAttributionToBody(body, attributionLine) {
  const current = (body || '').trimEnd();
  if (current.includes(attributionLine)) {
    return current;
  }
  return current ? `${current}\n\n${attributionLine}\n` : `${attributionLine}\n`;
}

export async function runAgentAttribution({ github, context, core }) {
  const { owner, repo } = context.repo;
  const prNumber = context.payload.pull_request?.number;

  if (!prNumber) {
    core.info('No pull request found in context, nothing to do.');
    return;
  }

  const { data: pr } = await github.rest.pulls.get({
    owner,
    repo,
    pull_number: prNumber,
  });

  if (pr.state !== 'open') {
    core.info(`#${prNumber} is ${pr.state}, skipping.`);
    return;
  }

  // Collect text signals from PR body and commit messages
  const texts = [pr.body || ''];
  const commits = await github.paginate(github.rest.pulls.listCommits, {
    owner,
    repo,
    pull_number: prNumber,
    per_page: 100,
  });

  for (const c of commits) {
    if (c.commit?.message) {
      texts.push(c.commit.message);
    }
  }

  const detected = detectAgentDetails(texts);

  if (!detected) {
    core.info(`#${prNumber}: No AI model or harness detected.`);
    return;
  }

  const attributionLine = formatAttributionLine(detected);
  core.info(`#${prNumber}: Detected AI attribution -> "${attributionLine}"`);

  // Ensure PR body has attribution
  const existingAttribution = parseExistingAttribution(pr.body);
  if (!existingAttribution) {
    const updatedBody = appendAttributionToBody(pr.body, attributionLine);
    await github.rest.pulls.update({
      owner,
      repo,
      pull_number: prNumber,
      body: updatedBody,
    });
    core.info(`#${prNumber}: Appended attribution to PR description.`);
  } else {
    core.info(`#${prNumber}: PR description already contains attribution ("${existingAttribution.raw}").`);
  }

  // Ensure ai-assisted label exists and is applied
  try {
    await github.rest.issues.getLabel({ owner, repo, name: AI_LABEL });
  } catch (error) {
    if (error.status === 404) {
      try {
        await github.rest.issues.createLabel({
          owner,
          repo,
          name: AI_LABEL,
          color: '7B61FF',
          description: 'PR created or assisted with an AI coding agent',
        });
        core.info(`Created label "${AI_LABEL}".`);
      } catch (createError) {
        if (createError.status !== 422) throw createError;
      }
    } else {
      throw error;
    }
  }

  const currentLabels = (pr.labels || []).map((l) => l.name);
  if (!currentLabels.includes(AI_LABEL)) {
    await github.rest.issues.addLabels({
      owner,
      repo,
      issue_number: prNumber,
      labels: [AI_LABEL],
    });
    core.info(`#${prNumber}: Added "${AI_LABEL}" label.`);
  }
}
