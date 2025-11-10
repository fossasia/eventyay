.. highlight:: python
   :linenothreshold: 5

.. _`pluginsignals`:

General APIs
============

This page lists some general signals and hooks which do not belong to a
specific plugin but might come in handy for all sorts of plugin.

Core
----

.. automodule:: eventyay.common.signals
   :members: periodic_task, register_locales, auth_html, register_data_exporters, register_my_data_exporters

.. automodule:: eventyay.submission.signals
   :members: submission_state_change

.. automodule:: eventyay.schedule.signals
   :members: schedule_release, register_my_data_exporters

.. automodule:: eventyay.mail.signals
   :members: register_mail_placeholders, queuedmail_post_send, queuedmail_pre_send, request_pre_send

.. automodule:: eventyay.person.signals
   :members: delete_user

Exporters
---------

.. automodule:: eventyay.common.signals
   :no-index:
   :members: register_data_exporters


Organiser area
--------------

.. automodule:: eventyay.orga.signals
   :members: nav_event, nav_global, html_head, activate_event, nav_event_settings, event_copy_data

.. automodule:: eventyay.common.signals
   :no-index:
   :members: activitylog_display, activitylog_object_link

Display
-------

.. automodule:: eventyay.cfp.signals
   :members: cfp_steps, footer_link, html_above_submission_list, html_above_profile_page, html_head

.. automodule:: eventyay.agenda.signals
   :members: register_recording_provider, html_above_session_pages, html_below_session_pages

.. automodule:: eventyay.common.signals
   :no-index:
   :members: profile_bottom_html
