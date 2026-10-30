from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from eventyay.base.models import OrganizerRequestFieldSetting, OrganizerRequestQuestion
from eventyay.base.settings import GlobalSettingsObject


REQUEST_FIELDS = (
    {
        'key': 'name',
        'label': _('Your name'),
        'help_text': _('Who is asking for the organiser account.'),
        'locked': True,
    },
    {
        'key': 'email',
        'label': _('Email'),
        'help_text': _('Where we send the decision, and the login for the organiser account.'),
        'locked': True,
    },
    {
        'key': 'organizer_name',
        'label': _('Organiser name on Eventyay'),
        'help_text': _('The name shown on your event pages.'),
        'locked': True,
    },
    {
        'key': 'slug',
        'label': _('Short form'),
        'help_text': _('Used in your web addresses. This cannot be changed later.'),
        'locked': True,
    },
    {
        'key': 'affiliation',
        'label': _('Organisation'),
        'help_text': _('The community, company, or university these events belong to.'),
        'locked': False,
    },
    {
        'key': 'events',
        'label': _('Events you organise'),
        'help_text': _('Name the events, what kind they are, and add a link if you have one.'),
        'locked': False,
    },
)


def ensure_request_field_settings():
    existing = set(OrganizerRequestFieldSetting.objects.values_list('key', flat=True))
    missing = [
        OrganizerRequestFieldSetting(key=field['key'], position=position, active=True, required=True)
        for position, field in enumerate(REQUEST_FIELDS)
        if field['key'] not in existing
    ]
    if missing:
        OrganizerRequestFieldSetting.objects.bulk_create(missing)


def organizer_request_enabled() -> bool:
    return GlobalSettingsObject().settings.get('organizer_request_enabled', as_type=bool, default=True)


def ordered_form_items():
    ensure_request_field_settings()
    catalog = {field['key']: field for field in REQUEST_FIELDS}
    items = []
    for setting in OrganizerRequestFieldSetting.objects.all():
        spec = catalog.get(setting.key)
        if spec is not None:
            items.append(('field', setting, spec))
    for question in OrganizerRequestQuestion.objects.all():
        items.append(('question', question, None))
    items.sort(key=lambda item: (item[1].position, 0 if item[0] == 'field' else 1, item[1].pk))
    return items


def rewrite_positions(items):
    for position, (kind, obj, _spec) in enumerate(items):
        if obj.position == position:
            continue
        model = OrganizerRequestFieldSetting if kind == 'field' else OrganizerRequestQuestion
        model.objects.filter(pk=obj.pk).update(position=position)
        obj.position = position


def next_form_position():
    items = ordered_form_items()
    if not items:
        return 0
    return max(item[1].position for item in items) + 1


def save_form_order(tokens):
    items = ordered_form_items()
    by_token = {}
    for item in items:
        kind, obj, _spec = item
        token = f'field:{obj.key}' if kind == 'field' else f'question:{obj.pk}'
        by_token[token] = item
    if len(tokens) != len(by_token) or len(set(tokens)) != len(tokens):
        return False
    if any(token not in by_token for token in tokens):
        return False
    rewrite_positions([by_token[token] for token in tokens])
    return True


def organiser_form_rows():
    items = ordered_form_items()
    rows = []
    for kind, obj, spec in items:
        if kind == 'field':
            required = spec['locked'] or obj.required
            rows.append(
                {
                    'label': spec['label'],
                    'help_text': spec['help_text'],
                    'locked': spec['locked'],
                    'active': spec['locked'] or obj.active,
                    'required': required,
                    'required_state': 'required' if required else 'optional',
                    'is_custom': False,
                    'sort_id': f'field:{obj.key}',
                    'toggle_url': ''
                    if spec['locked']
                    else reverse('eventyay_admin:admin.organizer_forms.field', kwargs={'key': obj.key}),
                    'edit_url': '',
                    'delete_url': '',
                }
            )
            continue
        rows.append(
            {
                'label': obj.label,
                'help_text': obj.help_text,
                'locked': False,
                'active': obj.active,
                'required': obj.required,
                'required_state': 'required' if obj.required else 'optional',
                'is_custom': True,
                'sort_id': f'question:{obj.pk}',
                'toggle_url': reverse('eventyay_admin:admin.organizer_forms.toggle', kwargs={'pk': obj.pk}),
                'edit_url': reverse('eventyay_admin:admin.organizer_forms.edit', kwargs={'pk': obj.pk}),
                'delete_url': reverse('eventyay_admin:admin.organizer_forms.delete', kwargs={'pk': obj.pk}),
            }
        )
    return rows
