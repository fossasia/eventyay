import logging
from collections.abc import Sequence
from typing import TypedDict

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Event, QueuedMail, SpeakerProfile, SubmissionStates, Voucher
from eventyay.base.models.mail import MailTemplateRoles
from eventyay.base.models.speaker_voucher import (
    SpeakerVoucher,
    SpeakerVoucherSettings,
    SpeakerVoucherStatus,
    usable_batch_vouchers,
)
from eventyay.common.exceptions import SendMailException
from eventyay.multidomain.urlreverse import build_absolute_uri

logger = logging.getLogger(__name__)


class SendResult(TypedDict):
    sent: int
    resent: int
    skipped_claimed: int
    skipped_no_email: int
    skipped_ineligible: int
    aborted_insufficient: bool
    needed: int
    available: int


class SpeakerSummaryCounts(TypedDict):
    sent: int
    claimed: int
    eligible_not_sent: int
    eligible: int
    remaining: int
    total: int


def voucher_redeem_url(event: Event, code: str) -> str:
    redeem_base = build_absolute_uri(event, 'presale:event.redeem')
    return f'{redeem_base}?voucher={code}'


def _has_email(profile: SpeakerProfile) -> bool:
    user = profile.user
    return bool(user and (user.email or '').strip())


def eligible_speaker_profiles(event: Event):
    """Speakers with at least one confirmed session for this event."""
    return (
        SpeakerProfile.objects.filter(event=event)
        .filter(
            user__submissions__event=event,
            user__submissions__state=SubmissionStates.CONFIRMED,
        )
        .select_related('user')
        .distinct()
    )


def profiles_needing_voucher(event: Event):
    """Eligible speakers who still need a first send or a retry of a failed send.

    Includes profiles with no assignment and profiles whose assignment is still
    ``not_sent`` (email failed after allocation). Excludes speakers without email.
    """
    return (
        eligible_speaker_profiles(event)
        .filter(Q(voucher_assignment__isnull=True) | Q(voucher_assignment__status=SpeakerVoucherStatus.NOT_SENT))
        .exclude(user__email='')
        .filter(user__email__isnull=False)
    )


def speaker_summary_counts(event: Event, settings: SpeakerVoucherSettings) -> SpeakerSummaryCounts:
    with scope(event=event):
        eligible_ids = set(eligible_speaker_profiles(event).values_list('pk', flat=True))
        assigned = SpeakerVoucher.objects.filter(event=event, speaker_profile_id__in=eligible_ids)
        sent = assigned.exclude(status=SpeakerVoucherStatus.NOT_SENT).count()
        claimed = assigned.filter(
            Q(status=SpeakerVoucherStatus.CLAIMED) | Q(voucher__redeemed__gt=0)
        ).distinct().count()
        # Count speakers who still need a successful send (no assignment or not_sent).
        needing = profiles_needing_voucher(event).count()
    return {
        'sent': sent,
        'claimed': claimed,
        'eligible_not_sent': needing,
        'eligible': len(eligible_ids),
        'remaining': settings.batch_remaining_count() if settings.voucher_tag else 0,
        'total': settings.batch_total_count() if settings.voucher_tag else 0,
    }


def _claim_next_voucher(settings: SpeakerVoucherSettings) -> Voucher | None:
    """Pick and lock one unused voucher from the batch.

    Must be called inside a transaction.atomic() block so the row lock
    is held until the caller creates the SpeakerVoucher assignment.
    """
    with scopes_disabled():
        return (
            usable_batch_vouchers(settings.event, settings.voucher_tag)
            .order_by('pk')
            .select_for_update(skip_locked=True, of=('self',))
            .first()
        )


def _send_voucher_email(
    event: Event, profile: SpeakerProfile, voucher: Voucher, requestor=None
) -> QueuedMail | None:
    user = profile.user
    if not user or not user.email:
        return None

    template = event.get_mail_template(MailTemplateRoles.SPEAKER_VOUCHER)
    locale = user.locale or event.locale
    context = {
        'voucher_code': voucher.code,
        'voucher_url': voucher_redeem_url(event, voucher.code),
    }
    try:
        return template.to_mail(
            user,
            event=event,
            locale=locale,
            context=context,
            context_kwargs={'event': event, 'user': user},
            skip_queue=True,
            commit=True,
        )
    except SendMailException:
        logger.exception('Failed to send speaker voucher email to user %s', user.pk)
        return None


