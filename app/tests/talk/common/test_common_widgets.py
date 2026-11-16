from types import SimpleNamespace

from django.utils.datastructures import MultiValueDict

from eventyay.common.forms.widgets import SlidesWidget, get_count


def test_slides_widget_accepts_plain_dict_session_data():
    widget = SlidesWidget()

    value = widget.value_from_datadict(data={}, files=MultiValueDict(), name='slides')

    assert value == {
        'resources': [],
        'clear_ids': [],
    }


def test_get_count_uses_zero_annotated_count():
    value = SimpleNamespace(instance=SimpleNamespace(count=0))
    assert get_count(value, 'Design & UX') == 0


def test_get_count_ignores_plain_string_label():
    assert get_count('1', 'Design & UX') == 0


def test_get_count_reads_countable_label():
    assert get_count('1', SimpleNamespace(count=3)) == 3


def test_get_count_ignores_callable_instance_count():
    value = SimpleNamespace(instance=SimpleNamespace(count=lambda *args: 5))
    assert get_count(value, 'Design & UX') == 0
