import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock
from django import forms
from django.http import HttpResponseNotAllowed
from django_scopes import scope
from i18nfield.strings import LazyI18nString

from eventyay.cfp.forms.cfp import CfPFormMixin
from eventyay.cfp.flow import BaseCfPStep, FormFlowStep, i18n_string, validate_editor_payload


@pytest.mark.parametrize(
    "data,locales,expected",
    (
        ("Submission", ["en"], {"en": "Submission"}),
        ("Submission", ["en", "de"], {"en": "Submission", "de": "Submission"}),
        (
            "Submission",
            ["en", "de", "xx"],
            {"en": "Submission", "de": "Submission", "xx": "Submission"},
        ),
        ({"en": "Submission"}, ["en"], {"en": "Submission"}),
        ({"en": "Submission"}, ["en", "de"], {"en": "Submission", "de": "Submission"}),
        (
            {"en": "Submission", "de": "Submission"},
            ["en"],
            {"en": "Submission", "de": "Submission"},
        ),
        (
            {"en": "Submission", "de": "Submission"},
            ["en", "de"],
            {"en": "Submission", "de": "Submission"},
        ),
        (
            {"en": "Submission", "de": "WRONG"},
            ["en", "de"],
            {"en": "Submission", "de": "WRONG"},
        ),
        (LazyI18nString({"en": "Submission"}), ["en", "de"], {"en": "Submission"}),
        (1, ["en", "de"], {"en": "", "de": ""}),
    ),
)
def test_i18n_string(data, locales, expected):
    assert i18n_string(data, locales).data == expected


@pytest.mark.parametrize(
    "data,expected",
    (
        (None, {"steps": {}}),
        ([], {"steps": {}}),
        ({"steps": {"info": {}}}, {"steps": {"info": {"fields": []}}}),
        (
            {"steps": {"info": {"icon": "foo"}}},
            {"steps": {"info": {"fields": [], "icon": "foo"}}},
        ),
        ({"steps": {"info": {"fields": []}}}, {"steps": {"info": {"fields": []}}}),
        (
            {"steps": {"info": {"fields": [], "text": "teeext"}}},
            {"steps": {"info": {"fields": [], "text": {"en": "teeext"}}}},
        ),
        (
            {
                "steps": {
                    "info": {
                        "fields": [{"widget": "w", "key": "k", "help_text": "bar"}]
                    }
                }
            },
            {"steps": {"info": {"fields": [{"key": "k", "help_text": {"en": "bar"}}]}}},
        ),
        ({"steps": []}, {"steps": {}}),
        ({"steps": [{"identifier": "info"}]}, {"steps": {"info": {"fields": []}}}),
        ({"steps": [{}]}, {"steps": {}}),
        ({"steps": [{"identifier": ""}]}, {"steps": {}}),
        ({"steps": [{"identifier": ["info"]}]}, {"steps": {}}),
        ({"steps": [{"identifier": "info"}, {}]}, {"steps": {"info": {"fields": []}}}),
        (
            {"steps": [{"identifier": "info", "fields": [{}]}]},
            {"steps": {"info": {"fields": []}}},
        ),
        (
            {"steps": [{"identifier": "info", "fields": [{"key": 123}]}]},
            {"steps": {"info": {"fields": []}}},
        ),
        ({"steps": {"invalid_step": "not-a-dict"}}, {"steps": {}}),
    ),
)
@pytest.mark.django_db
def test_cfp_flow(event, data, expected):
    """Verify CfP flow configuration normalization and persistence behavior."""
    with scope(event=event):
        assert event.cfp.settings["flow"] == {}
        event.cfp_flow.save_config(event.cfp_flow.get_config(data))
        assert event.cfp.settings["flow"] == expected
        assert event.cfp_flow.get_config_json()


@pytest.mark.parametrize(
    "data,expected_error",
    (
        (None, "Payload must be a dictionary or a list."),
        ([], None),
        ([{"identifier": "info"}], None),
        ([{"identifier": "info", "fields": [{"key": "k"}]}], None),
        ({"steps": []}, None),
        ({"steps": [{"identifier": "info"}]}, None),
        ({"steps": [{"identifier": "info", "fields": [{"key": "k"}]}]}, None),
        ({"steps": {"info": {"fields": [{"key": "k"}]}}}, None),
        (
            {"steps": [{}]},
            "steps[0] is missing required field 'identifier'.",
        ),
        (
            {"steps": [{"identifier": ""}]},
            "steps[0] is missing required field 'identifier'.",
        ),
        (
            {"steps": [{"identifier": 123}]},
            "steps[0]['identifier'] must be a string.",
        ),
        (
            {"steps": [{"identifier": "info"}, {"identifier": "info"}]},
            "Duplicate step identifier 'info' found in steps.",
        ),
        (
            {"steps": "invalid"},
            "'steps' must be a list or dictionary.",
        ),
        (
            "not a dict or list",
            "Payload must be a dictionary or a list.",
        ),
        (
            {"steps": [{"identifier": "info", "fields": "not-a-list"}]},
            "steps[0]['fields'] must be a list.",
        ),
        (
            {"steps": [{"identifier": "info", "fields": ["not-a-dict"]}]},
            "steps[0]['fields'][0] must be an object.",
        ),
        (
            {"steps": [{"identifier": "info", "fields": [{}]}]},
            "steps[0]['fields'][0] is missing required field 'key'.",
        ),
        (
            {"steps": [{"identifier": "info", "fields": [{"key": 123}]}]},
            "steps[0]['fields'][0]['key'] must be a string.",
        ),
        (
            {"steps": [{"identifier": "info", "title": {"en": []}}]},
            "steps[0]['title']['en'] must be a string.",
        ),
        (
            {"steps": [{"identifier": "info", "fields": [{"key": "k", "help_text": {"en": []}}]}]},
            "steps[0]['fields'][0]['help_text']['en'] must be a string.",
        ),
        (
            {"steps": {"info": "not-a-dict"}},
            "Step 'info' configuration must be an object.",
        ),
        (
            {"steps": {"info": {"fields": "not-a-list"}}},
            "Step 'info'['fields'] must be a list.",
        ),
        (
            {"steps": {"info": {"fields": [{}]}}},
            "Step 'info'['fields'][0] is missing required field 'key'.",
        ),
        (
            {"steps": {"info": {"title": {"en": 123}}}},
            "Step 'info'['title']['en'] must be a string.",
        ),
    ),
)
def test_validate_editor_payload(data, expected_error):
    """Verify that validate_editor_payload correctly accepts valid configurations and rejects malformed inputs."""
    assert validate_editor_payload(data) == expected_error




