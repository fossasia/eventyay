# Implementation Plan: Hybrid Attendee Experience

## Overview

Implement participation-mode-aware attendee routing, navigation, iCal export, schedule UI, and organizer email filtering. All code goes under `app/eventyay/`; tests under `app/tests/`. Language: Python 3.12 / Django 5.2+.

## Tasks

- [x] 1. Add `ParticipationMode` choices and `Product.participation_mode` field
  - Add `ParticipationMode(models.TextChoices)` with `VIRTUAL` and `IN_PERSON` to `app/eventyay/base/models/choices.py`
  - Add `participation_mode = models.CharField(...)` field to `Product` in `app/eventyay/base/models/product.py`, importing `ParticipationMode` from choices
  - Generate migration: `python manage.py makemigrations base --name product_participation_mode`
  - Update `app/eventyay/control/forms/product.py` to include `participation_mode` in the product edit form with label and help text
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 9.1_

  - [ ]* 1.1 Write property test for Product.participation_mode persistence round-trip
    - **Property 9: Product participation_mode persistence round-trip**
    - **Validates: Requirements 1.1, 1.2**
    - Use Hypothesis to generate any `ParticipationMode` value; save and reload Product; assert value preserved

  - [ ]* 1.2 Write property test for Product copy inherits participation_mode
    - **Property 10: Product copy inherits participation_mode**
    - **Validates: Requirement 1.4**
    - Generate Product with any mode; invoke copy logic; assert copied product has same mode

  - [ ]* 1.3 Write unit test for control form includes participation_mode field
    - Instantiate the product form and assert `participation_mode` is in `form.fields`
    - _Requirements: 1.3_

- [x] 2. Add `OrderPosition.participation_mode_override` field
  - Add `participation_mode_override = models.CharField(max_length=50, choices=..., null=True, blank=True)` to `OrderPosition` in `app/eventyay/base/models/orders.py`
  - Generate migration: `python manage.py makemigrations base --name orderposition_participation_mode_override`
  - _Requirements: 2.1_

  - [ ]* 2.1 Write unit test for override field existence and nullability
    - Assert `OrderPosition._meta.get_field('participation_mode_override').null` is `True`
    - _Requirements: 2.1_

- [x] 3. Implement `ExperienceProfile` dataclass and `ExperienceResolver` service
  - Create `app/eventyay/base/services/experience_resolver.py`
  - Define `ExperienceProfile` dataclass with typed fields: `participation_mode`, `has_stream_access`, `show_join_online_nav`, `primary_cta_url`, `calendar_location`
  - Implement `ExperienceResolver` class with `_HANDLERS` registry dict, `resolve()` method, `_build_virtual_profile()`, `_build_in_person_profile()`, `_get_stream_url()`, `_get_event_url()` helpers
  - `resolve()` must raise `ValueError` for missing product and for unknown mode
  - No Django request object dependency
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 9.2, 9.3, 9.4_

  - [ ]* 3.1 Write property test for ExperienceProfile flags match participation mode
    - **Property 1: ExperienceProfile flags match participation mode**
    - **Validates: Requirements 3.3, 3.4**
    - Use Hypothesis to generate virtual and in_person positions; assert `has_stream_access` and `show_join_online_nav` match expected values per mode

  - [ ]* 3.2 Write property test for resolver override precedence
    - **Property 2: Resolver override precedence**
    - **Validates: Requirements 2.2, 2.3**
    - Generate positions with and without `participation_mode_override`; assert resolved mode follows override-first rule

  - [ ]* 3.3 Write property test for ExperienceProfile structural completeness
    - **Property 3: ExperienceProfile structural completeness**
    - **Validates: Requirements 3.1, 3.2**
    - Generate any valid position; assert returned object is `ExperienceProfile` with all five fields present and correctly typed

  - [ ]* 3.4 Write unit tests for ExperienceResolver error conditions
    - Assert `ValueError` raised when `position.product_id` is `None` (Requirement 3.6)
    - Assert `ValueError` raised for unknown mode string (Requirement 9.3)
    - Assert resolver callable without request object (Requirement 3.5)

- [ ] 4. Checkpoint — Ensure all tests pass
  - Run `pytest tests/` and confirm all tests pass before proceeding. Ask the user if questions arise.

- [x] 5. Implement post-checkout routing in `ConfirmStep`
  - Override `get_success_url` in `app/eventyay/presale/checkoutflowstep/confirm_step.py`
  - Use `ExperienceResolver` to resolve profiles for all positions in the completed order (use `select_related('product')`)
  - Redirect to stream URL if all positions are virtual and stream URL is non-None; otherwise return `self.get_order_url(order)`
  - Wrap resolver calls in a try/except that logs a `WARNING` and falls back on any `ValueError`
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 5.1 Write property test for post-checkout redirect rule
    - **Property 4: Post-checkout redirect is stream page iff all positions are virtual and stream URL exists**
    - **Validates: Requirements 4.1, 4.2**
    - Generate orders with random mixes of virtual/in_person positions; assert redirect URL follows the all-virtual rule

  - [ ]* 5.2 Write unit tests for post-checkout edge cases
    - Assert fallback to order URL when stream URL is absent (Requirement 4.3)
    - Assert fallback to order URL when resolver raises (Requirement 4.4)

