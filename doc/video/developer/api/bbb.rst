BigBlueButton module
====================

To enable video calls, we integrate the BigBlueButton (BBB) software. eventyay implements simple load balancing across
multiple BBB servers, which is why the frontend always needs to convert a room or call ID into an actual meeting
URL explicitly.

Prerequisites
-------------

To use BigBlueButton with eventyay, the following prerequisites must be met:

- A running BigBlueButton server supported by the upstream BBB project.
- The BBB server must be reachable from the eventyay backend.
- HTTPS is required for production deployments to allow clients to join meetings.
- The BigBlueButton shared secret must match the value configured in eventyay.

If multiple BBB servers are configured, eventyay will select a server automatically
based on internal load and availability.

BBB Rooms
---------

To join the video chat for a room, a client can push a message like this::

    => ["bbb.room_url", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"url": "https://…"}]
    
The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached, ``bbb.failed`` is
returned.

In a room-based BBB meeting, moderator and attendee permissions are assigned based on world and room rights.

Private conversations
---------------------

If a private conversation includes a chat message referring to a call ID, you can get the call URL like this:

    => ["bbb.call_url", 1234, {"call": "f160bf4f-93c4-4b50-b348-6ef61db4dbe7"}]
    <- ["success", 1234, {"url": "https://…"}]

The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached or the call does not exist
or you do not have permission to join, ``bbb.failed`` is returned.

In a private meeting, everyone has moderator rights.

Recordings
----------

If the user has the ``room:bbb.recordings`` permission, you can access recordings with the following command::

    => ["bbb.recordings", 1234, {"room": "f160bf4f-93c4-4b50-b348-6ef61db4dbe7"}]
    <- [
         "success",
         1234,
         {
           "results": [
             {
               "start": "2020-08-02T19:30:00.000+02:00",
               "end": "2020-08-02T20:30:00.000+02:00",
               "participants": "3",
               "state": "published",
               "url": "https://…"
             }
           ]
         }
       ]

The response will contain an URL for the video chat. A display name needs to be set, otherwise
an error of type ``bbb.join.missing_profile`` is returned. If the BBB server can't be reached or the call does not exist
or you do not have permission to join, ``bbb.failed`` is returned.

In a private meeting, everyone has moderator rights.

Required BBB Server Configuration
---------------------------------

The following configuration aspects are required or recommended on the
BigBlueButton server:

- API access must be enabled and reachable from eventyay.
- Recording must be enabled if recordings are expected to be listed.
- The shared secret configured in BBB must match the secret used by eventyay.
- The BBB server must be publicly reachable for clients joining meetings.

When using a reverse proxy, ensure that all BBB endpoints are forwarded correctly
and that WebSocket connections are supported.

Smoke Test Checklist
--------------------

After configuring BigBlueButton, the following steps can be used to verify
a basic end-to-end setup:

1. Create a Video Channel using BigBlueButton.
2. Join the room as a moderator.
3. Join the same room as an attendee.
4. Enable recording and end the meeting.
5. Verify that the recording appears and is accessible.

If any step fails, check backend logs and BBB server availability.

Troubleshooting
---------------

``bbb.join.missing_profile``
  The user does not have a display name set. Ensure the user profile
  contains a valid display name before joining a meeting.

``bbb.failed``
  A generic failure occurred while joining or creating a meeting. Possible
  causes include:

  - BigBlueButton server is unreachable
  - Invalid or mismatched shared secret
  - Missing permissions to join the room or call
  - Requested room or call does not exist
