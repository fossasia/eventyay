---
name: django-create-api-endpoint
description: Steps for adding a new Django REST Framework API endpoint
---

## When to use

Use this skill when exposing new data or functionality via the DRF API using viewsets and serializers.

## Steps

1. Create or update a serializer in the appropriate location within `app/eventyay/api/`. Prefer using explicit serializer fields covering direct model or nested relation mappings.
2. Create or update a viewset within `app/eventyay/api/`.
3. Register the new viewset's router in the appropriate module router or `app/eventyay/api/urls.py`.

## Validation

1. Verify that the serializer correctly maps exactly to the expected model or relations without unnecessary custom method wrappers.
2. Assert the endpoint resolves effectively.

## Gotchas

- **Computed Data Overuse:** Only use `SerializerMethodField` for genuinely computed or conditional data. Do NOT use it if a direct field assignment natively exists.
