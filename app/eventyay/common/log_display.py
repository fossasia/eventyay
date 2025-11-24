import string

from django.dispatch import receiver
from django.utils.html import escape
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy as _n

from eventyay.base.models import (
    ActivityLog,
    Answer,
    AnswerOption,
    CfP,
    Event,
    MailTemplate,
    LogEntry,
    QueuedMail,
    Review,
    SpeakerProfile,
    Submission,
    SubmissionComment,
    SubmissionStates,
    TalkQuestion,
)
from eventyay.base.signals import activitylog_display, activitylog_object_link
from eventyay.common.text.phrases import phrases

# Usually, we don't have to include the object name in activity log
# strings, because we use ActivityLog.content_object to get the object
# and display it above the message. However, in some cases, like when
# we log the deletion of an object, we don't have the object anymore,
# so we'll want to format the message instead.
TEMPLATE_LOG_NAMES = {
    'eventyay.event.delete': _('The event {name} ({slug}) by {organiser} was deleted.'),
    'eventyay.organiser.delete': _('The organiser {name} was deleted.'),
    # Legacy pretalx prefixes (for backward compatibility with historic data)
    'pretalx.event.delete': _('The event {name} ({slug}) by {organiser} was deleted.'),
    'pretalx.organiser.delete': _('The organiser {name} was deleted.'),
}

