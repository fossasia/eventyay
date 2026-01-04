# Sessions Module

This module provides unified components for displaying session information across the application (Talk schedule, Video rooms, etc.).

## Components

### SessionDetail
Displays detailed information about a single session.

**Props:**
- `talkId` (String, required): The ID of the session/talk.
- `context` (String, optional): The context in which the component is used.
  - `'talk'` (default): For the main schedule view. Informational focus.
  - `'video'`: For video playback pages. Includes actions like "Join Room".

**Usage:**
```vue
<template>
  <SessionDetail :talkId="id" context="video" />
</template>
<script>
import SessionDetail from 'modules/sessions/components/SessionDetail.vue'
</script>
```

### SessionList
Displays a linear schedule list of sessions.

## Architecture
The module uses a Pinia store (`useScheduleStore`) to fetch and manage the event schedule data from the API. This store is shared with the Speakers module to avoid duplicate data fetching.

- `store.js`: Pinia store definition.
- `service.js`: API interaction logic.
