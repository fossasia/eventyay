Video Configuration
===================

The video frontend can be statically configured by defining :code:`window.Eventyay` before startup.
For example, add the following to the :code:`index.html` you are serving:

.. code-block:: html

	<script>window.Eventyay={"api": {"socket": "wss://sample.demo.Eventyay.org/ws/world/sample/"}, "features": []}</script>

Full configuration
------------------

.. code-block:: js

	{
		"api": {
			"base": "https://sample.demo.Eventyay.org/api/world/sample/",
			"socket": "wss://sample.demo.Eventyay.org/ws/world/sample/",
			"upload": "https://sample.demo.Eventyay.org/storage/upload/"
		},
		"features": [] // enable experimental features,
		"locale": "en", // DEPRECTATED, alias of defaultLocale
		"defaultLocale": "en",
		"locales": ["en", "de", "pt_BR"], // keep this empty to disable user-choosable locale. Order of this array is dropdown order
		"date_locale": "en-ie",
		"timetravelTo": "2020-08-26T06:49:28.975Z", // forces local time to always be this (for schedule demo purposes ONLY)
		// if no token is found in URL hash redirect to given authentication URL.
		// used together with an external server which generates JW tokens based e.g. on user login and password
		"externalAuthUrl": "https://example.com/auth",
		"theme": {
			"logo": {
				"url": "/eventyay-video-logo.svg",
				"fitToWidth": false // optional
			}
			"colors": {
				"primary": '#673ab7', // hightlight color, should be high contrast on white background
				"sidebar": '#180044'
			},
			"streamOfflineImage": "/some-large-image.svg", // image shown instead of "Stream offline"
			// override texts in the ui
			// see video/src/locales for full list of keys
			// DO NOT use this to completely translate the ui
			"textOverwrites": {
				"ProfilePrompt:headline:text": "’ello Guv!"
			},
			"identicons": {
				"style": "identiheart" // the identicon renderer, one of: identiheart, initials
			}
		},
		"videoPlayer": {
			"hls.js": {} // https://github.com/video-dev/hls.js/blob/master/docs/API.md#fine-tuning
		}
	}


Presentation Mode
-----------------

To enter presentation mode, append `/presentation` to a room url.
This shows ONLY the content of the currently pinned question (and updates if anything changes).

You can style presenation mode via custom css:

.. code-block:: css

	// add a background
	#presentation-mode {
		background: url('YOUR_URL_HERE');
		background-size: cover;
		color: A_COLOR_THAT_MATCHES_YOUR_BACKGROUND;
	}

Experimental Features
---------------------

* schedule-control
* roulette
* muxdata
* zoom
* janus
* jitsi
* page.landing
* iframe-player
* polls

Jitsi Rooms
-----------

Jitsi rooms are available when the :code:`jitsi` feature flag is enabled. They are configured as a dedicated
video room provider, not as a generic iframe, so Eventyay checks room permissions before returning the Jitsi
join configuration.

For moderator support, use a Jitsi deployment with JWT/token authentication enabled. Public anonymous Jitsi
rooms can be used only without reliable moderator enforcement, because Eventyay cannot force Jitsi moderator
state after the user enters an anonymous room.

Room configuration fields:

* :code:`domain`: Jitsi Meet domain, for example :code:`meet.example.org`.
* :code:`room_name`: Jitsi room name. If omitted, Eventyay uses the room ID.
* :code:`jwt_enabled`: Enable server-side JWT generation.
* :code:`app_id`: JWT issuer/application ID configured on the Jitsi deployment.
* :code:`key_id`: Optional JWT key ID sent as the token :code:`kid` header.
* :code:`app_secret`: JWT shared secret. Eventyay stores this server-side and does not expose it in room config.
* :code:`start_with_audio_muted`: Ask Jitsi to join with audio muted.
* :code:`start_with_video_muted`: Ask Jitsi to join with video muted.

Manual test checklist:

* Enable the :code:`jitsi` feature flag.
* Create a Jitsi room in the video admin UI.
* Configure a JWT-enabled Jitsi domain, app ID, key ID if needed, and app secret.
* Join as an attendee and verify the room opens.
* Join as a user with :code:`room:jitsi.moderate` and verify Jitsi receives moderator context.
* Join as a user without :code:`room:jitsi.join` and verify Eventyay denies the room config request.
* Confirm the room config returned to the frontend does not include :code:`app_secret`.
