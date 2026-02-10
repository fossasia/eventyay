from django.urls import include, path, re_path

from eventyay.common.views import EventSocialMediaCard, get_static

from .views import featured, feed, schedule, speaker, talk, widget


def get_schedule_urls(regex_prefix, name_prefix=''):
    """Given a prefix (e.g. /schedule), generate matching schedule-URLs.

    This is useful to generate the same export URLs for main and
    versioned schedule URLs.
    """

    regex_prefix = regex_prefix.rstrip('/')

    return [
        path(f'{regex_prefix}{regex}', view, name=f'{name_prefix}{name}')
        for regex, view, name in [
            ('/', schedule.ScheduleView.as_view(), 'schedule'),
            ('/nojs', schedule.ScheduleNoJsView.as_view(), 'schedule-nojs'),
            ('.xml', schedule.ExporterView.as_view(), 'export.schedule.xml'),
            ('.xcal', schedule.ExporterView.as_view(), 'export.schedule.xcal'),
            ('.json', schedule.ExporterView.as_view(), 'export.schedule.json'),
            ('.ics', schedule.ExporterView.as_view(), 'export.schedule.ics'),
            (
                '/export/google-calendar',
                schedule.CalendarRedirectView.as_view(),
                'export.google-calendar',
            ),
            (
                '/export/my-google-calendar',
                schedule.CalendarRedirectView.as_view(),
                'export.my-google-calendar',
            ),
            (
                '/export/webcal',
                schedule.CalendarRedirectView.as_view(),
                'export.webcal',
            ),
            (
                '/export/my-webcal',
                schedule.CalendarRedirectView.as_view(),
                'export.my-webcal',
            ),
            (
                '/export/<str:name>/<str:token>/',
                schedule.ExporterView.as_view(),
                'export-tokenized',
            ),
            ('/export/<name>', schedule.ExporterView.as_view(), 'export'),
            ('/widgets/schedule.json', widget.widget_data, 'widget.data'),
            # Legacy widget data URL, but expected in old widget code.
            # Keep at least until end of 2024, reconsider afterwards.
            ('/widget/v2.json', widget.widget_data, 'widget.data.legacy'),
        ]
    ]


app_name = 'agenda'
urlpatterns = [
    path(
        'widgets/schedule.js',
        widget.widget_script,
        name='widget.script',
    ),
    path('static/event.css', widget.event_css, name='event.css'),
    path(
        'schedule/changelog/',
        schedule.ChangelogView.as_view(),
        name='schedule.changelog',
    ),
    path('schedule/feed.xml', feed.ScheduleFeed(), name='feed'),
    # Old widget URL. Keep at least until end of 2024. Will still be used in
    # a lot of old websites, so possibly just keep it forever.
    re_path(
        '^schedule/widget/v2.[a-z]{2}.js$',
        widget.widget_script,
        name='widget.script.legacy',
    ),
    path(
        'schedule/widget/messages.js',
        schedule.schedule_messages,
        name='widget.messages',
    ),
    *get_schedule_urls('schedule'),
    *get_schedule_urls('schedule/v/<version>', 'versioned-'),
    path('featured/', featured.FeaturedView.as_view(), name='featured'),
    path('speakers/', speaker.SpeakerList.as_view(), name='speakers'),
    path(
        'speakers/avatar.svg',
        speaker.empty_avatar_view,
        name='speakers.avatar',
    ),
    path(
        'speakers/by-id/<int:pk>/',
        speaker.SpeakerRedirect.as_view(),
        name='speaker.redirect',
    ),
    path('sessions/', schedule.ScheduleView.as_view(), name='talks'),
    path('talk/<slug>/', talk.TalkView.as_view(), name='talk.detail'),
    path(
        'talk/<slug>/og-image',
        talk.TalkSocialMediaCard.as_view(),
        name='talk-social',
    ),
    path(
        'talk/<slug>/feedback/',
        talk.FeedbackView.as_view(),
        name='feedback',
    ),
    path(
        'talk/<slug>.ics',
        talk.SingleICalView.as_view(),
        name='ical',
    ),
    path(
        'talk/review/<slug>',
        talk.TalkReviewView.as_view(),
        name='review',
    ),
    path(
        'speakers/<code>/',
        speaker.SpeakerView.as_view(),
        name='speaker',
    ),
    path(
        'speakers/<code>/og-image',
        speaker.SpeakerSocialMediaCard.as_view(),
        name='speaker-social',
    ),
    path(
        'speakers/<code>/talks.ics',
        speaker.SpeakerTalksIcalView.as_view(),
        name='speaker.talks.ical',
    ),
    path(
        'og-image',
        EventSocialMediaCard.as_view(),
        name='event-social',
    ),
    path(
        'online-video/join/',
        talk.OnlineVideoJoin.as_view(),
        name='event.onlinevideo.join',
    ),
    path(
        'sw.js',
        get_static,
        {
            'path': 'agenda/js/serviceworker.js',
            'content_type': 'application/javascript',
        },
    ),
]