# These log names were used in the past, and we still support them for display purposes
# Map old pretalx prefixes to new eventyay prefixes
LOG_ALIASES = {
    # Old event-level aliases
    'pretalx.event.invite.orga.accept': 'eventyay.invite.orga.accept',
    'pretalx.event.invite.orga.retract': 'eventyay.invite.orga.retract',
    'pretalx.event.invite.orga.send': 'eventyay.invite.orga.send',
    'pretalx.event.invite.reviewer.retract': 'eventyay.invite.reviewer.retract',
    'pretalx.event.invite.reviewer.send': 'eventyay.invite.reviewer.send',
    # Old submission aliases
    'pretalx.submission.confirmation': 'eventyay.submission.confirm',
    'pretalx.submission.answerupdate': 'eventyay.submission.answer.update',
    'pretalx.submission.answercreate': 'eventyay.submission.answer.create',
    'pretalx.submission.make_submitted': 'eventyay.submission.create',
    # Map all old pretalx.* prefixes to new eventyay.* prefixes
    'pretalx.cfp.update': 'eventyay.cfp.update',
    'pretalx.event.create': 'eventyay.event.create',
    'pretalx.event.update': 'eventyay.event.update',
    'pretalx.event.activate': 'eventyay.event.activate',
    'pretalx.event.deactivate': 'eventyay.event.deactivate',
    'pretalx.event.plugins.enabled': 'eventyay.event.plugins.enabled',
    'pretalx.event.plugins.disabled': 'eventyay.event.plugins.disabled',
    'pretalx.invite.orga.accept': 'eventyay.invite.orga.accept',
    'pretalx.invite.orga.retract': 'eventyay.invite.orga.retract',
    'pretalx.invite.orga.send': 'eventyay.invite.orga.send',
    'pretalx.invite.reviewer.retract': 'eventyay.invite.reviewer.retract',
    'pretalx.invite.reviewer.send': 'eventyay.invite.reviewer.send',
    'pretalx.team.member.remove': 'eventyay.team.member.remove',
    'pretalx.mail.create': 'eventyay.mail.create',
    'pretalx.mail.delete': 'eventyay.mail.delete',
    'pretalx.mail.delete_all': 'eventyay.mail.delete_all',
    'pretalx.mail.sent': 'eventyay.mail.sent',
    'pretalx.mail.update': 'eventyay.mail.update',
    'pretalx.mail_template.create': 'eventyay.mail_template.create',
    'pretalx.mail_template.delete': 'eventyay.mail_template.delete',
    'pretalx.mail_template.update': 'eventyay.mail_template.update',
    'pretalx.question.create': 'eventyay.question.create',
    'pretalx.question.delete': 'eventyay.question.delete',
    'pretalx.question.update': 'eventyay.question.update',
    'pretalx.question.option.create': 'eventyay.question.option.create',
    'pretalx.question.option.delete': 'eventyay.question.option.delete',
    'pretalx.question.option.update': 'eventyay.question.option.update',
    'pretalx.tag.create': 'eventyay.tag.create',
    'pretalx.tag.delete': 'eventyay.tag.delete',
    'pretalx.tag.update': 'eventyay.tag.update',
    'pretalx.room.create': 'eventyay.room.create',
    'pretalx.room.update': 'eventyay.room.update',
    'pretalx.room.delete': 'eventyay.room.delete',
    'pretalx.schedule.release': 'eventyay.schedule.release',
    'pretalx.submission.accept': 'eventyay.submission.accept',
    'pretalx.submission.cancel': 'eventyay.submission.cancel',
    'pretalx.submission.confirm': 'eventyay.submission.confirm',
    'pretalx.submission.create': 'eventyay.submission.create',
    'pretalx.submission.deleted': 'eventyay.submission.deleted',
    'pretalx.submission.reject': 'eventyay.submission.reject',
    'pretalx.submission.resource.create': 'eventyay.submission.resource.create',
    'pretalx.submission.resource.delete': 'eventyay.submission.resource.delete',
    'pretalx.submission.resource.update': 'eventyay.submission.resource.update',
    'pretalx.submission.review.delete': 'eventyay.submission.review.delete',
    'pretalx.submission.review.update': 'eventyay.submission.review.update',
    'pretalx.submission.review.create': 'eventyay.submission.review.create',
    'pretalx.submission.speakers.add': 'eventyay.submission.speakers.add',
    'pretalx.submission.speakers.invite': 'eventyay.submission.speakers.invite',
    'pretalx.submission.speakers.remove': 'eventyay.submission.speakers.remove',
    'pretalx.submission.unconfirm': 'eventyay.submission.unconfirm',
    'pretalx.submission.update': 'eventyay.submission.update',
    'pretalx.submission.withdraw': 'eventyay.submission.withdraw',
    'pretalx.submission.answer.update': 'eventyay.submission.answer.update',
    'pretalx.submission.answer.create': 'eventyay.submission.answer.create',
    'pretalx.submission.comment.create': 'eventyay.submission.comment.create',
    'pretalx.submission.comment.delete': 'eventyay.submission.comment.delete',
    'pretalx.submission_type.create': 'eventyay.submission_type.create',
    'pretalx.submission_type.delete': 'eventyay.submission_type.delete',
    'pretalx.submission_type.make_default': 'eventyay.submission_type.make_default',
    'pretalx.submission_type.update': 'eventyay.submission_type.update',
    'pretalx.access_code.create': 'eventyay.access_code.create',
    'pretalx.access_code.send': 'eventyay.access_code.send',
    'pretalx.access_code.update': 'eventyay.access_code.update',
    'pretalx.access_code.delete': 'eventyay.access_code.delete',
    'pretalx.track.create': 'eventyay.track.create',
    'pretalx.track.delete': 'eventyay.track.delete',
    'pretalx.track.update': 'eventyay.track.update',
    'pretalx.speaker.arrived': 'eventyay.speaker.arrived',
    'pretalx.speaker.unarrived': 'eventyay.speaker.unarrived',
    'pretalx.speaker_information.create': 'eventyay.speaker_information.create',
    'pretalx.speaker_information.update': 'eventyay.speaker_information.update',
    'pretalx.speaker_information.delete': 'eventyay.speaker_information.delete',
    'pretalx.user.token.reset': 'eventyay.user.token.reset',
    'pretalx.user.token.revoke': 'eventyay.user.token.revoke',
    'pretalx.user.token.upgrade': 'eventyay.user.token.upgrade',
    'pretalx.user.password.reset': 'eventyay.user.password.reset',
    'pretalx.user.password.update': 'eventyay.user.password.update',
    'pretalx.user.profile.update': 'eventyay.user.profile.update',
}

