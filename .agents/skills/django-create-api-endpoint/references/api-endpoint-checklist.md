# API Endpoint Checklist

## Serializer

- Fields are explicit and stable.
- `SerializerMethodField` is used only for truly computed values.

## Viewset

- Querysets are scoped correctly for event ownership where required.
- Permissions and authentication requirements are explicit.

## Routing

- Viewset is registered through the expected router/URL module.
- Naming and URL style match nearby endpoints.

## Validation

- Add tests for success and failure responses.
- Confirm response shape and status codes are intentional.
