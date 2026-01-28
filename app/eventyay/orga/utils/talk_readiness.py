from django.utils.translation import gettext_lazy as _


def get_talk_readiness(event):
    warnings = []
    suggestions = []
    if not event.cfp.text or len(str(event.cfp.text)) < 50:
        warnings.append(
            {
                'text': _('The CfP doesn’t have a full text yet.'),
                'url': event.cfp.urls.text,
            }
        )
    if (
        event.get_feature_flag('use_tracks')
        and event.cfp.request_track
        and event.tracks.count() < 2
    ):
        suggestions.append(
            {
                'text': _(
                    'You want submitters to choose the tracks for their proposals, but you do not offer tracks for selection. Add at least one track!'
                ),
                'url': event.cfp.urls.tracks,
            }
        )
    if event.submission_types.count() == 1:
        suggestions.append(
            {
                'text': _('You have configured only one session type so far.'),
                'url': event.cfp.urls.types,
            }
        )
    if not event.talkquestions.exists():
        suggestions.append(
            {
                'text': _('You have configured no custom fields yet.'),
                'url': event.cfp.urls.new_question,
            }
        )
    return warnings, suggestions
