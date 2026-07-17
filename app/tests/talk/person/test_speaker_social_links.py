import pytest
from django_scopes import scope

from eventyay.base.models import SpeakerSocialLink
from eventyay.common.social_links import build_social_link_url, serialize_social_link
from eventyay.person.forms.social_link import (
    build_speaker_social_links_formset,
    save_speaker_social_links,
)


def test_build_social_link_url_with_handle_and_full_url():
    assert build_social_link_url('github', 'octocat') == 'https://github.com/octocat'
    assert build_social_link_url('linkedin', 'https://linkedin.com/in/someone') == 'https://linkedin.com/in/someone'
    assert build_social_link_url('website', 'example.com/me') == 'https://example.com/me'


def test_build_social_link_url_rejects_non_http_schemes():
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        build_social_link_url('website', 'javascript://%0Aalert(1)')
    with pytest.raises(ValidationError):
        build_social_link_url('github', 'ftp://files.example.com/user')


@pytest.mark.django_db
def test_speaker_social_links_formset_save(speaker, event):
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'optional', 'public': True}
        event.cfp.save()
        profile = speaker.event_profile(event)

        formset = build_speaker_social_links_formset(
            profile=profile,
            data={
                'social_links-TOTAL_FORMS': '2',
                'social_links-INITIAL_FORMS': '0',
                'social_links-MIN_NUM_FORMS': '0',
                'social_links-MAX_NUM_FORMS': '1000',
                'social_links-0-network': 'github',
                'social_links-0-path': 'octocat',
                'social_links-0-DELETE': '',
                'social_links-1-network': 'linkedin',
                'social_links-1-path': 'someone',
                'social_links-1-DELETE': '',
            },
        )
        assert formset.is_valid(), formset.errors
        save_speaker_social_links(profile, formset)

        links = list(profile.social_links.order_by('network'))
        assert len(links) == 2
        assert links[0].network == 'github'
        assert links[0].url == 'https://github.com/octocat'
        assert links[1].network == 'linkedin'
        assert links[1].url == 'https://linkedin.com/in/someone'

        serialized = serialize_social_link(links[0])
        assert serialized['key'] == 'github'
        assert serialized['url'] == 'https://github.com/octocat'
        assert serialized['icon_class'] == 'fa-github'


@pytest.mark.django_db
def test_speaker_social_links_hidden_when_cfp_disabled(speaker, event, client):
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'do_not_ask', 'public': True}
        event.cfp.save()
        profile = speaker.event_profile(event)
        SpeakerSocialLink.objects.create(
            profile=profile,
            network='github',
            url='https://github.com/octocat',
        )

    response = client.get(profile.urls.public)
    # public speaker page is a shell; API is the source of truth
    assert response.status_code == 200

    api_response = client.get(f'/api/v1/events/{event.slug}/speakers/{speaker.code}/')
    assert api_response.status_code == 200
    assert 'social_links' not in api_response.json()


@pytest.mark.django_db
def test_speaker_social_links_public_api(speaker, event, client):
    with scope(event=event):
        event.cfp.fields['social_links'] = {'visibility': 'optional', 'public': True}
        event.cfp.save()
        profile = speaker.event_profile(event)
        SpeakerSocialLink.objects.create(
            profile=profile,
            network='x',
            url='https://x.com/someone',
        )

    api_response = client.get(f'/api/v1/events/{event.slug}/speakers/{speaker.code}/')
    assert api_response.status_code == 200
    data = api_response.json()
    assert 'social_links' in data
    assert data['social_links'][0]['key'] == 'x'
    assert data['social_links'][0]['url'] == 'https://x.com/someone'