LOG_NAMES = {
    # Primary eventyay prefixes (used for new logs)
    'eventyay.cfp.update': _('The CfP has been modified.'),
    'eventyay.event.create': _('The event has been added.'),
    'eventyay.event.update': _('The event was modified.'),
    'eventyay.event.activate': _('The event was made public.'),
    'eventyay.event.deactivate': _('The event was deactivated.'),
    'eventyay.event.plugins.enabled': _('A plugin was enabled.'),
    'eventyay.event.plugins.disabled': _('A plugin was disabled.'),
    'eventyay.invite.orga.accept': _('The invitation to the event orga was accepted.'),
    'eventyay.invite.orga.retract': _('An invitation to the event orga was retracted.'),
    'eventyay.invite.orga.send': _('An invitation to the event orga was sent.'),
    'eventyay.invite.reviewer.retract': _('The invitation to the review team was retracted.'),
    'eventyay.invite.reviewer.send': _('The invitation to the review team was sent.'),
    'eventyay.team.member.remove': _('A team member was removed'),
    'eventyay.mail.create': _('An email was created.'),
    'eventyay.mail.delete': _('A pending email was deleted.'),
    'eventyay.mail.delete_all': _('All pending emails were deleted.'),
    'eventyay.mail.sent': _('An email was sent.'),
    'eventyay.mail.update': _('An email was modified.'),
    'eventyay.mail_template.create': _('A mail template was added.'),
    'eventyay.mail_template.delete': _('A mail template was deleted.'),
    'eventyay.mail_template.update': _('A mail template was modified.'),
    'eventyay.question.create': _('A custom field was added.'),
    'eventyay.question.delete': _('A custom field was deleted.'),
    'eventyay.question.update': _('A custom field was modified.'),
    'eventyay.question.option.create': _('A custom field option was added.'),
    'eventyay.question.option.delete': _('A custom field option was deleted.'),
    'eventyay.question.option.update': _('A custom field option was modified.'),
    'eventyay.tag.create': _('A tag was added.'),
    'eventyay.tag.delete': _('A tag was deleted.'),
    'eventyay.tag.update': _('A tag was modified.'),
    'eventyay.room.create': _('A new room was added.'),
    'eventyay.room.update': _('A room was modified.'),
    'eventyay.room.delete': _('A room was deleted.'),
    'eventyay.schedule.release': _('A new schedule version was released.'),
    'eventyay.submission.accept': _('The proposal was accepted.'),
    'eventyay.submission.cancel': _('The proposal was cancelled.'),
    'eventyay.submission.confirm': _('The proposal was confirmed.'),
    'eventyay.submission.create': _('The proposal was added.'),
    'eventyay.submission.deleted': _('The proposal was deleted.'),
    'eventyay.submission.reject': _('The proposal was rejected.'),
    'eventyay.submission.resource.create': _('A proposal resource was added.'),
    'eventyay.submission.resource.delete': _('A proposal resource was deleted.'),
    'eventyay.submission.resource.update': _('A proposal resource was modified.'),
    'eventyay.submission.review.delete': _('A review was deleted.'),
    'eventyay.submission.review.update': _('A review was modified.'),
    'eventyay.submission.review.create': _('A review was added.'),
    'eventyay.submission.speakers.add': _('A speaker was added to the proposal.'),
    'eventyay.submission.speakers.invite': _('A speaker was invited to the proposal.'),
    'eventyay.submission.speakers.remove': _('A speaker was removed from the proposal.'),
    'eventyay.submission.unconfirm': _('The proposal was unconfirmed.'),
    'eventyay.submission.update': _('The proposal was modified.'),
    'eventyay.submission.withdraw': _('The proposal was withdrawn.'),
    'eventyay.submission.answer.update': _('A custom field response was modified.'),
    'eventyay.submission.answer.create': _('A custom field response was added.'),
    'eventyay.submission.comment.create': _('A proposal comment was added.'),
    'eventyay.submission.comment.delete': _('A proposal comment was deleted.'),
    'eventyay.submission_type.create': _('A session type was added.'),
    'eventyay.submission_type.delete': _('A session type was deleted.'),
    'eventyay.submission_type.make_default': _('The session type was made default.'),
    'eventyay.submission_type.update': _('A session type was modified.'),
    'eventyay.access_code.create': _('An access code was added.'),
    'eventyay.access_code.send': _('An access code was sent.'),
    'eventyay.access_code.update': _('An access code was modified.'),
    'eventyay.access_code.delete': _('An access code was deleted.'),
    'eventyay.track.create': _('A track was added.'),
    'eventyay.track.delete': _('A track was deleted.'),
    'eventyay.track.update': _('A track was modified.'),
    'eventyay.speaker.arrived': _('A speaker has been marked as arrived.'),
    'eventyay.speaker.unarrived': _('A speaker has been marked as not arrived.'),
    'eventyay.speaker_information.create': _('A speaker information note was added.'),
    'eventyay.speaker_information.update': _('A speaker information note was modified.'),
    'eventyay.speaker_information.delete': _('A speaker information note was deleted.'),
    'eventyay.user.token.reset': _('The API token was reset.'),
    'eventyay.user.token.revoke': _('The API token was revoked.'),
    'eventyay.user.token.upgrade': _('The API token was upgraded to the latest version.'),
    'eventyay.user.password.reset': phrases.base.password_reset_success,
    'eventyay.user.password.update': _('The password was modified.'),
    'eventyay.user.profile.update': _('The profile was modified.'),
}


