import logging
from collections.abc import Sequence
from datetime import timedelta
from typing import TypedDict
from urllib.parse import urlencode

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

# If a worker dies after claiming SENDING, allow another send to reclaim it.
SENDING_STALE_AFTER = timedelta(minutes=15)


class SendResult(TypedDict):
    sent: int
    resent: int
    skipped_claimed: int
    skipped_no_email: int
    skipped_ineligible: int
    skipped_unusable: int
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
    return f'{redeem_base}?{urlencode({"voucher": code})}'


def _has_email(profile: SpeakerProfile) -> bool:
    user = profile.user
    return bool(user and (user.email or '').strip())


def assignment_needs_replacement(assignment: SpeakerVoucher) -> bool:
    """True when the linked ticket voucher can no longer be emailed/redeemed."""
    voucher = assignment.voucher
    return voucher.valid_until is not None and voucher.valid_until < now()


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
        .filter(
            Q(voucher_assignment__isnull=True)
            | Q(voucher_assignment__status=SpeakerVoucherStatus.NOT_SENT)
        )
        .exclude(user__email='')
        .filter(user__email__isnull=False)
        .select_related('voucher_assignment', 'voucher_assignment__voucher')
    )


def speaker_summary_counts(event: Event, settings: SpeakerVoucherSettings) -> SpeakerSummaryCounts:
    with scope(event=event):
        eligible_ids = set(eligible_speaker_profiles(event).values_list('pk', flat=True))
        assigned = SpeakerVoucher.objects.filter(event=event, speaker_profile_id__in=eligible_ids)
        sent = assigned.exclude(
            status__in=(SpeakerVoucherStatus.NOT_SENT, SpeakerVoucherStatus.SENDING)
        ).count()
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
    mail = None
    try:
        mail = template.to_mail(
            user,
            event=event,
            locale=locale,
            context=context,
            context_kwargs={'event': event, 'user': user},
            skip_queue=False,
            commit=True,
        )
        mail.send(requestor=requestor, synchronous=True)
        return mail
    except SendMailException:
        logger.exception('Failed to send speaker voucher email to user %s', user.pk)
        if mail is not None and mail.pk and mail.sent is None:
            # Drop the unsent outbox row so a retry does not leave a duplicate/stale mail.
            mail.delete()
        return None


def _recover_stale_sending_assignments(event: Event) -> None:
    """Reclaim assignments left in ``sending`` after a crashed worker."""
    SpeakerVoucher.objects.filter(
        event=event,
        status=SpeakerVoucherStatus.SENDING,
        updated__lt=now() - SENDING_STALE_AFTER,
    ).update(status=SpeakerVoucherStatus.NOT_SENT, sent_at=None)


def _claim_assignment_for_send(assignment: SpeakerVoucher) -> tuple[SpeakerVoucher, bool] | None:
    """Atomically claim an assignment for delivery.

    Returns ``(locked_assignment, was_already_sent)`` or ``None`` when another
    request already owns delivery for this row.
    """
    with transaction.atomic():
        locked = (
            SpeakerVoucher.objects.select_for_update(skip_locked=True)
            .select_related('voucher', 'speaker_profile', 'speaker_profile__user')
            .filter(pk=assignment.pk)
            .first()
        )
        if locked is None:
            return None

        locked.refresh_claimed_status()
        if locked.status == SpeakerVoucherStatus.CLAIMED or locked.voucher.redeemed > 0:
            return None
        if locked.status == SpeakerVoucherStatus.SENDING:
            return None

        was_already_sent = locked.status == SpeakerVoucherStatus.SENT
        if locked.status not in (SpeakerVoucherStatus.NOT_SENT, SpeakerVoucherStatus.SENT):
            return None

        locked.status = SpeakerVoucherStatus.SENDING
        locked.save(update_fields=['status'])
        return locked, was_already_sent


