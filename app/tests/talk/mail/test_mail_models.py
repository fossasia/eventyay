import pytest
from django_scopes import scope, scopes_disabled

from eventyay.common.exceptions import SendMailException
from pretalx.common.mail import TolerantDict
from pretalx.mail.models import QueuedMail
from pretalx.person.models import User


@pytest.mark.parametrize(
    "key,value",
    (
        ("1", "a"),
        ("2", "b"),
        ("3", "3"),
    ),
)
def test_tolerant_dict(key, value):
    d = TolerantDict({"1": "a", "2": "b"})
    assert d[key] == value


@pytest.mark.django_db
def test_sent_mail_sending(sent_mail):
    assert str(sent_mail)
    with pytest.raises(Exception):  # noqa
        sent_mail.send()


@pytest.mark.django_db
def test_mail_template_model(mail_template):
    assert mail_template.event.slug in str(mail_template)


@pytest.mark.parametrize("commit", (True, False))
@pytest.mark.django_db
def test_mail_template_model_to_mail(mail_template, commit):
    mail_template.to_mail("testdummy@exacmple.com", None, commit=commit)


@pytest.mark.django_db
def test_mail_template_model_to_mail_fails_without_address(mail_template):
    with pytest.raises(TypeError):
        mail_template.to_mail(1, None)


@pytest.mark.django_db
def test_mail_template_model_to_mail_shortens_subject(mail_template):
    mail_template.subject = "A" * 300
    mail = mail_template.to_mail("testdummy@exacmple.com", None, commit=False)
    assert len(mail.subject) == 199


@pytest.mark.django_db
def test_mail_submission_present_in_context(mail_template, submission, event):
    with scope(event=event):
        mail = mail_template.to_mail(
            "testdummy@exacmple.com",
            None,
            context_kwargs={"submission": submission},
        )
        mail.save()
        assert mail.submissions.all().contains(submission)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "text,signature,expected",
    (
        ("test", None, "test"),
        ("test", "sig", "test\n-- \nsig"),
        ("test", "-- \nsig", "test\n-- \nsig"),
    ),
)
def test_mail_make_text(event, text, signature, expected):
    if signature:
        event.mail_settings["signature"] = signature
        event.save()
    assert QueuedMail(text=text, event=event).make_text() == expected


@pytest.mark.django_db
@pytest.mark.parametrize(
    "text,prefix,expected",
    (
        ("test", None, "test"),
        ("test", "pref", "[pref] test"),
        ("test", "[pref]", "[pref] test"),
    ),
)
def test_mail_prefixed_subject(event, text, prefix, expected):
    if prefix:
        event.mail_settings["subject_prefix"] = prefix
        event.save()
    assert QueuedMail(text=text, subject=text, event=event).prefixed_subject == expected


@pytest.mark.parametrize("email", (None, "   "))
@pytest.mark.django_db
def test_to_mail_user_missing_email_returns_draft(mail_template, email):
    """commit=False with no valid email should return a draft without raising."""
    user = User(email=email, locale="en")
    mail = mail_template.to_mail(user, None, commit=False)
    assert mail.to is None


@pytest.mark.parametrize("email", (None, "   "))
@pytest.mark.django_db
def test_to_mail_user_missing_email_skip_queue_raises(mail_template, email):
    """commit=False + skip_queue=True with no valid email must raise SendMailException."""
    user = User(email=email, locale="en")
    with pytest.raises(SendMailException):
        mail_template.to_mail(user, None, commit=False, skip_queue=True)


@pytest.mark.django_db
def test_to_mail_valid_email_used_when_mixed(mail_template):
    """A user with a valid email produces the correct to address."""
    user = User(email="valid@example.com", locale="en")
    mail = mail_template.to_mail(user, None, commit=False)
    assert mail.to == "valid@example.com"
