// Tier order (max 5): area → stack → test → intent (branch) → other
const MAX = 5;
const MAX_AREAS = 2;

const TEST = ['app/tests/**', '**/test_*.py', '**/*_test.py', '**/*.test.js', '**/*.spec.js', '**/*.spec.ts'];

const LABELS = [
  ['fix', 'ee0701', 'Bug fix (fix/, fix-* branches)'],
  ['chore', '888888', 'Maintenance (chore/, patch/)'],
  ['refactor', 'fbca04', 'Code restructuring (refactor/)'],
  ['perf', 'f9d0c4', 'Performance (perf/)'],
  ['style', 'e4e669', 'Formatting only (style/)'],
  ['revert', 'ffffff', 'Reverts a previous change'],
  ['backend', '2b67c6', 'Python/Django source files'],
  ['frontend', '168700', 'JS, Vue, CSS, SCSS, templates'],
  ['database', 'C2E0C6', 'Database migrations'],
  ['ci', '1D76DB', 'GitHub Actions and CI scripts'],
  ['deployment', '5319E7', 'Docker and deployment config'],
  ['documentation', '5A3AE6', 'Documentation'],
  ['test', 'A9EF22', 'Tests'],
  ['internationalization', 'C5DEF5', 'Translations and locale'],
  ['dependencies', '0366d6', 'Dependency updates'],
  ['presale', '0075CA', 'Attendee ticket shop'],
  ['control', '0052CC', 'Organiser control panel'],
  ['orga', '006B75', 'Talk organiser UI'],
  ['cfp', '0E8A16', 'Call-for-proposals'],
  ['submission', '2EA043', 'Talk submissions and reviews'],
  ['agenda', '1D7874', 'Public agenda and timetable'],
  ['schedule', '238636', 'Schedule backend and webapp/schedule'],
  ['schedule-editor', '196C2E', 'Schedule editor webapp'],
  ['webcheckin', '9A6700', 'Web check-in webapp and plugin'],
  ['video', 'A371F7', 'Video conference webapp'],
  ['api', '0969DA', 'REST API'],
  ['base', '8250DF', 'Shared models and services'],
  ['common', '8957E5', 'common/ and eventyay_common/'],
  ['mail', 'BF3989', 'Email templates and sending'],
  ['multidomain', '6639BA', 'Multi-domain routing'],
  ['storage', '8250DF', 'File storage'],
  ['config', '57606A', 'Django settings'],
  ['plugins', '953800', 'Eventyay plugins'],
  ['core', '656D76', 'Core helpers and permissions'],
];

const AREAS = [
  ['schedule-editor', ['app/eventyay/webapp/schedule-editor/**']],
  ['webcheckin', ['app/eventyay/webapp/webcheckin/**', 'app/eventyay/plugins/webcheckin/**']],
  ['video', ['app/eventyay/webapp/video/**', 'app/tests/**/video/**', 'app/tests/**/*video*']],
  ['schedule', ['app/eventyay/webapp/schedule/**', 'app/eventyay/schedule/**', 'app/tests/**/schedule/**']],
  ['presale', ['app/eventyay/presale/**', 'app/tests/**/presale/**', 'doc/**/presale/**']],
  ['control', ['app/eventyay/control/**', 'app/tests/**/control/**', 'doc/admin/**']],
  ['orga', ['app/eventyay/orga/**', 'app/tests/**/orga/**', 'doc/talk/**']],
  ['cfp', ['app/eventyay/cfp/**', 'app/tests/**/cfp/**']],
  ['submission', ['app/eventyay/submission/**', 'app/tests/**/submission/**']],
  ['agenda', ['app/eventyay/agenda/**', 'app/tests/**/agenda/**']],
  ['api', ['app/eventyay/api/**', 'app/tests/**/api/**', 'doc/api/**']],
  ['common', ['app/eventyay/common/**', 'app/eventyay/eventyay_common/**', 'app/tests/**/common/**', 'app/tests/**/eventyay_common/**']],
  ['mail', ['app/eventyay/mail/**', 'app/tests/**/mail/**']],
  ['multidomain', ['app/eventyay/multidomain/**', 'app/tests/**/multidomain/**']],
  ['storage', ['app/eventyay/storage/**', 'app/tests/**/storage/**']],
  ['config', ['app/eventyay/config/**', 'app/manage.py']],
  ['plugins', ['app/eventyay/plugins/**', 'app/tests/**/plugins/**', 'doc/plugins/**']],
  ['core', ['app/eventyay/core/**', 'app/eventyay/helpers/**', 'app/eventyay/features/**', 'app/eventyay/person/**', 'app/eventyay/talk_rules/**', 'app/eventyay/event/**']],
  ['base', ['app/eventyay/base/**', 'app/tests/**/base/**', 'app/tests/**/tickets/**']],
];

const LAYERS = [
  ['frontend', ['app/**/*.js', 'app/**/*.ts', 'app/**/*.vue', 'app/**/*.scss', 'app/**/*.css', 'app/**/package.json', 'app/eventyay/static/**', 'app/eventyay/static.dist/**', 'app/eventyay/jinja-templates/**', 'app/**/templates/**']],
  ['backend', ['app/**/*.py', 'app/pyproject.toml', 'app/uv.lock']],
];

