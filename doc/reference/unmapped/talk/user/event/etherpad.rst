Etherpad collaborative notes
============================

eventyay can attach an `Etherpad <https://etherpad.org/>`_ pad to each session,
so speakers, attendees, and organisers can take collaborative notes for talks,
workshops, BoF sessions, and meetings.

The pad *content* is always stored on the configured Etherpad instance, never
inside eventyay. eventyay only stores and displays the pad link.

Overview
--------

The integration has three levels:

* **Platform** – the administrator configures the Etherpad instance and decides
  whether the integration is available at all.
* **Event** – organisers enable Etherpad for their event and choose whether pad
  links are shown publicly.
* **Session** – each session has its own Etherpad URL, entered manually or
  generated automatically.

Platform configuration (administrators)
---------------------------------------

In the global settings (control panel → *Global settings* → *Etherpad*), an
administrator can configure:

* **Enable Etherpad integration** – master switch for the whole platform.
* **Default Etherpad instance URL** – e.g. ``https://pad.example.org``.
* **Etherpad API key** – the contents of the instance's ``APIKEY.txt``. This is
  only required for automatic pad creation and is never exposed to the browser.
* **Pad name pattern** – the template used to generate pad names. Available
  placeholders are ``{event}``, ``{submission}`` and ``{token}``. The default is
  ``{event}-{submission}-{token}``.

If no API key is configured, eventyay still generates pad links ("link-only"
mode): Etherpad creates the pad automatically the first time someone opens the
link.

Event configuration (organisers)
---------------------------------

Once the platform integration is enabled with an instance URL, an *Etherpad*
section appears in your event settings, where you can:

* **Enable Etherpad for sessions** – turn the feature on for this event.
* **Auto-generate Etherpad links** – show a one-click button on session pages to
  create a pad.
* **Show Etherpad links publicly** – when enabled, the pad link is shown on the
  public session page. When disabled, the link stays visible only to organisers.

Session configuration
----------------------

On the session edit page you can:

* Enter or edit the **Etherpad URL** manually. You can link to any Etherpad
  instance, not only the platform default — useful if different sessions use
  different instances.
* Click **Auto-generate Etherpad link** to create a pad automatically (if your
  event allows it). If the session already has a pad, you will be asked to
  confirm before it is replaced, so existing notes are never lost accidentally.
  Generating the same session's pad twice (with confirmation) produces a new pad
  name each time; the old pad and its content remain on the Etherpad server but
  are no longer linked from the session.

Public session pages
--------------------

When the event and session settings allow it, public session pages show an
**Open collaborative notes** button. The link opens the pad on the configured
Etherpad instance in a new browser tab. If public display is disabled, the link
is not shown to public visitors.

Security notes
--------------

* Etherpad API keys are stored server-side only and are never sent to the
  browser or exposed through the API.
* Generated pad names use a stable, URL-safe pattern (event, session code, and a
  random token) rather than the public session title.
* Pad links are only exposed publicly when the organiser has explicitly enabled
  public display for the event.