@receiver(activitylog_display)
def default_activitylog_display(sender: Event, activitylog: LogEntry, **kwargs):
    if templated_entry := TEMPLATE_LOG_NAMES.get(activitylog.action_type):
        message = str(templated_entry)
        # Check if all placeholders are present in activitylog.data
        placeholders = {v[1] for v in string.Formatter().parse(message) if v[1]}
        if placeholders <= set(activitylog.json_data.keys()):
            return message.format(**activitylog.json_data)
    action_type = LOG_ALIASES.get(activitylog.action_type, activitylog.action_type)
    return LOG_NAMES.get(action_type)


def _submission_label_text(submission: Submission) -> str:
    if submission.state in (
        SubmissionStates.ACCEPTED,
        SubmissionStates.CONFIRMED,
    ):
        return _n('Session', 'Sessions', 1)
    else:
        return _n('Proposal', 'Proposals', 1)


@receiver(activitylog_object_link)
def default_activitylog_object_link(sender: Event, activitylog: LogEntry, **kwargs):
    if not activitylog.content_object:
        return
    url = ''
    text = ''
    link_text = ''
    if isinstance(activitylog.content_object, Submission):
        url = activitylog.content_object.orga_urls.base
        link_text = escape(activitylog.content_object.title)
        text = _submission_label_text(activitylog.content_object)
    elif isinstance(activitylog.content_object, SubmissionComment):
        url = activitylog.content_object.submission.orga_urls.comments + f'#comment-{activitylog.content_object.pk}'
        link_text = escape(activitylog.content_object.submission.title)
        text = _submission_label_text(activitylog.content_object.submission)
    elif isinstance(activitylog.content_object, Review):
        url = activitylog.content_object.submission.orga_urls.reviews
        link_text = escape(activitylog.content_object.submission.title)
        text = _submission_label_text(activitylog.content_object.submission)
    elif isinstance(activitylog.content_object, TalkQuestion):
        url = activitylog.content_object.urls.base
        link_text = escape(activitylog.content_object.question)
        text = _('Custom field')
    elif isinstance(activitylog.content_object, AnswerOption):
        url = activitylog.content_object.question.urls.base
        link_text = escape(activitylog.content_object.question.question)
        text = _('Custom field')
    elif isinstance(activitylog.content_object, Answer):
        if activitylog.content_object.submission:
            url = activitylog.content_object.submission.orga_urls.base
        else:
            url = activitylog.content_object.question.urls.base
        link_text = escape(activitylog.content_object.question.question)
        text = _('Response to custom field')
    elif isinstance(activitylog.content_object, CfP):
        url = activitylog.content_object.urls.text
        link_text = _('Call for Proposals')
    elif isinstance(activitylog.content_object, MailTemplate):
        url = activitylog.content_object.urls.base
        text = _('Mail template')
        link_text = escape(activitylog.content_object.subject)
    elif isinstance(activitylog.content_object, QueuedMail):
        url = activitylog.content_object.urls.base
        text = _('Email')
        link_text = escape(activitylog.content_object.subject)
    elif isinstance(activitylog.content_object, SpeakerProfile):
        url = activitylog.content_object.orga_urls.base
        text = _('Speaker profile')
        link_text = escape(activitylog.content_object.user.get_display_name())
    elif isinstance(activitylog.content_object, Event):
        url = activitylog.content_object.orga_urls.base
        text = _('Event')
        link_text = escape(activitylog.content_object.name)
    if url:
        if not link_text:
            link_text = url
        return f'{text} <a href="{url}">{link_text}</a>'
    if text or link_text:
        return f'{text} {link_text}'