const META = [
  ['database', ['app/eventyay/**/migrations/**']],
  ['ci', ['.github/workflows/**', '.github/scripts/**']],
  ['deployment', ['deployment/**', 'docker-compose.yml', 'Dockerfile', '**/Dockerfile', '.dockerignore']],
  ['documentation', ['doc/**', '**/*.md', '**/*.rst', 'README.rst', 'CONTRIBUTING.md', 'DEPLOYMENT.md', 'agents.md', 'AGENTS.md']],
  ['test', TEST],
  ['internationalization', ['app/eventyay/locale/**', '**/*.po']],
  ['dependencies', ['app/pyproject.toml', 'app/uv.lock', '**/package-lock.json', '**/yarn.lock', '.github/dependabot.yml']],
];

const OTHER = ['database', 'ci', 'deployment', 'documentation', 'internationalization', 'dependencies'];

const BRANCH = [
  ['fix', [/^fix\//, /^fix-/]],
  ['chore', [/^chore[/\-]/, /^patch\//]],
  ['refactor', [/^refactor\//, /^refactor-/]],
  ['perf', [/^perf\//, /^performance[/\-]/]],
  ['style', [/^style\//]],
  ['revert', [/^revert-/]],
];

const MANAGED = new Set(LABELS.map(([name]) => name));

const glob = (path, pattern) => {
  const re = pattern.replace(/[.+^${}()|[\]\\]/g, '\\$&').replace(/\*\*/g, '\0').replace(/\*/g, '[^/]*').replace(/\0/g, '.*');
  return new RegExp(`^${re}$`).test(path);
};

const any = (path, patterns) => patterns.some((p) => glob(path, p));

const bump = (map, key) => map.set(key, (map.get(key) ?? 0) + 1);

const rank = (map, keys) =>
  keys.filter((k) => (map.get(k) ?? 0) > 0).sort((a, b) => (map.get(b) ?? 0) - (map.get(a) ?? 0) || a.localeCompare(b));

const branchIntent = (ref) => BRANCH.find(([, ps]) => ps.some((p) => p.test(ref)))?.[0] ?? null;

function score(files) {
  const areas = new Map();
  const layers = new Map();
  const meta = new Map();

  for (const file of files) {
    const test = any(file, TEST);
    const area = AREAS.find(([, ps]) => any(file, ps))?.[0] ?? (glob(file, 'app/**') ? 'base' : null);
    if (area) bump(areas, area);

    if (!test) {
      for (const [label, ps] of LAYERS) {
        if (any(file, ps)) bump(layers, label);
      }
    }
    for (const [label, ps] of META) {
      if (any(file, ps)) bump(meta, label);
    }
  }
  return { areas, layers, meta };
}

function pick({ areas, layers, meta }, intent) {
  const out = [];
  const add = (l) => {
    if (l && out.length < MAX && !out.includes(l)) out.push(l);
  };

  for (const l of rank(areas, AREAS.map(([n]) => n)).slice(0, MAX_AREAS)) add(l);
  for (const l of rank(layers, ['frontend', 'backend'])) add(l);
  if (meta.get('test')) add('test');
  add(intent);
  for (const l of rank(meta, OTHER)) add(l);
  return out;
}

async function ensureLabels(github, owner, repo) {
  for (const [name, color, description] of LABELS) {
    try {
      await github.rest.issues.getLabel({ owner, repo, name });
    } catch (e) {
      if (e.status !== 404) throw e;
      await github.rest.issues.createLabel({ owner, repo, name, color, description });
    }
  }
}

export async function runPrLabeler({ github, context, core, prNumber }) {
  const { owner, repo } = context.repo;
  const number = prNumber ?? context.payload.pull_request?.number ?? Number(context.payload.inputs?.['pr-number']);
  if (!number) return core.setFailed('Could not determine pull request number.');

  await ensureLabels(github, owner, repo);

  const { data: pr } = await github.rest.pulls.get({ owner, repo, pull_number: number });
  const files = [];
  for (let page = 1; ; page += 1) {
    const { data } = await github.rest.pulls.listFiles({ owner, repo, pull_number: number, per_page: 100, page });
    files.push(...data);
    if (data.length < 100) break;
  }

  const intent = branchIntent(pr.head.ref);
  const selected = pick(score(files.map((f) => f.filename)), intent);

  const { data: issue } = await github.rest.issues.get({ owner, repo, issue_number: number });
  const current = issue.labels.map((l) => (typeof l === 'string' ? l : l.name));

  for (const l of current.filter((l) => MANAGED.has(l) && !selected.includes(l))) {
    await github.rest.issues.removeLabel({ owner, repo, issue_number: number, name: l });
  }
  const add = selected.filter((l) => !current.includes(l));
  if (add.length) await github.rest.issues.addLabels({ owner, repo, issue_number: number, labels: add });

  core.info(`PR #${number} (${pr.head.ref}): ${selected.join(', ') || '(none)'}`);
}
