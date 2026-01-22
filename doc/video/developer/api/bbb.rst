BigBlueButton module
====================

To enable video calls, we integrate the BigBlueButton (BBB) software. eventyay implements simple load balancing across
multiple BBB servers, which is why the frontend always needs to convert a room or call ID into an actual meeting
URL explicitly.

BBB Rooms
---------

To join the video chat for a room, a client can push a message like this::

    => ["bbb.room_url", 1234, {"room": "room_1"}]
    <- ["success", 1234, {"url": "https://…"}]
    

The response will contain a URL for the video chat. See the Error Handling section below for possible errors when joining.

In a room-based BBB meeting, moderator and attendee permissions are assigned based on world and room rights.

Error Handling
~~~~~~~~~~~~~~

When joining a BBB room or call, the following errors may occur:

**bbb.join.missing_profile**
  The user has not set a display name in their profile. The UI should prompt the user to:
  1. Navigate to their profile settings
  2. Set a display name
  3. Retry joining the video conference

**bbb.failed**
  The BigBlueButton server is unavailable or the meeting cannot be created. Common causes:
  
  - The BBB server is down or unreachable (network issue)
  - No active BBB servers are configured for this event
  - The meeting configuration is invalid
  
  The UI should display a user-friendly error message and offer a retry option. If the error persists,
  the event organizer should check the BBB server configuration and logs.

**protocol.denied**
  The user does not have permission to join this room's video conference. Check room-level permissions.

**room.unknown**
  The specified room does not exist.

Private conversations
---------------------

If a private conversation includes a chat message referring to a call ID, you can get the call URL like this::

    => ["bbb.call_url", 1234, {"call": "f160bf4f-93c4-4b50-b348-6ef61db4dbe7"}]
    <- ["success", 1234, {"url": "https://…"}]


The response will contain a URL for the video chat. See the Error Handling section above for possible errors when joining.

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

The response will contain the list of available recordings. If the BBB server can't be reached,
``bbb.failed`` is returned. If the user does not have permission to view recordings, ``protocol.denied`` is returned.

In a private meeting, everyone has moderator rights.
