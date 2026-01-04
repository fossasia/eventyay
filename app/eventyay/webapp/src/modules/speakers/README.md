# Speakers Module

This module provides unified components for displaying speaker information.

## Components

### SpeakerDetail
Displays detailed information about a speaker and their sessions.

**Props:**
- `speakerId` (String, required): The ID/Code of the speaker.
- `context` (String, optional): The context in which the component is used.

### SpeakerList
Displays a grid of all speakers in the event.

## Architecture
This module shares the `useScheduleStore` with the Sessions module to access consistent schedule data.

- `store.js`: Exports the shared store.
- `service.js`: Exports the shared service.
