import datetime as dt

import pytest
from django import forms
from django.utils.translation import gettext_lazy as _
from django_scopes import scope, scopes_disabled

from eventyay.base.models import Answer, Submission
from eventyay.base.models.event import Organizer, Event
from eventyay.base.models.question import (
    TalkQuestion,
    TalkQuestionTarget,
    TalkQuestionVariant,
    TalkQuestionRequired,
    AnswerOption,
)
from eventyay.submission.forms.question import TalkQuestionsForm


@pytest.fixture
def event(db):
    with scopes_disabled():
        org = Organizer.objects.create(name="Test Org", slug="test-dep-org")
        return Event.objects.create(
            name="Test Event",
            slug="test-dep-evt",
            email="t@t.com",
            date_from=dt.date.today(),
            date_to=dt.date.today(),
            organizer=org,
        )


@pytest.fixture
def string_parent(event):
    with scopes_disabled():
        return TalkQuestion.all_objects.create(
            event=event,
            question="Are you a speaker?",
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.OPTIONAL,
            active=True,
            position=1,
        )


@pytest.fixture
def required_child(event, string_parent):
    with scopes_disabled():
        return TalkQuestion.all_objects.create(
            event=event,
            question="Which language?",
            variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.REQUIRED,
            active=True,
            position=2,
            dependency_question=string_parent,
            dependency_values=["yes"],
        )


def _form(event, data):
    with scope(event=event):
        return TalkQuestionsForm(event=event, data=data)


@pytest.mark.django_db
def test_hidden_dependent_field_is_not_required(event, string_parent, required_child):
    """Parent value not in dep_values → child is not enforced."""
    form = _form(event, {f"question_{string_parent.pk}": "no", f"question_{required_child.pk}": ""})
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_visible_dependent_field_empty_raises_error(event, string_parent, required_child):
    """Parent value matches → child is required → error on empty submission."""
    form = _form(event, {f"question_{string_parent.pk}": "yes", f"question_{required_child.pk}": ""})
    assert not form.is_valid()
    assert f"question_{required_child.pk}" in form.errors


@pytest.mark.django_db
def test_visible_dependent_field_filled_is_valid(event, string_parent, required_child):
    """Parent matches + child has a value → valid."""
    form = _form(event, {f"question_{string_parent.pk}": "yes", f"question_{required_child.pk}": "Python"})
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_chained_dependency_grandparent_not_met(event, string_parent):
    """Q1 condition not met → Q2 hidden → Q3 not enforced (full chain)."""
    with scopes_disabled():
        mid = TalkQuestion.all_objects.create(
            event=event, question="Mid?", variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION, question_required=TalkQuestionRequired.OPTIONAL,
            active=True, position=3, dependency_question=string_parent, dependency_values=["yes"],
        )
        leaf = TalkQuestion.all_objects.create(
            event=event, question="Leaf?", variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION, question_required=TalkQuestionRequired.REQUIRED,
            active=True, position=4, dependency_question=mid, dependency_values=["mid-answer"],
        )
    form = _form(event, {
        f"question_{string_parent.pk}": "no",
        f"question_{mid.pk}": "mid-answer",
        f"question_{leaf.pk}": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_choices_parent_dependency_by_option_pk(event):
    """CHOICES parent: dependency matched by AnswerOption PK stored in dependency_values."""
    with scopes_disabled():
        parent = TalkQuestion.all_objects.create(
            event=event, question="Track?", variant=TalkQuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION, question_required=TalkQuestionRequired.OPTIONAL,
            active=True, position=1,
        )
        opt = AnswerOption.objects.create(question=parent, answer="Python")
        child = TalkQuestion.all_objects.create(
            event=event, question="Python version?", variant=TalkQuestionVariant.STRING,
            target=TalkQuestionTarget.SUBMISSION, question_required=TalkQuestionRequired.REQUIRED,
            active=True, position=2,
            dependency_question=parent, dependency_values=[str(opt.pk)],
        )

    form = _form(event, {f"question_{parent.pk}": str(opt.pk), f"question_{child.pk}": ""})
    assert not form.is_valid()
    assert f"question_{child.pk}" in form.errors


@pytest.mark.django_db
def test_choices_field_always_uses_radio_select(event):
    """Radio fields must not switch to a dropdown when there are four or more options."""
    with scopes_disabled():
        question = TalkQuestion.all_objects.create(
            event=event,
            question='Pick one?',
            variant=TalkQuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.OPTIONAL,
            active=True,
            position=1,
        )
        for index in range(5):
            AnswerOption.objects.create(question=question, answer=f'Option {index}')

    with scope(event=event):
        form = TalkQuestionsForm(event=event)
        field = form.fields[f'question_{question.pk}']
        assert isinstance(field.widget, forms.RadioSelect)


@pytest.mark.django_db
def test_choices_required_field_has_no_empty_label(event):
    with scopes_disabled():
        question = TalkQuestion.all_objects.create(
            event=event,
            question='Pick one?',
            variant=TalkQuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.REQUIRED,
            active=True,
            position=1,
        )
        AnswerOption.objects.create(question=question, answer='Only option')

    with scope(event=event):
        form = TalkQuestionsForm(event=event)
        field = form.fields[f'question_{question.pk}']
        assert field.empty_label is None


@pytest.mark.django_db
def test_choices_optional_field_has_no_initial_without_answer(event):
    with scopes_disabled():
        question = TalkQuestion.all_objects.create(
            event=event,
            question='Pick one?',
            variant=TalkQuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.OPTIONAL,
            active=True,
            position=1,
        )
        AnswerOption.objects.create(question=question, answer='Only option')

    with scope(event=event):
        form = TalkQuestionsForm(event=event)
        field = form.fields[f'question_{question.pk}']
        assert field.initial is None
        assert field.empty_label == _('— No selection —')


@pytest.mark.django_db
def test_choices_ignores_removed_option_on_initial(event):
    with scopes_disabled():
        submission = Submission.objects.create(
            title='Test proposal',
            event=event,
            submission_type=event.cfp.default_type,
            content_locale='en',
        )
        question = TalkQuestion.all_objects.create(
            event=event,
            question='Pick one?',
            variant=TalkQuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.OPTIONAL,
            active=True,
            position=1,
        )
        removed_option = AnswerOption.objects.create(question=question, answer='Removed')
        AnswerOption.objects.create(question=question, answer='Still there')
        answer = Answer.objects.create(question=question, submission=submission, answer='Removed')
        answer.options.add(removed_option)
        removed_option.delete()

    with scope(event=event):
        form = TalkQuestionsForm(event=event, submission=submission)
        assert form.fields[f'question_{question.pk}'].initial is None


@pytest.mark.django_db
def test_choices_save_empty_clears_stale_answer(event):
    with scopes_disabled():
        submission = Submission.objects.create(
            title='Test proposal',
            event=event,
            submission_type=event.cfp.default_type,
            content_locale='en',
        )
        question = TalkQuestion.all_objects.create(
            event=event,
            question='Pick one?',
            variant=TalkQuestionVariant.CHOICES,
            target=TalkQuestionTarget.SUBMISSION,
            question_required=TalkQuestionRequired.OPTIONAL,
            active=True,
            position=1,
        )
        option = AnswerOption.objects.create(question=question, answer='Gone')
        answer = Answer.objects.create(question=question, submission=submission, answer='Gone')
        answer.options.add(option)
        option.delete()

    with scope(event=event):
        form = TalkQuestionsForm(
            event=event,
            submission=submission,
            data={f'question_{question.pk}': ''},
        )
        assert form.is_valid(), form.errors
        form.save()
        assert not submission.answers.filter(question=question).exists()
