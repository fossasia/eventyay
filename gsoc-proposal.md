## Summary

Fixes #<issue_number>

Adds a new read-only REST API endpoint at `GET /api/v1/events/` that allows
unauthenticated users to browse public, live events. Previously, the
`EventViewSet` at `/api/v1/organizers/{organizer}/events/` returned 403 for
unauthenticated requests, even though the same event data was publicly visible
on the HTML start page.

## Changes

- **`app/eventyay/api/serializers/event.py`** — Added `PublicEventSerializer`
  with a limited set of public-safe fields (name, slug, organizer, dates,
  location, currency, geo coordinates, has_subevents). Sensitive fields like
  plugins, sales_channels, meta_data, seating_plan, and valid_keys are excluded.

- **`app/eventyay/api/views/event.py`** — Added `PublicEventFilter` (search by
  name, filter by organizer/past/future) and `PublicEventViewSet` (read-only,
  no authentication required). The queryset filters for `live=True`,
  `is_public=True`, and excludes test-mode events.

- **`app/eventyay/api/urls.py`** — Registered the new viewset at
  `/api/v1/events/`.

## API

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/v1/events/` | None | List public events (paginated) |
| GET | `/api/v1/events/{slug}/` | None | Single event detail |

**Query parameters:** `?q=` (name search), `?organizer=` (filter by slug),
`?is_future=true/false`, `?is_past=true/false`, `?has_subevents=true/false`,
`?ordering=date_from` / `-date_from` / `name` / `slug`

**Example response:**

{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "name": {"en": "Test Conference 2026"},
      "slug": "testevent",
      "organizer": "testorg",
      "date_from": "2026-04-05T15:42:36.239375Z",
      "date_to": "2026-04-07T15:42:36.239382Z",
      "location": null,
      "currency": "USD",
      "has_subevents": false,
      "geo_lat": null,
      "geo_lon": null
    }
  ]
}
