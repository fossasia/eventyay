"""Test the funding.json validity."""

import json
from pathlib import Path

import pytest

HERE = Path(__file__).parent
REPOSITORY_ROOT = HERE.parent.parent.parent
FUNDING_JSON_PATH = REPOSITORY_ROOT / "funding.json"


@pytest.fixture
def funding_json():
    """Load the funding.json file."""
    return FUNDING_JSON_PATH.read_text(encoding="utf-8")


@pytest.fixture
def funding_data(funding_json):
    """Parse the funding.json file."""
    return json.loads(funding_json)


@pytest.mark.parametrize(
    "key_present",
    [
        "$schema",
        "version",
        "entity",
        "projects",
        "funding",
    ],
)
def test_some_validity_of_funding_json(funding_data, key_present):
    """Check that the funding.json file is valid JSON."""
    assert key_present in funding_data


def test_consistent_format(funding_json, funding_data):
    """Check that the funding.json file is consistently formatted."""
    reformatted = json.dumps(funding_data, indent=4) + "\n"
    print(reformatted)
    assert funding_json == reformatted, "The file should be properly formatted."
