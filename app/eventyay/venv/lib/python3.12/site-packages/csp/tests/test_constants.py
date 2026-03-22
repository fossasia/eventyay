from csp import constants


def test_nonce() -> None:
    assert constants.Nonce() == constants.Nonce()
    assert constants.NONCE == constants.Nonce()
    assert repr(constants.Nonce()) == "csp.constants.NONCE"
