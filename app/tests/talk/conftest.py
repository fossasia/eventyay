import pytest
from django.core import management


@pytest.fixture(scope="session", autouse=True)
def collect_static():
    """
    Collect static files once for the test session.
    This is required by multiple tests but does not depend on Pretalx.
    """
    management.call_command("collectstatic", "--noinput", "--clear")


@pytest.fixture
def template_patch(monkeypatch):
    """
    Patch template rendering for performance.
    This avoids slow Django template rendering during tests.
    """
    monkeypatch.setattr(
        "django.template.backends.django.Template.render",
        lambda *args, **kwargs: "mocked template",
    )