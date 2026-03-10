from eventyay.common.signals import EventPluginSignal

register_recording_provider = EventPluginSignal()
"""
This signal is sent out to gather all known recording providers. Receivers
should return a subclass of ``pretalx.agenda.recording.BaseRecordingProvider.``

As with all event plugin signals, the ``sender`` keyword argument will contain
the event.
"""
html_above_session_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public session
pages.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing, and
the ``submission`` which is currently displayed.
The receivers are expected to return HTML.
"""
html_below_session_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public session
pages.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing, and
the ``submission`` which is currently displayed.
The receivers are expected to return HTML.
"""
html_above_schedule_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public schedule
page, above the schedule widget.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing.
The receivers are expected to return HTML.
"""
html_below_schedule_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public schedule
page, below the schedule widget.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing.
The receivers are expected to return HTML.
"""
html_above_speaker_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public speaker
detail page.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing, and
the ``profile`` of the speaker being displayed.
The receivers are expected to return HTML.
"""
html_below_speaker_pages = EventPluginSignal()
"""
This signal is sent out to display additional information on the public speaker
detail page.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing, and
the ``profile`` of the speaker being displayed.
The receivers are expected to return HTML.
"""
html_above_speakers_list = EventPluginSignal()
"""
This signal is sent out to display additional information on the public speakers
list page, above the speakers list.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing.
The receivers are expected to return HTML.
"""
html_below_speakers_list = EventPluginSignal()
"""
This signal is sent out to display additional information on the public speakers
list page, below the speakers list.

As with all plugin signals, the ``sender`` keyword argument will contain the event.
Additionally, the signal will be called with the ``request`` it is processing.
The receivers are expected to return HTML.
"""
