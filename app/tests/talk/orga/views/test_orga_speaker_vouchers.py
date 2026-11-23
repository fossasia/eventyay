from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from django.utils.timezone import now
from django_scopes import scope, scopes_disabled

from eventyay.base.models import CartPosition, Product, QueuedMail, SpeakerProfile, Voucher
from eventyay.base.models.mail import MailTemplateRoles
from eventyay.base.models.speaker_voucher import (
    SpeakerVoucher,
    SpeakerVoucherSettings,
    SpeakerVoucherStatus,
    usable_batch_vouchers,
)
from eventyay.base.models.submission import SubmissionStates
from eventyay.base.services.speaker_vouchers import (
    allocate_and_send_vouchers,
    eligible_speaker_profiles,
    profiles_needing_voucher,
    send_speaker_vouchers_task,
    speaker_voucher_row_state,
    voucher_redeem_url,
)
from eventyay.common.exceptions import SendMailException


@pytest.fixture
def speaker_voucher_batch(event):
    with scope(event=event):
        vouchers = [
            Voucher.objects.create(
                event=event,
                code=f'SPK{i:03d}',
                tag='speakers',
                max_usages=1,
                price_mode='set',
                value=Decimal('0.00'),
            )
            for i in range(3)
        ]
    return vouchers


@pytest.fixture
def speaker_voucher_settings(event, speaker_voucher_batch):
    with scope(event=event):
        return SpeakerVoucherSettings.objects.create(
            event=event,
            enabled=True,
            voucher_tag='speakers',
        )


@pytest.mark.django_db
def test_eligible_speakers_require_confirmed_session(
    event, speaker, submission, confirmed_submission, other_speaker, other_submission
):
    with scope(event=event):
        SpeakerProfile.objects.get_or_create(event=event, user=other_speaker)
        profiles = list(eligible_speaker_profiles(event))
        assert len(profiles) == 1
        assert profiles[0].user == speaker
        assert other_speaker not in {p.user for p in profiles}