def test_base_cfp_step_attributes():
    step = BaseCfPStep(None)
    assert step.priority == 100
    assert step.done(None) is None
    assert isinstance(step.get(None), HttpResponseNotAllowed)
    assert isinstance(step.post(None), HttpResponseNotAllowed)

def test_form_flow_step_handles_none_file_content_type():
    class TestFormFlowStep(FormFlowStep):
        @property
        def identifier(self):
            return 'test'

    step = TestFormFlowStep(None)
    step.cfp_session = {
        'files': {
            'test': {
                'image': {
                    'name': 'test.png',
                    'tmp_name': 'test.png',
                    'content_type': None,
                }
            }
        }
    }

    assert step.get_form_initial() == {
        'image': SimpleNamespace(
            name='test.png',
            url='/media/cfp_uploads/test.png'
        )
    }


def test_cfp_form_mixin_scrubs_incomplete_errors_in_not_strict_mode():
    class PartialValueField(forms.MultiValueField):
        def __init__(self, *args, **kwargs):
            super().__init__(
                fields=(
                    forms.CharField(required=True),
                    forms.CharField(required=True),
                ),
                require_all_fields=False,
                *args,
                **kwargs,
            )

        def compress(self, data_list):
            return data_list

    class DraftSplitForm(CfPFormMixin, forms.Form):
        availability = PartialValueField(required=True)

    form = DraftSplitForm(
        data={
            'availability_0': '2026-05-26',
            'availability_1': '',
        },
        not_strict=True,
    )

    assert form.is_valid()
    assert not form.errors


def test_form_flow_step_clears_last_session_file():
    
    class TestFormFlowStep(FormFlowStep):
        @property
        def identifier(self):
            return 'test'
            
    step = TestFormFlowStep(None)
    step.request = MagicMock()
    step.request.method = 'POST'
    step.request.POST = {'slide-clear': '1'}
    step.file_storage = MagicMock()
    
    step.cfp_session = {
        'files': {
            'test': {
                'slide': {
                    'name': 'test.pdf',
                    'tmp_name': 'test_tmp.pdf',
                    'content_type': 'application/pdf',
                }
            }
        }
    }
    
    files = step.get_files()
    
    assert files is None
    assert 'slide' not in step.cfp_session['files']['test']


def test_form_flow_step_invalid_post_retains_session_file():
    
    class TestForm(forms.Form):
        name = forms.CharField(required=True)
        document = forms.FileField(required=False)
        
    class TestFormFlowStep(FormFlowStep):
        form_class = TestForm
        @property
        def identifier(self):
            return 'test'
            
        def get_form_kwargs(self):
            return {}
            
    step = TestFormFlowStep(None)
    step.request = MagicMock()
    step.request.method = 'POST'
    step.request.POST = {'name': ''}  # Invalid POST (missing required 'name')
    step.request.FILES = MagicMock()
    step.request.FILES.lists.return_value = []
    step.file_storage = MagicMock()
    
    step.cfp_session = {
        'initial': {},
        'data': {},
        'files': {
            'test': {
                'document': {
                    'name': 'test.pdf',
                    'tmp_name': 'test_tmp.pdf',
                    'content_type': 'application/pdf',
                }
            }
        }
    }
    
    form = step.get_form()
    
    assert not form.is_valid()
    assert 'name' in form.errors
    # Verify the previously uploaded file's initial data remains available on the form
    assert 'document' in form.initial
    assert form.initial['document'].name == 'test.pdf'


def test_form_flow_step_invalid_post_cleared_file_not_in_initial():
    class TestForm(forms.Form):
        name = forms.CharField(required=True)
        document = forms.FileField(required=False)
        
    class TestFormFlowStep(FormFlowStep):
        form_class = TestForm
        @property
        def identifier(self):
            return 'test'
            
        def get_form_kwargs(self):
            return {}
            
    step = TestFormFlowStep(None)
    step.request = MagicMock()
    step.request.method = 'POST'
    step.request.POST = {'name': '', 'document-clear': '1'}  # Invalid POST + clear file
    step.request.FILES = MagicMock()
    step.request.FILES.lists.return_value = []
    step.file_storage = MagicMock()
    
    step.cfp_session = {
        'initial': {},
        'data': {},
        'files': {
            'test': {
                'document': {
                    'name': 'test.pdf',
                    'tmp_name': 'test_tmp.pdf',
                    'content_type': 'application/pdf',
                }
            }
        }
    }
    
    form = step.get_form()
    
    assert not form.is_valid()
    assert 'name' in form.errors
    # Verify the cleared file is removed from the form initial data
    assert 'document' not in form.initial or not form.initial['document']
