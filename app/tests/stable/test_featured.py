import json
import re

import pytest
import datetime as dt
from django.contrib.auth.models import AnonymousUser
from django_scopes import scope
from eventyay.base.models import Submission, Room, TalkSlot, SubmissionType
from eventyay.common.templatetags.event_tags import show_schedule_nav_tab

@pytest.mark.django_db
class TestFeaturedSessions:
    def test_featured_sessions_and_exporters(self, client, organizer, event, user):
        with scope(event=event):
            # 1. Create a submission type
            sub_type = SubmissionType.objects.create(event=event, name="Talk")
            
            # 2. Create featured and non-featured submissions
            sub_featured = Submission.objects.create(
                title="Featured Session Title",
                event=event,
                submission_type=sub_type,
                abstract="An abstract for a featured session",
                content_locale="en",
                is_featured=True,
            )
            sub_featured.speakers.add(user)
            sub_featured.accept()
            sub_featured.confirm()

            sub_regular = Submission.objects.create(
                title="Regular Session Title",
                event=event,
                submission_type=sub_type,
                abstract="An abstract for a regular session",
                content_locale="en",
                is_featured=False,
            )
            sub_regular.speakers.add(user)
            sub_regular.accept()
            sub_regular.confirm()

            # 3. Create room and release schedule
            room = Room.objects.create(event=event, name="Room A")
            
            # WIP slot for featured
            TalkSlot.objects.update_or_create(
                submission=sub_featured,
                schedule=event.wip_schedule,
                defaults={
                    "is_visible": True,
                    "start": event.date_from + dt.timedelta(hours=10),
                    "end": event.date_from + dt.timedelta(hours=11),
                    "room": room,
                },
            )
            # WIP slot for regular
            TalkSlot.objects.update_or_create(
                submission=sub_regular,
                schedule=event.wip_schedule,
                defaults={
                    "is_visible": True,
                    "start": event.date_from + dt.timedelta(hours=11),
                    "end": event.date_from + dt.timedelta(hours=12),
                    "room": room,
                },
            )
            
            # Release schedule
            event.release_schedule("v1")
            schedule = event.current_schedule
            
            # Put slots in current schedule
            TalkSlot.objects.update_or_create(
                submission=sub_featured,
                schedule=schedule,
                defaults={
                    "is_visible": True,
                    "start": event.date_from + dt.timedelta(hours=10),
                    "end": event.date_from + dt.timedelta(hours=11),
                    "room": room,
                },
            )
            TalkSlot.objects.update_or_create(
                submission=sub_regular,
                schedule=schedule,
                defaults={
                    "is_visible": True,
                    "start": event.date_from + dt.timedelta(hours=11),
                    "end": event.date_from + dt.timedelta(hours=12),
                    "room": room,
                },
            )
            
            # Set show_featured flag
            event.feature_flags["show_featured"] = "always"
            event.save()

            featured_url = str(event.urls.featured)
            schedule_export_base = str(event.urls.schedule).rstrip('/')

        # 4. Request the featured page
        response = client.get(featured_url)
        assert response.status_code == 200
        
        # Verify schedule JSON only contains the featured talk
        context = response.context
        assert 'schedule_data_json' in context
        schedule_data = context['schedule_data_json']
        assert "Featured Session Title" in schedule_data
        assert "Regular Session Title" not in schedule_data
        assert '"exports_disabled": true' in schedule_data

        # 5. Featured exports stay blocked until the schedule is publicly released
        export_json_url = f'{schedule_export_base}.json?featured=true'
        response = client.get(export_json_url)
        assert response.status_code == 404

        with scope(event=event):
            event.settings.show_schedule = True
            event.talks_published = True
            event.save()

        response = client.get(export_json_url)
        assert response.status_code == 200
        export_content = response.content.decode('utf-8')
        assert "Featured Session Title" in export_content
        assert "Regular Session Title" not in export_content

        # Request exporters without featured=true (should contain both)
        export_json_url_all = f'{schedule_export_base}.json'
        response = client.get(export_json_url_all)
        assert response.status_code == 200
        export_content_all = response.content.decode('utf-8')
        assert "Featured Session Title" in export_content_all
        assert "Regular Session Title" in export_content_all

        # 6. Test navigation tab visibility
        from django.test import RequestFactory
        from eventyay.common.templatetags.event_tags import can_view_featured_sessions_public

        rf = RequestFactory()
        req = rf.get('/')
        req.event = event
        req.user = user

        # 6.1. No featured sessions anywhere (always mode still shows the nav tab)
        with scope(event=event):
            sub_featured.is_featured = False
            sub_featured.save()
            TalkSlot.objects.filter(schedule=schedule, submission=sub_featured).delete()

        ctx = {'request': req}
        assert can_view_featured_sessions_public(ctx, event) is True

        response = client.get(featured_url)
        assert response.status_code == 200
        assert 'No featured sessions have been selected yet' in response.content.decode()

        # 6.2. Featured submission present, but no schedule released — schedule list with pending pill
        with scope(event=event):
            sub_featured.is_featured = True
            sub_featured.save()
            event.schedules.filter(version__isnull=False).update(published=None)
            event.__dict__.pop('current_schedule', None)

        assert can_view_featured_sessions_public(ctx, event) is True
        response = client.get(featured_url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Featured Session Title" in content
        assert 'schedule_pending' in content or 'Coming soon' in content
        assert '<article id="featured-talks">' not in content
        meta = json.loads(response.context['schedule_meta_json'])
        assert meta['exporters'] == []

        export_json_url = f'{schedule_export_base}.json?featured=true'
        response = client.get(export_json_url)
        assert response.status_code == 404

        # 6.3. Schedule released, has featured talks
        with scope(event=event):
            event.release_schedule("v2")
            new_schedule = event.current_schedule
            TalkSlot.objects.create(
                submission=sub_featured,
                schedule=new_schedule,
                is_visible=True,
                start=event.date_from + dt.timedelta(hours=10),
                end=event.date_from + dt.timedelta(hours=11),
                room=room,
            )

        assert can_view_featured_sessions_public(ctx, event) is True

        # 6.4. Schedule released, but has NO featured talks (even if confirmed submission exists)
        with scope(event=event):
            TalkSlot.objects.filter(schedule=new_schedule, submission=sub_featured).delete()

        assert can_view_featured_sessions_public(ctx, event) is True


@pytest.mark.django_db
def test_featured_page_hides_schedule_nav_before_public_release(
    client, organizer_client, event, user, rf
):
    with scope(event=event):
        sub_type = SubmissionType.objects.create(event=event, name='Talk')
        sub_featured = Submission.objects.create(
            title='Featured Session Title',
            event=event,
            submission_type=sub_type,
            abstract='An abstract for a featured session',
            content_locale='en',
            is_featured=True,
        )
        sub_featured.speakers.add(user)
        sub_featured.accept()
        sub_featured.confirm()
        room = Room.objects.create(event=event, name='Room A')
        TalkSlot.objects.update_or_create(
            submission=sub_featured,
            schedule=event.wip_schedule,
            defaults={
                'is_visible': True,
                'start': event.date_from + dt.timedelta(hours=10),
                'end': event.date_from + dt.timedelta(hours=11),
                'room': room,
            },
        )
        event.release_schedule('v1')
        event.feature_flags['show_featured'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.talks_published = False
        event.save(update_fields=['feature_flags', 'talks_published'])
        featured_url = str(event.urls.featured)
        schedule_url = str(event.urls.schedule)

    request = rf.get(featured_url)
    request.event = event
    request.user = AnonymousUser()
    assert show_schedule_nav_tab({'request': request}, event=event) is False

    schedule_nav_pattern = re.compile(
        rf'<a href="{re.escape(schedule_url)}" class="header-tab[^"]*"'
    )
    for test_client in (client, organizer_client):
        response = test_client.get(featured_url)
        assert response.status_code == 200
        assert schedule_nav_pattern.search(response.content.decode()) is None


@pytest.mark.django_db
def test_featured_talk_detail_shows_pending_data_when_slot_not_public(client, event, user):
    """Featured talk pages must render when the session is not on the public schedule yet."""
    from django.urls import reverse

    with scope(event=event):
        sub_type = SubmissionType.objects.create(event=event, name='Talk')
        sub_featured = Submission.objects.create(
            title='Hidden Featured Session',
            event=event,
            submission_type=sub_type,
            abstract='Featured abstract',
            content_locale='en',
            is_featured=True,
        )
        sub_featured.speakers.add(user)
        sub_featured.accept()
        sub_featured.confirm()
        room = Room.objects.create(event=event, name='Room A')
        TalkSlot.objects.update_or_create(
            submission=sub_featured,
            schedule=event.wip_schedule,
            defaults={
                'is_visible': False,
                'start': None,
                'end': None,
                'room': room,
            },
        )
        event.release_schedule('v1')
        schedule = event.current_schedule
        TalkSlot.objects.update_or_create(
            submission=sub_featured,
            schedule=schedule,
            defaults={
                'is_visible': False,
                'start': None,
                'end': None,
                'room': room,
            },
        )
        event.feature_flags['show_featured'] = 'always'
        event.feature_flags['show_schedule'] = True
        event.talks_published = True
        event.save(update_fields=['feature_flags', 'talks_published'])
        talk_url = reverse(
            'agenda:talk.detail',
            kwargs={'slug': sub_featured.code, 'event': event.slug, 'organizer': event.organizer.slug},
        )

    response = client.get(talk_url, follow=True)
    assert response.status_code == 200
    schedule_data = json.loads(response.context['schedule_json'])
    assert schedule_data['talks'][0]['code'] == sub_featured.code
    assert schedule_data['talks'][0]['schedule_pending'] is True

