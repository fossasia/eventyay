.. _talk-installation:

Installation
============

This guide will help you to install eventyay on Linux. This setup is suitable to
support events in usual sizes, but the guide does not go into performance
tuning or customisation options beyond the standard settings.

.. warning:: While we try to make it straightforward to run eventyay, it still
             requires some Linux experience to get it right, particularly to
             make sure that standard security practices are followed. If
             you’re not feeling comfortable managing a Linux server, check
             out our hosting and service offers at `eventyay.com`_.

For the more automation-savvy, we also provide an `Ansible role`_ that follows
this guide. If you prefer a docker setup, there is a `docker-compose setup`_.
Please note that the docker setup is community provided and not officially
supported.

Step 0: Prerequisites
---------------------

Please set up the following systems beforehand. We can’t go into their use
and configuration here, but please have a look at the linked pages.

* **Python 3.11 or newer**
* An SMTP server to send out mails
* An HTTP reverse proxy like nginx to allow HTTPS connections and serve
  files from the filesystem
* A database server: `PostgreSQL`_ 14+, or SQLite 3. Given the choice, we’d
  recommend to use PostgreSQL.
* A `redis`_ server, if you want to use eventyay with an asynchronous task
  runner or improved caching.
* `nodejs`_ and npm (usually bundled with nodejs). You’ll need a `supported
  version of nodejs`_.

.. highlight:: console

Please ensure that the environment used to run eventyay is configured to work
with non-ASCII file names. You can check this by running::

    $ python -c "import sys; print(sys.getfilesystemencoding())"
    utf-8

Step 1: Unix user
-----------------

.. hint:: All code lines prepended with a ``#`` symbol are commands that you
          need to execute on your server as the ``root`` user (e.g. using
          ``sudo``); you should run all lines prepended with a ``$`` symbol as
          the ``eventyay`` user. If the prompt reads ``(env)$``, your virtual
          Python environment should be active.

As we do not want to run eventyay as root, we first create a new unprivileged user::

    # adduser eventyay --disabled-password --home /var/eventyay


Step 2: Database setup
----------------------

Eventyay runs with PostgreSQL or SQLite. If you’re using SQLite, you can skip
this step, as there is no need to set up the database.

We recommend using PostgreSQL. This is how you can set up a database for your
Eventyay installation – if you do not use PostgreSQL, please refer to the
appropriate documentation on how to set up a database::

  # sudo -u postgres createuser eventyay -P
  # sudo -u postgres createdb -O eventyay eventyay

Make sure that your database encoding is UTF-8. You can check with this command::

  # sudo -u postgres psql -c 'SHOW SERVER_ENCODING'


Step 3: Package dependencies
----------------------------

Besides the packages above, you might need local system packages to build and
run eventyay. We cannot maintain an up-to-date dependency list for all Linux
flavours – on Ubuntu-like systems, you will need packages like:

- ``build-essential``
- ``libssl-dev``
- ``python3-dev``
- ``python3-venv``
- ``gettext``


Step 4: Configuration
---------------------

.. highlight:: console

Now we’ll create a configuration directory and configuration file for eventyay::

    # mkdir /etc/eventyay
    # touch /etc/eventyay/eventyay.cfg
    # chown -R eventyay:eventyay /etc/eventyay/
    # chmod 0600 /etc/eventyay/eventyay.cfg

This snippet can get you started with a basic configuration in your
``/etc/eventyay/eventyay.cfg`` file:

.. literalinclude:: ../../../app/eventyay.cfg
   :language: ini

Refer to :ref:`configure` for a full list of configuration options – the
options above are only the ones you’ll likely need to get started.

Step 5: Installation
--------------------

For your Python installation, you’ll want to use a virtual environment to
isolate the installation from system packages. Set up your virtual environment
like this – you’ll only have to run this command once (that is, only once per
Python version – when you upgrade from Python 3.13 to 3.14, you’ll need to
remove the old ``venv`` directory and create it again the same way)::

    $ python3 -m venv /var/eventyay/venv

Now, activate the virtual environment – you’ll have to run this command once
per session whenever you’re interacting with ``python``, ``pip`` or
``eventyay``::

    $ source /var/eventyay/venv/bin/activate

Now, upgrade your pip and then install the required Python packages::

    (venv)$ pip install -U pip setuptools wheel gunicorn

.. note:: You may need to replace all following mentions of ``pip`` with ``pip3``.

For **SQLite**::

    pip install --upgrade-strategy eager -U eventyay

For **PostgreSQL**::

    pip install --upgrade-strategy eager -U "eventyay[postgres]"

If you intend to run eventyay with asynchronous task runners or with redis as
cache server, you can add ``[redis]`` to the installation command, which will
pull in the appropriate dependencies. Please note that you should also use
``eventyay[redis]`` when you upgrade eventyay in this case.

We also need to create a data directory::

    $ mkdir -p /var/eventyay/data/media

Finally, check that your configuration is ready for production::

    (venv)$ python -m eventyay check --deploy

