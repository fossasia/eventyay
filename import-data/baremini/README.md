# Bare Minimum event — import CSV pack

## Speakers (`baremini_speakers.csv`)

**Re-import the same file** to update existing speakers (matched by **Email** or **Speaker Code**).

| CSV column | Map to |
|------------|--------|
| Full Name | Full name |
| Email | Email address |
| Biography | Biography |
| Speaker Code | Speaker ID |
| Locale | Invite language |
| **Profile Picture URL** | **Profile picture URL** |
| Profile Picture Source | Profile picture source |
| Profile Picture License | Profile picture license |
| Linked Sessions | Linked session IDs |

Profile images are downloaded from the URL on import. **Note:** avatars are only set for speakers who do not already have an uploaded profile image. To refresh images, remove existing avatars in the UI first, then re-import.

## Sessions (`baremini_sessions.csv`)

Import after speakers. Map **Speaker Emails** → Linked speaker IDs.

## Orders (`baremini_orders.csv`)

Products: `Standard Ticket`, `Virtual Ticket`, `BE HAPPY`.
