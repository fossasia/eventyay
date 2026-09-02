import pytest
from django.template import Context, Template
from django_scopes import scope

from eventyay.person.forms import SpeakerProfileForm


@pytest.mark.django_db
def test_avatar_label_shows_required_asterisk_when_avatar_required(event, speaker):
    with scope(event=event):
        event.cfp.fields['avatar'] = {'visibility': 'required', 'public': True}
        event.cfp.save()

        form = SpeakerProfileForm(event=event, user=speaker)
        template = Template('{% include "common/avatar.html" with user=speaker form=form %}')
        context = {
            'event': event,
            'form': form,
            'speaker': speaker,
            'request': type('Req', (), {'event': event})(),
        }
        rendered = template.render(Context(context))

        label_part = rendered.split('<div class="avatar-form-fields')[0]
        assert '<span class="d-inline text-danger"> *</span>' in label_part


@pytest.mark.django_db
def test_avatar_label_no_asterisk_when_avatar_not_required(event, speaker):
    with scope(event=event):
        event.cfp.fields['avatar'] = {'visibility': 'optional', 'public': True}
        event.cfp.save()

        form = SpeakerProfileForm(event=event, user=speaker)
        template = Template('{% include "common/avatar.html" with user=speaker form=form %}')
        context = {
            'event': event,
            'form': form,
            'speaker': speaker,
            'request': type('Req', (), {'event': event})(),
        }
        rendered = template.render(Context(context))

        label_part = rendered.split('<div class="avatar-form-fields')[0]
        assert '<span class="d-inline text-danger"> *</span>' not in label_part


@pytest.mark.django_db
def test_speaker_profile_form_orders_social_links_by_config(event, speaker):
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'optional', 'public': True}
        event.cfp.fields['biography'] = {'visibility': 'optional', 'public': True}
        event.cfp.fields['avatar'] = {'visibility': 'optional', 'public': True}
        # Configure custom order: social_links before biography and avatar
        event.cfp.settings['fields_config'] = {
            'speaker': ['social_links', 'biography', 'fullname', 'avatar']
        }
        event.cfp.save()

        form = SpeakerProfileForm(event=event, user=speaker)
        field_keys = list(form.fields.keys())

        assert 'social_links' in field_keys
        assert field_keys.index('social_links') < field_keys.index('biography')
        assert field_keys.index('social_links') < field_keys.index('avatar')


@pytest.mark.django_db
def test_speaker_profile_form_orders_social_links_after_biography(event, speaker):
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'optional', 'public': True}
        event.cfp.fields['biography'] = {'visibility': 'optional', 'public': True}
        event.cfp.fields['avatar'] = {'visibility': 'optional', 'public': True}
        # Configure custom order: biography before social_links
        event.cfp.settings['fields_config'] = {
            'speaker': ['fullname', 'biography', 'social_links', 'avatar']
        }
        event.cfp.save()

        form = SpeakerProfileForm(event=event, user=speaker)
        field_keys = list(form.fields.keys())

        assert 'social_links' in field_keys
        assert field_keys.index('biography') < field_keys.index('social_links')
        assert field_keys.index('social_links') < field_keys.index('avatar')


@pytest.mark.django_db
def test_speaker_profile_form_excludes_social_links_when_disabled(event, speaker):
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'do_not_ask', 'public': True}
        event.cfp.save()

        form = SpeakerProfileForm(event=event, user=speaker)
        assert 'social_links' not in form.fields
