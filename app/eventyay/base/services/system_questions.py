from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from eventyay.base.models import Product

SYSTEM_QUESTION_PRODUCT_OVERRIDES_SETTING = 'system_question_product_overrides'

STATE_DO_NOT_ASK = 'do_not_ask'
STATE_OPTIONAL = 'optional'
STATE_REQUIRED = 'required'
STATE_DEFAULT = 'default'

VALID_FIELD_STATES = {STATE_DO_NOT_ASK, STATE_OPTIONAL, STATE_REQUIRED}

SYSTEM_QUESTION_FIELD_SETTING_KEYS = {
    'attendee_name_parts': ('attendee_names_asked', 'attendee_names_required'),
    'attendee_email': ('attendee_emails_asked', 'attendee_emails_required'),
    'company': ('attendee_company_asked', 'attendee_company_required'),
    'job_title': ('attendee_job_title_asked', 'attendee_job_title_required'),
    'street': ('attendee_addresses_asked', 'attendee_addresses_required'),
}
SYSTEM_QUESTION_FIELDS = tuple(SYSTEM_QUESTION_FIELD_SETTING_KEYS.keys())


def asked_required_to_state(asked: bool, required: bool) -> str:
    if not asked:
        return STATE_DO_NOT_ASK
    return STATE_REQUIRED if required else STATE_OPTIONAL


def state_to_asked_required(state: str) -> tuple[bool, bool]:
    if state == STATE_REQUIRED:
        return True, True
    if state == STATE_OPTIONAL:
        return True, False
    return False, False


def get_system_question_base_state(event, field_id: str) -> str:
    asked_key, required_key = SYSTEM_QUESTION_FIELD_SETTING_KEYS[field_id]
    asked = event.settings.get(asked_key, as_type=bool)
    required = event.settings.get(required_key, as_type=bool)
    return asked_required_to_state(asked, required)


def get_system_question_base_states(event) -> dict[str, str]:
    return {
        field_id: get_system_question_base_state(event, field_id)
        for field_id in SYSTEM_QUESTION_FIELDS
    }


def get_system_question_product_overrides(event) -> dict[str, dict[str, str]]:
    raw = event.settings.get(SYSTEM_QUESTION_PRODUCT_OVERRIDES_SETTING, as_type=dict) or {}
    if not isinstance(raw, dict):
        return {}

    overrides: dict[str, dict[str, str]] = {}
    for field_id, states in raw.items():
        if field_id not in SYSTEM_QUESTION_FIELD_SETTING_KEYS or not isinstance(states, dict):
            continue
        cleaned_states: dict[str, str] = {}
        for product_id, state in states.items():
            if state in VALID_FIELD_STATES:
                cleaned_states[str(product_id)] = state
        if cleaned_states:
            overrides[field_id] = cleaned_states
    return overrides


def get_system_question_field_overrides(event, field_id: str) -> dict[str, str]:
    return get_system_question_product_overrides(event).get(field_id, {})


def get_system_question_state(
    event,
    field_id: str,
    product: 'Product | None' = None,
    *,
    base_states: dict[str, str] | None = None,
    product_overrides: dict[str, dict[str, str]] | None = None,
) -> str:
    if product is not None and not product.admission:
        return STATE_DO_NOT_ASK

    if base_states is None:
        base_state = get_system_question_base_state(event, field_id)
    else:
        base_state = base_states.get(field_id, get_system_question_base_state(event, field_id))

    if product is None:
        return base_state

    product_id = str(product.pk)
    if product_overrides is None:
        product_overrides = get_system_question_product_overrides(event)
    field_overrides = product_overrides.get(field_id, {})
    return field_overrides.get(product_id, base_state)


def get_system_question_asked_required(
    event,
    field_id: str,
    product: 'Product | None' = None,
    *,
    base_states: dict[str, str] | None = None,
    product_overrides: dict[str, dict[str, str]] | None = None,
) -> tuple[bool, bool]:
    return state_to_asked_required(
        get_system_question_state(
            event,
            field_id,
            product,
            base_states=base_states,
            product_overrides=product_overrides,
        )
    )


def set_system_question_field_overrides(event, field_id: str, product_states: dict[str | int, str]) -> None:
    overrides = get_system_question_product_overrides(event)

    cleaned_states: dict[str, str] = {}
    for product_id, state in product_states.items():
        if state in VALID_FIELD_STATES:
            cleaned_states[str(product_id)] = state

    if cleaned_states:
        overrides[field_id] = cleaned_states
    elif field_id in overrides:
        del overrides[field_id]

    event.settings.set(SYSTEM_QUESTION_PRODUCT_OVERRIDES_SETTING, overrides)


def get_enabled_system_question_fields(
    event,
    product: 'Product',
    *,
    base_states: dict[str, str] | None = None,
    product_overrides: dict[str, dict[str, str]] | None = None,
) -> set[str]:
    if not product.admission:
        return set()

    if base_states is None:
        base_states = get_system_question_base_states(event)
    if product_overrides is None:
        product_overrides = get_system_question_product_overrides(event)

    return {
        field_id
        for field_id in SYSTEM_QUESTION_FIELDS
        if get_system_question_asked_required(
            event,
            field_id,
            product,
            base_states=base_states,
            product_overrides=product_overrides,
        )[0]
    }


def product_has_system_questions(
    event,
    product: 'Product',
    *,
    base_states: dict[str, str] | None = None,
    product_overrides: dict[str, dict[str, str]] | None = None,
) -> bool:
    return bool(
        get_enabled_system_question_fields(
            event,
            product,
            base_states=base_states,
            product_overrides=product_overrides,
        )
    )


def get_products_with_system_question(
    event,
    field_id: str,
    products: Iterable['Product'],
    *,
    base_states: dict[str, str] | None = None,
    product_overrides: dict[str, dict[str, str]] | None = None,
) -> list['Product']:
    return [
        p
        for p in products
        if get_system_question_asked_required(
            event,
            field_id,
            p,
            base_states=base_states,
            product_overrides=product_overrides,
        )[0]
    ]