def _release_send_claim(assignment: SpeakerVoucher, *, restore_status: str, sent_at=None) -> None:
    SpeakerVoucher.objects.filter(pk=assignment.pk, status=SpeakerVoucherStatus.SENDING).update(
        status=restore_status,
        sent_at=sent_at,
    )


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
    - Assignment ``not_sent`` with a usable code → retry email with the same code
    - Sent — not claimed with a usable code → resend the same code
    - Assignment whose code expired or was cancelled → replace with a new code, then send
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
        'skipped_unusable': 0,
        'aborted_insufficient': False,
        'needed': 0,
        'available': 0,
    }

    if not settings.enabled or not settings.voucher_tag:
        return result

    profile_ids = [p.pk for p in profiles]
    with scope(event=event):
        _recover_stale_sending_assignments(event)
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
    needs_replacement: list[tuple[SpeakerProfile, SpeakerVoucher]] = []
    for profile in profiles:
        if not _has_email(profile):
            result['skipped_no_email'] += 1
            continue
        if profile.pk not in eligible_ids:
            result['skipped_ineligible'] += 1
            continue

        existing = existing_map.get(profile.pk)
        if existing is None:
            new_recipients.append(profile)
            continue

        existing.refresh_claimed_status()
        if existing.status == SpeakerVoucherStatus.CLAIMED or existing.voucher.redeemed > 0:
            result['skipped_claimed'] += 1
            continue
        if existing.status == SpeakerVoucherStatus.SENDING:
            # Another request owns delivery for this assignment.
            continue
        # Expired/cancelled codes cannot be emailed; claim a replacement below.
        # Active cart reservations do not block the assigned speaker from receiving their code.
        if assignment_needs_replacement(existing):
            needs_replacement.append((profile, existing))
            continue
        retry_or_resend.append((profile, existing))

    result['needed'] = len(new_recipients) + len(needs_replacement)
    result['available'] = settings.batch_remaining_count()

    if not allow_partial and result['needed'] > result['available']:
        result['aborted_insufficient'] = True
        return result

    newly_allocated: list[tuple[SpeakerProfile, SpeakerVoucher]] = []
    if new_recipients or needs_replacement:
        try:
            with scope(event=event), transaction.atomic():
                for profile in new_recipients:
                    if SpeakerVoucher.objects.filter(speaker_profile=profile).exists():
                        existing = SpeakerVoucher.objects.select_related('voucher').get(
                            speaker_profile=profile
                        )
                        if existing.status == SpeakerVoucherStatus.CLAIMED or existing.voucher.redeemed > 0:
                            continue
                        if existing.status == SpeakerVoucherStatus.SENDING:
                            continue
                        if assignment_needs_replacement(existing):
                            needs_replacement.append((profile, existing))
                        else:
                            retry_or_resend.append((profile, existing))
                        continue
                    voucher = _claim_next_voucher(settings)
                    if voucher is None:
                        if not allow_partial:
                            raise _InsufficientVouchers()
                        break
                    try:
                        # Nested atomic() creates a savepoint so IntegrityError does not
                        # abort the outer allocation transaction on PostgreSQL.
                        with transaction.atomic():
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
                        if (
                            existing
                            and existing.status
                            not in (SpeakerVoucherStatus.CLAIMED, SpeakerVoucherStatus.SENDING)
                        ):
                            if assignment_needs_replacement(existing):
                                needs_replacement.append((profile, existing))
                            else:
                                retry_or_resend.append((profile, existing))
                        continue
                    newly_allocated.append((profile, speaker_voucher))

                for profile, assignment in list(needs_replacement):
                    voucher = _claim_next_voucher(settings)
                    if voucher is None:
                        if not allow_partial:
                            raise _InsufficientVouchers()
                        result['skipped_unusable'] += 1
                        continue
                    assignment.voucher = voucher
                    assignment.status = SpeakerVoucherStatus.NOT_SENT
                    assignment.sent_at = None
                    assignment.save(update_fields=['voucher', 'status', 'sent_at'])
                    newly_allocated.append((profile, assignment))
        except _InsufficientVouchers:
            result['aborted_insufficient'] = True
            result['available'] = settings.batch_remaining_count()
            return result

    for profile, assignment in newly_allocated + retry_or_resend:
        claimed = _claim_assignment_for_send(assignment)
        if claimed is None:
            continue
        locked, was_already_sent = claimed
        previous_sent_at = locked.sent_at
        restore_status = (
            SpeakerVoucherStatus.SENT if was_already_sent else SpeakerVoucherStatus.NOT_SENT
        )
        mail = _send_voucher_email(event, profile, locked.voucher, requestor=requestor)
        if mail is None:
            _release_send_claim(
                locked,
                restore_status=restore_status,
                sent_at=previous_sent_at if was_already_sent else None,
            )
            continue
        locked.status = SpeakerVoucherStatus.SENT
        locked.sent_at = now()
        locked.save(update_fields=['status', 'sent_at'])
        action = (
            'eventyay.speaker.voucher.resent'
            if was_already_sent
            else 'eventyay.speaker.voucher.sent'
        )
        locked.log_action(
            action,
            person=requestor,
            orga=True,
            data={
                'voucher_code': locked.voucher.code,
                'speaker_user_id': profile.user.pk if profile.user else None,
            },
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
    speaker_user = (
        speaker_voucher.speaker_profile.user
        if speaker_voucher.speaker_profile
        else None
    )
    speaker_voucher.log_action(
        'eventyay.speaker.voucher.cancelled',
        person=requestor,
        orga=True,
        data={
            'voucher_code': voucher.code,
            'speaker_user_id': speaker_user.pk if speaker_user else None,
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
        if assignment.status in (SpeakerVoucherStatus.NOT_SENT, SpeakerVoucherStatus.SENDING):
            return 'not_sent' if confirmed_count else 'withdrawn'
        if confirmed_count:
            return 'sent'
        return 'withdrawn'

    if confirmed_count:
        return 'not_sent'
    return 'dash'
