Management commands
===================

This reference describes management commands supported by the eventyay server.
Generally, to run any command with our recommended Docker-based setup, you use a command line like this::

    $ docker exec -it eventyay.service eventyay <COMMAND> <ARGS>

We will not repeat the first part of that in the examples on this page. In the development setup, it looks like this
instead::

    $ docker-compose exec server python manage.py <COMMAND> <ARGS>

User management
---------------

``createsuperuser``
"""""""""""""""""""

The ``createsuperuser`` allows you to interactively create a user for the backend configuration interface.

Database management
-------------------

``migrate``
"""""""""""

The ``migrate`` command updates the database tables to conform to what eventyay expects.  As migrate touches the
database, you should have a backup of the state before the command run. Running migrate if eventyay has no pending
database changes is harmless. It will result in no changes to the database.

If migrations touch upon large populated tables, they may run for some time. The release notes will include a warning
if an upgrade can trigger this behaviour.

.. note:: Currently, this command is run by default during server startup.

``showmigrations``
""""""""""""""""""

If you ran into trouble during ``migrate``, run ``showmigrations``. It will show you the current state of all eventyay
migrations. It may be useful debug output to include in bug reports about database problems.

World management
----------------

``generate_token``
""""""""""""""""""

The ``generate_token`` command allows you to create a valid access token to a eventyay world::

    > generate_token myevent2019 --trait moderator --trait speaker --days 90
    https://eventyay.mydomain.com/#token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9…

``import_config``
"""""""""""""""""

The ``import`` command allows you to import a world configuration from a JSON file. It is mainly used during development
and testing to get started quickly. It takes a filename as the only argument. Note that the command looks for the file
*within* the Docker container::

    > import_config sample/worlds/sample.json


Connection management
---------------------

Connection management commands allow you to operate on the current user sessions on your system. They are useful during
system maintenance.

``connections list``
""""""""""""""""""""

Shows a list of connection labels and their estimated number of current connections. The estimated number might be
significantly higher than expected if connections where dropped without a cleanup, and old connection labels might
be lingering around for a couple of seconds. Connection labels are composed by the git commit ID of the eventyay
build and the environment (read from the ``EVENTYAY_VIDEO_ENVIRONMENT`` environment variable, ``unknown``) by default.
Sample output::

    > connections list
    label                              est. number of connections
    411b261.production                 3189

``connections drop``
""""""""""""""""""""

Tells the server to drop all connections, optionally filtered with a specific connection label. For example, you might
want to drop all connections still connected to an old version::

    > connections drop 411b261.*

The server will send out a message to all workers still having clients with this version to close these connections
immediately. If you do not want to drop all at once, you can pass a sleep interval, e.g. a number of milliseconds to
wait between every message that is sent out::

    > connections drop --interval 50 411b261.*

``connections force_reload``
""""""""""""""""""""""""""""

Tells the server to send a force-reload command to all connections, optionally filtered with a specific connection
label. For example, you might want to force-reload all connections still connected to an old version::

    > connections force_reload 411b261.*

This will not close the connections server-side, but instead instruct browsers to reload the application, e.g. to fetch
a new JavaScript application version.
If you do not want to reload all at once, you can pass a sleep interval, e.g. a number of milliseconds to
wait between every message that is sent out::

    > connections force_reload --interval 50 411b261.*

Debugging
---------

``shell_plus``
""""""""""""""

The ``shell_plus`` command opens a shell with the eventyay configuration and environment. All database models and some
more useful modules will be imported automatically.
