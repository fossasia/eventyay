import pytest
from django_scopes import scope

from eventyay.orga.templatetags.context_icons import get_top_menu_item_icon_class
from eventyay.orga.templatetags.orga_edit_link import orga_edit_link
from eventyay.orga.templatetags.review_score import _review_score_number, review_score


@pytest.mark.parametrize(
    "score,expected",
    (
        (3, "3"),
        (0, "0"),
        (3.0, "3"),
        (1.5, "1.5"),
        (None, "×"),
    ),
)
@pytest.mark.django_db()
def test_templatetag_review_score(score, expected, event):
    with scope(event=event):
        assert _review_score_number(event, score) == expected


@pytest.mark.django_db
def test_template_tag_review_score_numeric(review):
    with scope(event=review.submission.event):
        review.submission.current_score = 1
        review.save()
        assert review_score(None, review.submission) == "1"


@pytest.mark.parametrize(
    "url,target,result",
    (
        (
            "https://foo.bar",
            None,
            '<a href="https://foo.bar" class="btn btn-xs btn-outline-info orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
        (
            "https://foo.bar",
            "",
            '<a href="https://foo.bar" class="btn btn-xs btn-outline-info orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
        (
            "https://foo.bar",
            "target",
            '<a href="https://foo.bar#target" class="btn btn-xs btn-outline-info orga-edit-link ml-auto" title="Edit"><i class="fa fa-pencil"></i></a>',
        ),
    ),
)
def test_templatetag_orga_edit_link(url, target, result):
    assert orga_edit_link(url, target) == result


def test_get_top_menu_item_icon_class():
    class DummyRequest:
        pass

    req = DummyRequest()

    # Default / Global -> fa-dashboard
    assert get_top_menu_item_icon_class({"request": req}) == "fa-dashboard"

    # Organizer only -> fa-group
    req.organizer = "org"
    assert get_top_menu_item_icon_class({"request": req}) == "fa-group"

    # Event (with or without organizer) -> fa-dashboard
    req.event = "event"
    assert get_top_menu_item_icon_class({"request": req}) == "fa-dashboard"