@pytest.mark.django_db
def test_allocate_and_send_assigns_unique_vouchers(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['sent'] == 1
        assert result['aborted_insufficient'] is False
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.status == SpeakerVoucherStatus.SENT
        assert assignment.voucher.tag == 'speakers'
        assert QueuedMail.objects.filter(
            event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER, sent__isnull=False
        ).count() == 1


@pytest.mark.django_db
def test_resend_reuses_same_voucher(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        code = SpeakerVoucher.objects.get(speaker_profile=profile).voucher.code
        mails_before = QueuedMail.objects.filter(
            event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER, sent__isnull=False
        ).count()
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['resent'] == 1
        assert result['sent'] == 0
        assert SpeakerVoucher.objects.get(speaker_profile=profile).voucher.code == code
        assert SpeakerVoucher.objects.filter(speaker_profile=profile).count() == 1
        assert (
            QueuedMail.objects.filter(
                event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER, sent__isnull=False
            ).count()
            == mails_before + 1
        )


@pytest.mark.django_db
def test_not_sent_assignment_is_retried_without_new_voucher(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        voucher = speaker_voucher_batch[0]
        SpeakerVoucher.objects.create(
            event=event,
            speaker_profile=profile,
            voucher=voucher,
            status=SpeakerVoucherStatus.NOT_SENT,
        )
        assert profiles_needing_voucher(event).filter(pk=profile.pk).exists()
        remaining_before = speaker_voucher_settings.batch_remaining_count()
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['sent'] == 1
        assert result['resent'] == 0
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.voucher_id == voucher.pk
        assert assignment.status == SpeakerVoucherStatus.SENT
        assert speaker_voucher_settings.batch_remaining_count() == remaining_before
        assert QueuedMail.objects.filter(
            event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER, sent__isnull=False
        ).exists()


@pytest.mark.django_db
def test_insufficient_vouchers_sends_nothing(
    event, speaker, confirmed_submission, speaker_voucher_settings
):
    with scope(event=event):
        speaker_voucher_settings.voucher_tag = 'empty-batch'
        speaker_voucher_settings.save(update_fields=['voucher_tag'])
        profile = speaker.event_profile(event)
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['aborted_insufficient'] is True
        assert result['sent'] == 0
        assert SpeakerVoucher.objects.filter(event=event).count() == 0
        assert not QueuedMail.objects.filter(
            event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER
        ).exists()


@pytest.mark.django_db
def test_expired_vouchers_are_not_available(event, speaker, confirmed_submission):
    with scope(event=event):
        settings_obj = SpeakerVoucherSettings.objects.create(
            event=event,
            enabled=True,
            voucher_tag='speakers',
        )
        Voucher.objects.create(
            event=event,
            code='EXPIRED1',
            tag='speakers',
            max_usages=1,
            redeemed=0,
            valid_until=now() - timedelta(days=1),
            price_mode='set',
            value=Decimal('0.00'),
        )
        Voucher.objects.create(
            event=event,
            code='USED1',
            tag='speakers',
            max_usages=1,
            redeemed=1,
            price_mode='set',
            value=Decimal('0.00'),
        )
        assert settings_obj.batch_remaining_count() == 0
        profile = speaker.event_profile(event)
        result = allocate_and_send_vouchers(event, settings_obj, [profile])
        assert result['aborted_insufficient'] is True
        assert SpeakerVoucher.objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_voucher_never_reused_across_speakers(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch, other_speaker
):
    with scope(event=event):
        SpeakerProfile.objects.get_or_create(event=event, user=other_speaker)
        confirmed_submission.speakers.add(other_speaker)
        profiles = list(eligible_speaker_profiles(event))
        assert len(profiles) == 2
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, profiles)
        assert result['sent'] == 2
        codes = list(SpeakerVoucher.objects.filter(event=event).values_list('voucher__code', flat=True))
        assert len(codes) == len(set(codes))


@pytest.mark.django_db
def test_speaker_voucher_mail_template_placeholders(event):
    with scope(event=event):
        template = event.get_mail_template(MailTemplateRoles.SPEAKER_VOUCHER)
        assert 'voucher_code' in template.valid_placeholders
        assert 'voucher_url' in template.valid_placeholders
        assert '{voucher_code}' in str(template.text)
        assert '{voucher_url}' in str(template.text)


@pytest.mark.django_db
def test_orga_can_open_speaker_vouchers_page(orga_client, event, speaker_voucher_batch):
    response = orga_client.get(event.orga_urls.speaker_vouchers, follow=True)
    assert response.status_code == 200
    assert 'Speaker Vouchers' in response.text
    assert 'Enable speaker vouchers' in response.text


@pytest.mark.django_db
def test_orga_can_save_speaker_voucher_settings(orga_client, event, speaker_voucher_batch):
    response = orga_client.post(
        event.orga_urls.speaker_vouchers,
        data={'enabled': 'on', 'voucher_tag': 'speakers'},
        follow=True,
    )
    assert response.status_code == 200
    with scope(event=event):
        settings_obj = SpeakerVoucherSettings.objects.get(event=event)
        assert settings_obj.enabled is True
        assert settings_obj.voucher_tag == 'speakers'


@pytest.mark.django_db
def test_orga_bulk_send_vouchers(
    orga_client, event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch, orga_user
):
    """The bulk-send endpoint dispatches a background task and returns immediately.

    We patch ``apply_async`` to run the allocation service synchronously so the
    test can still assert on the resulting DB state and activity log requestor.
    """
    from eventyay.base.models import Event as _Event
    from eventyay.base.models import SpeakerProfile as _SP
    from eventyay.base.models import User as _User
    from eventyay.base.models.speaker_voucher import SpeakerVoucherSettings as _SVS
    from eventyay.base.services.speaker_vouchers import allocate_and_send_vouchers as _asv

    def _run_sync(args, **kw):
        ev = _Event.objects.get(pk=args[0])
        sv_settings = _SVS.objects.get(pk=args[1])
        profiles = list(_SP.objects.filter(pk__in=args[2]).select_related('user'))
        user_pk = args[3] if len(args) > 3 else None
        req = _User.objects.get(pk=user_pk) if user_pk else None
        with scope(event=ev):
            _asv(ev, sv_settings, profiles, requestor=req)

    with patch(
        'eventyay.base.services.speaker_vouchers.send_speaker_vouchers_task.apply_async',
        side_effect=_run_sync,
    ):
        response = orga_client.post(event.orga_urls.speaker_vouchers_send, follow=True)

    assert response.status_code == 200
    # Page should come back immediately with the async "Sending…" message.
    assert 'Sending' in response.text and 'voucher' in response.text
    with scope(event=event):
        profile = speaker.event_profile(event)
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.status == SpeakerVoucherStatus.SENT
        assert QueuedMail.objects.filter(event=event, sent__isnull=False).exists()
        assert not profiles_needing_voucher(event).exists()
        log = assignment.logged_actions().first()
        assert log is not None
        assert log.user == orga_user


@pytest.mark.django_db
def test_orga_bulk_send_retries_not_sent_when_batch_empty(
    orga_client, event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch, orga_user
):
    """Speakers with status=not_sent already hold a voucher code.

    A bulk send retry should succeed and dispatch even when the batch has 0 spare codes.
    """
    from eventyay.base.models import Event as _Event
    from eventyay.base.models import SpeakerProfile as _SP
    from eventyay.base.models import User as _User
    from eventyay.base.models.speaker_voucher import SpeakerVoucherSettings as _SVS
    from eventyay.base.services.speaker_vouchers import allocate_and_send_vouchers as _asv

    with scope(event=event):
        profile = speaker.event_profile(event)
        voucher = speaker_voucher_batch[0]
        # Invalidate remaining batch vouchers so remaining unused count is 0
        for v in speaker_voucher_batch[1:]:
            v.redeemed = 1
            v.save(update_fields=['redeemed'])
        SpeakerVoucher.objects.create(
            event=event,
            speaker_profile=profile,
            voucher=voucher,
            status=SpeakerVoucherStatus.NOT_SENT,
        )
        assert speaker_voucher_settings.batch_remaining_count() == 0
        assert profiles_needing_voucher(event).count() == 1

    def _run_sync(args, **kw):
        ev = _Event.objects.get(pk=args[0])
        sv_settings = _SVS.objects.get(pk=args[1])
        profiles = list(_SP.objects.filter(pk__in=args[2]).select_related('user'))
        user_pk = args[3] if len(args) > 3 else None
        req = _User.objects.get(pk=user_pk) if user_pk else None
        with scope(event=ev):
            _asv(ev, sv_settings, profiles, requestor=req)

    with patch(
        'eventyay.base.services.speaker_vouchers.send_speaker_vouchers_task.apply_async',
        side_effect=_run_sync,
    ):
        response = orga_client.post(event.orga_urls.speaker_vouchers_send, follow=True)

    assert response.status_code == 200
    assert 'Sending' in response.text and 'voucher' in response.text
    with scope(event=event):
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.status == SpeakerVoucherStatus.SENT
        assert assignment.voucher_id == voucher.pk
        log = assignment.logged_actions().first()
        assert log is not None
        assert log.user == orga_user


@pytest.mark.django_db
def test_send_speaker_vouchers_task_records_requestor(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch, orga_user
):
    with scope(event=event):
        profile = speaker.event_profile(event)
    send_speaker_vouchers_task(event.pk, speaker_voucher_settings.pk, [profile.pk], user_pk=orga_user.pk)
    with scope(event=event):
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.status == SpeakerVoucherStatus.SENT
        log = assignment.logged_actions().first()
        assert log is not None
        assert log.user == orga_user


@pytest.mark.django_db
def test_orga_bulk_send_aborts_when_batch_empty(
    orga_client, event, speaker, confirmed_submission, speaker_voucher_settings
):
    with scope(event=event):
        speaker_voucher_settings.voucher_tag = 'missing'
        speaker_voucher_settings.save(update_fields=['voucher_tag'])
    response = orga_client.post(event.orga_urls.speaker_vouchers_send, follow=True)
    assert response.status_code == 200
    assert 'Not enough unused vouchers' in response.text
    with scope(event=event):
        assert SpeakerVoucher.objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_voucher_redeem_url_encodes_special_characters(event):
    with scope(event=event):
        url = voucher_redeem_url(event, 'A&B+C#1')
    query = parse_qs(urlparse(url).query)
    assert query['voucher'] == ['A&B+C#1']


@pytest.mark.django_db
def test_usable_batch_excludes_vouchers_reserved_in_cart(event, speaker_voucher_batch):
    with scope(event=event):
        product = Product.objects.create(event=event, name='Ticket', default_price=0, admission=True)
        reserved = speaker_voucher_batch[0]
        CartPosition.objects.create(
            event=event,
            cart_id='speaker-voucher-cart',
            product=product,
            price=0,
            expires=now() + timedelta(minutes=30),
            voucher=reserved,
        )
        with scopes_disabled():
            usable_ids = set(usable_batch_vouchers(event, 'speakers').values_list('pk', flat=True))
        assert reserved.pk not in usable_ids
        assert usable_ids == {speaker_voucher_batch[1].pk, speaker_voucher_batch[2].pk}


@pytest.mark.django_db
def test_ineligible_speaker_with_assignment_is_not_resent(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        confirmed_submission.state = SubmissionStates.CANCELED
        confirmed_submission.save(update_fields=['state'])
        mails_before = QueuedMail.objects.filter(
            event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER, sent__isnull=False
        ).count()
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['skipped_ineligible'] == 1
        assert result['resent'] == 0
        assert result['sent'] == 0
        assert (
            QueuedMail.objects.filter(
                event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER, sent__isnull=False
            ).count()
            == mails_before
        )


@pytest.mark.django_db
def test_expired_assignment_is_replaced_before_retry(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        expired = speaker_voucher_batch[0]
        expired.valid_until = now() - timedelta(days=1)
        expired.save(update_fields=['valid_until'])
        SpeakerVoucher.objects.create(
            event=event,
            speaker_profile=profile,
            voucher=expired,
            status=SpeakerVoucherStatus.NOT_SENT,
        )
        result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['sent'] == 1
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.voucher_id != expired.pk
        assert assignment.status == SpeakerVoucherStatus.SENT
        assert assignment.voucher.valid_until is None or assignment.voucher.valid_until >= now()


@pytest.mark.django_db
def test_failed_synchronous_send_leaves_assignment_not_sent(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        with patch(
            'eventyay.base.models.mail.QueuedMail.send',
            side_effect=SendMailException('smtp failed'),
        ):
            result = allocate_and_send_vouchers(event, speaker_voucher_settings, [profile])
        assert result['sent'] == 0
        assignment = SpeakerVoucher.objects.get(speaker_profile=profile)
        assert assignment.status == SpeakerVoucherStatus.NOT_SENT
        assert assignment.sent_at is None
        assert not QueuedMail.objects.filter(
            event=event, template__role=MailTemplateRoles.SPEAKER_VOUCHER
        ).exists()


@pytest.mark.django_db
def test_usable_batch_requires_single_use_unused_codes(event):
    with scope(event=event):
        multi = Voucher.objects.create(
            event=event,
            code='MULTI1',
            tag='speakers',
            max_usages=5,
            redeemed=0,
            price_mode='set',
            value=Decimal('0.00'),
        )
        used = Voucher.objects.create(
            event=event,
            code='USED2',
            tag='speakers',
            max_usages=1,
            redeemed=1,
            price_mode='set',
            value=Decimal('0.00'),
        )
        ok = Voucher.objects.create(
            event=event,
            code='OK0001',
            tag='speakers',
            max_usages=1,
            redeemed=0,
            price_mode='set',
            value=Decimal('0.00'),
        )
        with scopes_disabled():
            usable_ids = set(usable_batch_vouchers(event, 'speakers').values_list('pk', flat=True))
        assert usable_ids == {ok.pk}
        assert multi.pk not in usable_ids
        assert used.pk not in usable_ids


@pytest.mark.django_db
def test_row_state_shows_not_sent_after_failed_delivery(
    event, speaker, confirmed_submission, speaker_voucher_batch
):
    with scope(event=event):
        profile = speaker.event_profile(event)
        SpeakerVoucher.objects.create(
            event=event,
            speaker_profile=profile,
            voucher=speaker_voucher_batch[0],
            status=SpeakerVoucherStatus.NOT_SENT,
        )
        assert speaker_voucher_row_state(profile) == 'not_sent'


@pytest.mark.django_db
def test_pending_send_counts_include_expired_replacements(
    event, speaker, confirmed_submission, speaker_voucher_settings, speaker_voucher_batch, orga_user
):
    from eventyay.orga.views.speaker import SpeakerVoucherSettingsView

    with scope(event=event):
        profile = speaker.event_profile(event)
        expired = speaker_voucher_batch[0]
        expired.valid_until = now() - timedelta(days=1)
        expired.save(update_fields=['valid_until'])
        SpeakerVoucher.objects.create(
            event=event,
            speaker_profile=profile,
            voucher=expired,
            status=SpeakerVoucherStatus.NOT_SENT,
        )
        view = SpeakerVoucherSettingsView()
        view.request = type('R', (), {'event': event, 'user': orga_user})()
        recipient_count, new_needed, remaining, remaining_after = view._pending_send_counts(
            speaker_voucher_settings
        )
        assert recipient_count == 1
        assert new_needed == 1
        assert remaining == 2
        assert remaining_after == 1


@pytest.mark.django_db
def test_user_without_permission_cannot_access_or_send(review_client, event):
    response = review_client.get(event.orga_urls.speaker_vouchers, follow=True)
    assert response.status_code == 404

    response = review_client.post(event.orga_urls.speaker_vouchers_send, follow=True)
    assert response.status_code == 404