- [x] 6. Implement navigation personalisation in presale context
  - Update `app/eventyay/presale/context.py` to resolve the authenticated user's active `OrderPosition` for the event using `scope(event=event)` and `select_related('product')`
  - Inject `show_join_online_nav` (bool) and `join_online_url` (str or None) into the template context
  - Update the presale event navigation template to conditionally render the "Join online" link
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 6.1 Write unit tests for navigation context
    - Assert `show_join_online_nav=True` and `join_online_url` set for authenticated virtual attendee
    - Assert `show_join_online_nav=False` for authenticated in_person attendee
    - Assert `show_join_online_nav=False` for unauthenticated request (edge case 5.3)
    - Assert `show_join_online_nav=False` when stream page not configured (edge case 5.4)

- [x] 7. Implement iCal export personalisation
  - Update `get_ical` in `app/eventyay/presale/ical.py` to accept an optional `position` keyword argument
  - When `position` is provided, call `ExperienceResolver().resolve(position, event)` and use `profile.calendar_location` as the `LOCATION` value
  - Fall back to `ev.location` when `calendar_location` is `None` or resolver raises (log `WARNING`)
  - When `position` is `None`, preserve existing behaviour exactly
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 7.1 Write property test for iCal LOCATION round-trip
    - **Property 5: iCal LOCATION round-trip**
    - **Validates: Requirements 6.1, 6.2, 6.3**
    - Generate positions with known modes; call `get_ical`; assert LOCATION field matches `ExperienceProfile.calendar_location`

  - [ ]* 7.2 Write property test for iCal backward compatibility
    - **Property 6: iCal backward compatibility**
    - **Validates: Requirement 6.5**
    - Generate `Event` objects; call `get_ical` without position; assert output is identical to pre-feature behaviour

  - [ ]* 7.3 Write unit test for iCal virtual fallback to event URL
    - Assert LOCATION falls back to event URL when stream URL is absent for virtual attendee (edge case 6.4)

- [ ] 8. Checkpoint — Ensure all tests pass
  - Run `pytest tests/` and confirm all tests pass before proceeding. Ask the user if questions arise.

- [ ] 9. Implement schedule session card personalisation
  - Update the schedule context processor or view in `app/eventyay/schedule/` to resolve the authenticated attendee's `participation_mode` once per page load (using `ExperienceResolver` or direct field lookup)
  - Pass `attendee_participation_mode` as a template variable (string or `None`)
  - Update the session card template to conditionally render a "Join" CTA button (for virtual + streamed sessions) vs. room/location text
  - Ensure no additional per-session DB queries are introduced
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ]* 9.1 Write unit tests for schedule session card rendering
    - Assert "Join" CTA rendered for virtual attendee viewing a streamed session (Requirement 7.1)
    - Assert room/location rendered for in_person attendee (Requirement 7.2)
    - Assert room/location rendered for unauthenticated user (edge case 7.3)

- [x] 10. Implement Sendmail participation mode filter
  - Add `participation_mode` `ChoiceField` to `MailForm` in `app/eventyay/plugins/sendmail/forms.py` with choices `[('', 'All'), ('virtual', 'Virtual'), ('in_person', 'In-person')]`
  - In `SenderView.form_valid` in `app/eventyay/plugins/sendmail/views.py`, apply the participation mode filter to `opq` using a `Q(participation_mode_override=pm) | Q(participation_mode_override__isnull=True, product__participation_mode=pm)` query when the field is non-empty
  - Update the sendmail compose template to render the new filter field
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 10.1 Write unit test for Sendmail form includes participation_mode field
    - Instantiate `MailForm` and assert `participation_mode` is in `form.fields` (Requirement 8.1)

  - [ ]* 10.2 Write property test for Sendmail filter correctness
    - **Property 7: Sendmail participation mode filter correctness**
    - **Validates: Requirements 8.2, 8.3**
    - Generate sets of positions with mixed modes; apply filter; assert all results match the filter value

  - [ ]* 10.3 Write property test for Sendmail filter composability
    - **Property 8: Sendmail filter composability (metamorphic)**
    - **Validates: Requirement 8.5**
    - Generate position sets; apply existing filters then add participation filter; assert result count ≤ unfiltered count

- [ ] 11. Wire override logging for organizer-set participation_mode_override
  - In the organizer-facing view or service that sets `participation_mode_override` on an `OrderPosition`, call `order.log_action('eventyay.order.position.participation_mode_override_changed', data={...})` after saving
  - _Requirements: 2.4_

  - [ ]* 11.1 Write property test for override change logging
    - **Validates: Requirement 2.4**
    - For any valid override value set by an organizer, assert a `LogEntry` with the correct action type is created on the Order

- [ ] 12. Final checkpoint — Ensure all tests pass
  - Run `pytest tests/` and confirm all tests pass. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- All ORM queries on event-scoped models must use `django_scopes.scope(event=event)`
- Use `select_related('product')` when fetching `OrderPosition` objects to avoid N+1 queries
- Use `eventyay.*` imports throughout; no `pretix.*` or `pretalx.*` imports
- Property tests use Hypothesis with `@settings(max_examples=100)` minimum
- Each property test must include a comment: `# Feature: hybrid-attendee-experience, Property N: <text>`
