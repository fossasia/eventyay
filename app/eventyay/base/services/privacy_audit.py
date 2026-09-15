import json

from django.core.serializers.json import DjangoJSONEncoder

from eventyay.base.models import LogEntry

PRIVACY_ACTION_PREFIX = 'eventyay.privacy.'

# Settings grouped by the change an auditor cares about. Each group becomes one
# log entry, so saving the form with two category toggles flipped is recorded
# as two readable entries rather than one opaque "settings changed".
PROVIDER_KEY = 'privacy_consent_provider'
CATEGORY_KEYS = {
    'privacy_category_functional_enabled': 'functional',
    'privacy_category_analytics_enabled': 'analytics',
    'privacy_category_marketing_enabled': 'marketing',
    'privacy_category_embed_enabled': 'embed',
}
CMP_KEYS = ('privacy_cmp_provider_name', 'privacy_cmp_script_url')
LEGAL_URL_KEYS = ('privacy_policy_url', 'privacy_cookie_policy_url')

SERVICE_AUDIT_FIELDS = (
    'title',
    'provider',
    'purpose',
    'category',
    'enabled',
    'privacy_policy_url',
    'cookie_names',
    'data_processed',
    'region',
    'dpa_status',
)


def log_privacy_change(user, action, content_object, **data):
    """
    Record an administrator's privacy configuration change.

    Global settings are not a database object, so settings changes are attached
    to the administrator who made them. The audit log filters on the action
    type, not the object, so this does not affect what it shows.
    """
    return LogEntry.objects.create(
        content_object=content_object,
        user=user,
        action_type=f'{PRIVACY_ACTION_PREFIX}{action}',
        data=json.dumps(data, cls=DjangoJSONEncoder),
    )


def _normalise(value):
    # An unset setting reads back as None but the form saves it as '', and
    # hierarkey hands booleans back as strings on some paths. Neither is a
    # change an administrator made.
    if value is None:
        return ''
    if isinstance(value, str) and value in ('True', 'False'):
        return value == 'True'
    return value


def log_settings_changes(user, old, new):
    """Compare privacy settings before and after a save and log what changed."""
    old = {key: _normalise(value) for key, value in old.items()}
    new = {key: _normalise(value) for key, value in new.items()}

    def changed(key):
        return old.get(key) != new.get(key)

    if changed(PROVIDER_KEY):
        log_privacy_change(user, 'provider.changed', user, old=old.get(PROVIDER_KEY), new=new.get(PROVIDER_KEY))

    for key, category in CATEGORY_KEYS.items():
        if bool(old.get(key)) != bool(new.get(key)):
            action = 'category.enabled' if new.get(key) else 'category.disabled'
            log_privacy_change(user, action, user, category=category)

    cmp_changes = {key: {'old': old.get(key), 'new': new.get(key)} for key in CMP_KEYS if changed(key)}
    if cmp_changes:
        log_privacy_change(user, 'cmp.changed', user, changes=cmp_changes)

    url_changes = {key: {'old': old.get(key), 'new': new.get(key)} for key in LEGAL_URL_KEYS if changed(key)}
    if url_changes:
        log_privacy_change(user, 'legal_urls.changed', user, changes=url_changes)


def service_snapshot(service):
    return {field: getattr(service, field) for field in SERVICE_AUDIT_FIELDS}