def allocate_and_send_vouchers(
    event: Event,
    settings: SpeakerVoucherSettings,
    profiles: Sequence[SpeakerProfile],
    *,
    requestor=None,
    allow_partial: bool = False,
) -> SendResult:
    """Allocate voucher codes and send emails for selected speaker profiles.

    Behaviour per speaker:
    - No assignment → pick an unused voucher, create assignment, send email
    - Assignment ``not_sent`` → retry email with the same code (no new voucher)
    - Sent — not claimed → resend the same code
    - Claimed → skip
    - No email / not eligible → skip

    When ``allow_partial`` is False (default), all new vouchers are claimed in one
    transaction before any email is sent. If the batch cannot cover every new
    recipient, the transaction rolls back and nothing is sent.
    """
    result: SendResult = {
        'sent': 0,
        'resent': 0,
        'skipped_claimed': 0,
        'skipped_no_email': 0,
        'skipped_ineligible': 0,
        'aborted_insufficient': False,
        'needed': 0,
        'available': 0,
    }

    if not settings.enabled or not settings.voucher_tag:
        return result

    profile_ids = [p.pk for p in profiles]
    with scope(event=event):
        eligible_ids = set(
            eligible_speaker_profiles(event).filter(pk__in=profile_ids).values_list('pk', flat=True)
        )
        existing_map: dict[int, SpeakerVoucher] = {
            sv.speaker_profile_id: sv
            for sv in SpeakerVoucher.objects.filter(speaker_profile_id__in=profile_ids).select_related(
                'voucher', 'speaker_profile', 'speaker_profile__user'
            )
            if sv.speaker_profile_id is not None
        }

    new_recipients: list[SpeakerProfile] = []
    retry_or_resend: list[tuple[SpeakerProfile, SpeakerVoucher]] = []
    for profile in profiles:
        if not _has_email(profile):
            result['skipped_no_email'] += 1
            continue

        existing = existing_map.get(profile.pk)
        if existing is None:
            if profile.pk not in eligible_ids:
                result['skipped_ineligible'] += 1
                continue
            new_recipients.append(profile)
            continue

        existing.refresh_claimed_status()
        if existing.status == SpeakerVoucherStatus.CLAIMED or existing.voucher.redeemed > 0:
            result['skipped_claimed'] += 1
            continue
        retry_or_resend.append((profile, existing))

    result['needed'] = len(new_recipients)
    result['available'] = settings.batch_remaining_count()

    if not allow_partial and result['needed'] > result['available']:
        result['aborted_insufficient'] = True
        return result

    newly_allocated: list[tuple[SpeakerProfile, SpeakerVoucher]] = []
    if new_recipients:
        try:
            with scope(event=event), transaction.atomic():
                for profile in new_recipients:
                    if SpeakerVoucher.objects.filter(speaker_profile=profile).exists():
                        existing = SpeakerVoucher.objects.select_related('voucher').get(
                            speaker_profile=profile
                        )
                        if existing.status != SpeakerVoucherStatus.CLAIMED:
                            retry_or_resend.append((profile, existing))
                        continue
                    voucher = _claim_next_voucher(settings)
                    if voucher is None:
                        if not allow_partial:
                            raise _InsufficientVouchers()
                        break
                    try:
                        speaker_voucher = SpeakerVoucher.objects.create(
                            event=event,
                            speaker_profile=profile,
                            voucher=voucher,
                            status=SpeakerVoucherStatus.NOT_SENT,
                            sent_at=None,
                        )
                    except IntegrityError:
                        # Concurrent request won the race for this speaker or voucher.
                        existing = (
                            SpeakerVoucher.objects.filter(speaker_profile=profile)
                            .select_related('voucher')
                            .first()
                        )
                        if existing and existing.status != SpeakerVoucherStatus.CLAIMED:
                            retry_or_resend.append((profile, existing))
                        continue
                    newly_allocated.append((profile, speaker_voucher))
        except _InsufficientVouchers:
            result['aborted_insufficient'] = True
            result['available'] = settings.batch_remaining_count()
            return result

    for profile, assignment in newly_allocated + retry_or_resend:
        was_already_sent = assignment.status == SpeakerVoucherStatus.SENT
        mail = _send_voucher_email(event, profile, assignment.voucher, requestor=requestor)
        if mail is None:
            continue
        assignment.status = SpeakerVoucherStatus.SENT
        assignment.sent_at = now()
        assignment.save(update_fields=['status', 'sent_at'])
        action = (
            'eventyay.speaker.voucher.resent'
            if was_already_sent
            else 'eventyay.speaker.voucher.sent'
        )
        assignment.log_action(
            action,
            person=requestor,
            orga=True,
            data={'voucher_code': assignment.voucher.code, 'speaker': profile.user.email},
        )
        if was_already_sent:
            result['resent'] += 1
        else:
            result['sent'] += 1

    return result


class _InsufficientVouchers(Exception):
    """Internal signal to roll back a partial voucher allocation transaction."""


def cancel_speaker_voucher(speaker_voucher: SpeakerVoucher, *, requestor=None) -> None:
    """Expire the linked voucher so it cannot be redeemed; keep the assignment for audit."""
    voucher = speaker_voucher.voucher
    voucher.valid_until = now()
    voucher.save(update_fields=['valid_until'])
    speaker_voucher.log_action(
        'eventyay.speaker.voucher.cancelled',
        person=requestor,
        orga=True,
        data={
            'voucher_code': voucher.code,
            'speaker': (
                speaker_voucher.speaker_profile.user.email
                if speaker_voucher.speaker_profile and speaker_voucher.speaker_profile.user
                else None
            ),
        },
    )


def speaker_voucher_row_state(profile: SpeakerProfile) -> str:
    """Return the Speakers-list voucher display state for a profile.

    One of: ``dash``, ``not_sent``, ``sent``, ``claimed``, ``withdrawn``.
    """
    try:
        assignment = profile.voucher_assignment
    except SpeakerVoucher.DoesNotExist:
        assignment = None
    confirmed_count = getattr(profile, 'confirmed_submission_count', None)
    if confirmed_count is None:
        confirmed_count = profile.user.submissions.filter(
            event=profile.event, state=SubmissionStates.CONFIRMED
        ).count()

    if assignment is not None:
        assignment.refresh_claimed_status()
        if assignment.status == SpeakerVoucherStatus.CLAIMED or assignment.voucher.redeemed > 0:
            return 'claimed'
        if confirmed_count:
            return 'sent'
        return 'withdrawn'

    if confirmed_count:
        return 'not_sent'
    return 'dash'