We compile static files and translation data and create the database structure::

    (venv)$ python -m eventyay migrate
    (venv)$ python -m eventyay rebuild

Now, create a user with administrator rights, an organiser and a team by running::

    (venv)$ python -m eventyay init

Step 6: Starting eventyay as a service
--------------------------------------

.. highlight:: ini

We recommend starting eventyay using systemd to make sure it starts up after a
reboot. Create a file named ``/etc/systemd/system/eventyay-web.service``, and
adjust the content to fit your system::

    [Unit]
    Description=eventyay web service
    After=network.target

    [Service]
    User=eventyay
    Group=eventyay
    WorkingDirectory=/var/eventyay
    ExecStart=/var/eventyay/venv/bin/gunicorn eventyay.wsgi \
                          --name eventyay --workers 4 \
                          --max-requests 1200  --max-requests-jitter 50 \
                          --log-level=info --bind=127.0.0.1:8345
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

Eventyay optionally runs with Celery, a service that allows for long-running
tasks (like sending many emails) to be performed asynchronously in the
background. We strongly recommend running eventyay with Celery workers, as some
things, like cleaning up unused files, are otherwise not going to work.

To run Celery workers, you’ll need a second service
``/etc/systemd/system/eventyay-worker.service`` with the following content::

    [Unit]
    Description=eventyay background worker
    After=network.target

    [Service]
    User=eventyay
    Group=eventyay
    WorkingDirectory=/var/eventyay
    ExecStart=/var/eventyay/venv/bin/celery -A eventyay.celery_app worker -l info
    Restart=on-failure

    [Install]
    WantedBy=multi-user.target

.. highlight:: console

You can now run the following commands to enable and start the services::

    # systemctl daemon-reload
    # systemctl enable eventyay-web eventyay-worker
    # systemctl start eventyay-web eventyay-worker

Step 7: Reverse proxy
---------------------

You’ll need to set up an HTTP reverse proxy to handle HTTPS connections. It
does not particularly matter which one you use, as long as you make sure to use
`strong encryption settings`_. Your proxy should

* serve all requests exclusively over HTTPS,
* follow established security practices regarding protocols and ciphers.
* optionally set best-practice headers like ``Referrer-Policy`` and
  ``X-Content-Type-Options``,
* set the ``X-Forwarded-For`` and ``X-Forwarded-Proto`` headers,
* set the ``Host`` header,
* serve all requests for the ``/static/`` and ``/media/`` paths from the
  directories you set up in the previous step, without permitting directory
  listings or traversal. Files in the ``/media/`` directory should be served
  as attachments. You can use fairly aggressive cache settings for these URLs, and
* pass all other requests to the gunicorn server you set up in the previous step.


Step 8: Check the installation
------------------------------

You can make sure the web interface is up and look for any issues with::

    # journalctl -u eventyay-web

If you use Celery, you can do the same for the worker processes (for example in
case the emails are not sent)::

    # journalctl -u eventyay-worker

If you’re looking for errors, check the eventyay log. You can find the logging
directory in the start-up output.

Once eventyay is up and running, you can also find up to date administrator information
at https://eventyay.yourdomain.com/orga/admin/.

Step 9: Provide periodic tasks
------------------------------

There are a couple of things in eventyay that should be run periodically. It
does not matter how you run them, so you can go with your choice of periodic
tasks, be they systemd timers, cron, or something else entirely.

In the same environment as you ran the previous eventyay commands (e.g. the
``eventyay`` user, using either the executable paths in the
``/var/eventyay/venv`` directory, or running ``/var/eventyay/venv/bin/activate``
first), you should run

- ``python -m eventyay runperiodic`` somewhere every five minutes and once per hour.
- ``python -m eventyay clearsessions`` about once a month.

You could for example configure the ``eventyay`` user cron like this::

  */10 * * * * /var/eventyay/venv/bin/python -m eventyay runperiodic

Next Steps
----------

You made it! You should now be able to reach eventyay at
https://eventyay.yourdomain.com/orga/ Log in with the administrator account you
configured above, and create your first event!

Check out :ref:`configure` for details on the available configuration options.

If you want to read about updates, backups, and monitoring, head over to our
:ref:`maintenance` documentation!

.. _Ansible role: https://github.com/eventyay/ansible-eventyay
.. _Let’s Encrypt: https://letsencrypt.org/
.. _PostgreSQL: https://www.postgresql.org/docs/
.. _redis: https://redis.io/docs/latest/
.. _ufw: https://en.wikipedia.org/wiki/Uncomplicated_Firewall
.. _strong encryption settings: https://mozilla.github.io/server-side-tls/ssl-config-generator/
.. _docker-compose setup: https://github.com/fossasia/eventyay-docker
.. _eventyay.com: https://eventyay.com/
.. _nodejs: https://github.com/nodesource/distributions/blob/master/README.md
.. _supported version of nodejs: https://nodejs.org/en/about/previous-releases
