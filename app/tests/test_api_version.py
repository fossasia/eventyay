import pytest

from eventyay.api.views.version import numeric_version


@pytest.mark.parametrize(
    ('version', 'expected'),
    [
        ('1.2.3a1', 10_020_032_001),
        ('1.2.3b2', 10_020_033_002),
        ('1.2.3rc3', 10_020_034_003),
    ],
)
def test_numeric_version_supports_pre_releases(version, expected):
    assert numeric_version(version) == expected
