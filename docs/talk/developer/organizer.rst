.. _talk-organizer:

Organizer Interface
===================

The talk component includes a comprehensive organizer interface for managing call for papers, submissions, and schedules.

.. note::
   This documentation covers the organizer (``orga``) interface for the talk component.
   For CfP (call for papers) and public agenda interfaces, see other sections.

Overview
--------

The organizer interface provides tools for:

- **Event Management**: Configure talk-related settings
- **Submission Management**: Review and manage talk submissions
- **Speaker Management**: Handle speaker profiles and communications
- **Review Process**: Coordinate talk reviews
- **Schedule Building**: Create and publish event schedules
- **Track Organization**: Manage parallel tracks
- **Team Coordination**: Organize review teams

For complete API documentation, see :doc:`/development/api/component_modules`.

Key Modules
-----------

Signals
~~~~~~~

The organizer interface provides several signals for plugin integration:

.. automodule:: eventyay.orga.signals
   :members:
   :no-index:

Permissions
~~~~~~~~~~~

.. automodule:: eventyay.orga.permissions
   :members:
   :no-index:

Related Documentation
---------------------

- :doc:`/development/api/talk_models` - Data models
- :doc:`/development/api/signals` - Signal reference
- :doc:`plugins/index` - Plugin development

See Also
--------

- **CfP Interface**: :doc:`/talk/user/index`
- **Public Agenda**: For speaker and attendee views
- **API Documentation**: :doc:`/talk/api/index`

