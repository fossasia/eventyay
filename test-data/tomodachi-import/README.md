# Tomodachi Game — import pack

Ready-to-upload CSV files for the **Tomodachi** / `tomo-game` event.

| File | Rows | Use |
|------|------|-----|
| `speakers.csv` | 12 speakers | Orga → Import/Export → Speakers |
| `sessions.csv` | 24 confirmed sessions | Orga → Import/Export → Sessions |
| `orders.csv` | 80 orders | Control → Orders → Import attendees |

Session window: **2026-07-15 → 2026-07-31** (24 sessions within July).

## 1. Speakers

1. Open Talks orga for the event.
2. Settings / Import & Export → import **Speakers**.
3. Upload `speakers.csv`.
4. Map columns: `email`, `full_name`, `biography`, `identifier`.

## 2. Sessions (24)

1. Same Import & Export page → **Sessions**.
2. Upload `sessions.csv`.
3. Map at least: `title`, `linked_speakers` / `speakers`, `track`, `state`, `room`, `start`, `end`, `duration`.
4. Tracks/rooms are created automatically if missing (track auto-create is supported).
5. States are already `confirmed`.

Tip: import **speakers first** so `linked_speakers` emails resolve.

## 3. Orders (many products)

1. Tickets control → **Orders → Import**.
2. Upload `orders.csv`.
3. Settings suggestion:
   - One order per row (`orders` = many)
   - Status = paid
   - Enable **Create missing products** if products do not exist yet
4. Map: Email → email, Attendee name → attendee name, Product → product, Variation → variation, Price → price.

Product mix in the CSV:
- Standard Ticket, Virtual Ticket
- Admin, Management, Player Badge, Debt Repay, TeamShifts
- T-Shirt (S/M/L), Mug, Early Access Pass

## Notes

- Emails use `@tomodachi.test` / `@orders.tomodachi.test` domains so they will not hit real inboxes.
- Adjust product names in `orders.csv` if your event already uses different product titles.
- If schedule times fail validation, confirm the event date range covers **15–31 July 2026**.
