import json
from typing import Union

from .structs import (
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialRequestOptions,
)
from .options_to_json_dict import options_to_json_dict


def options_to_json(
    options: Union[
        PublicKeyCredentialCreationOptions,
        PublicKeyCredentialRequestOptions,
    ],
) -> str:
    """
    Convert registration or authentication options into a simple JSON dictionary, and then stringify
    the result to send to the front end as `Content-Type: application/json`. Alternatively use
    `webauthn.helpers.options_to_json_dict` to get a raw `dict` instead to combine the options with
    other data beforehand/encode with a different scheme/etc...
    """
    return json.dumps(options_to_json_dict(options=options))
