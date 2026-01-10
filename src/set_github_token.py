import os
import toml

# Get the GitHub token from environment variables
github_token = os.getenv('GITHUB_TOKEN')

PYPROJECT_PATH = os.getenv('PYPROJECT_PATH', '/pretix/pyproject.toml')

STRIPE_PREFIX = 'eventyay-stripe'
PAYPAL_PREFIX = 'eventyay-paypal'

STRIPE_REPO = 'fossasia/eventyay-tickets-stripe'
PAYPAL_REPO = 'fossasia/eventyay-tickets-paypal'
BRANCH = 'master'

# Load the pyproject.toml file
pyproject = toml.load(PYPROJECT_PATH)

# Normalize access to project section
project = pyproject.setdefault('project', {})
dependencies = project.get('dependencies', [])

# If github_token is None, remove Stripe and PayPal dependencies
if not github_token:
    dependencies = [
        dep
        for dep in dependencies
        if not dep.startswith((STRIPE_PREFIX, PAYPAL_PREFIX))
    ]
else:
    # Inject GitHub token into private dependency URLs
    for i, dep in enumerate(dependencies):
        if dep.startswith(STRIPE_PREFIX):
            dependencies[i] = (
                f'{STRIPE_PREFIX} @ git+https://{github_token}@github.com/'
                f'{STRIPE_REPO}.git@{BRANCH}'
            )
        elif dep.startswith(PAYPAL_PREFIX):
            dependencies[i] = (
                f'{PAYPAL_PREFIX} @ git+https://{github_token}@github.com/'
                f'{PAYPAL_REPO}.git@{BRANCH}'
            )

# Write back updated dependencies
project['dependencies'] = dependencies

# Save the updated pyproject.toml
with open(PYPROJECT_PATH, 'w') as file:
    toml.dump(pyproject, file)
