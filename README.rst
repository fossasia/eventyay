Eventyay
========

Eventyay is an open source event management platform by `FOSSASIA <https://fossasia.org>`_. It provides a unified system for event ticketing, registration, call for participation, speaker and session management, scheduling, online event video, web check in, organiser administration, APIs, and plugin based extensions.

Eventyay has been in development since 2014. Parts of the system historically originated from separate components for tickets, talks, and video. The current repository contains the unified Eventyay codebase.

Project status and release cycle
--------------------------------

Eventyay is actively developed.

The repository uses the following branch model:

* ``main`` is the production ready branch.
* ``dev`` is the testing and active development branch.

Pull requests should normally target ``dev``. Changes are tested and stabilised there before they are moved to ``main`` for production ready releases.

The repository is intended for:

* Contributors working on the Eventyay platform
* Developers building Eventyay plugins and integrations
* Operators evaluating or deploying self hosted Eventyay instances
* Event organisers and partners who need an extensible open source event platform

Main features
-------------

Eventyay includes:

* Event ticketing and registration
* Event related item sales, such as shirts or add ons
* Organiser and event administration
* Call for Participation workflows
* Speaker, submission, review, and schedule management
* Public event pages
* Schedule display and schedule editor frontends
* Online event and video related workflows
* Web based check in
* Separate check in station support through the Eventyay Checkin component
* PDF ticket and badge related workflows
* REST API endpoints
* OAuth and social authentication support
* Multi domain and multi event handling
* Plugin discovery and plugin URL registration
* Standard plugins and external plugin extensions for payments, CRM, exhibitions, social media, team shifts, interpretation, and spatial event integrations
* Email, notifications, scheduled tasks, reports, statistics, and check in lists
* Health check and metrics endpoints
* Internationalisation and translation infrastructure

Technology stack
----------------

Backend:

* Python 3.12
* Django 5.2
* Django REST Framework
* PostgreSQL
* Redis
* Celery
* Django Channels
* Daphne / ASGI
* Pydantic settings
* uv for Python dependency management

Frontend:

* Vue 3
* Vite
* JavaScript and TypeScript depending on the frontend module
* SCSS / Stylus
* Django Compressor for selected legacy and Django integrated assets

Quick start with Docker
-----------------------

Docker is the recommended way to start quickly.

Requirements:

* Docker
* Docker Compose plugin
* Git

Steps:

.. code-block:: bash

   git clone https://github.com/fossasia/eventyay.git
   cd eventyay
   git switch dev

   cp deployment/env.dev.sample .env.dev

   docker compose up -d --build

Create an admin user:

.. code-block:: bash

   docker exec -ti eventyay-next-web python manage.py create_admin_user

Open the local site:

.. code-block:: text

   http://localhost:8000

View logs:

.. code-block:: bash

   docker compose logs -f

Stop the development stack:

.. code-block:: bash

   docker compose down

The directory ``app/eventyay`` is mounted into the Docker container, so live editing of backend code is supported.

Python based local development
------------------------------

Use this setup when you want to run services directly on your machine.

Requirements:

* Python 3.12
* `uv <https://docs.astral.sh/uv/getting-started/installation/>`_
* PostgreSQL
* Redis
* Node.js and npm
* Debian or Ubuntu packages listed in ``deb-packages.txt`` or equivalent packages for your distribution

Clone the repository:

.. code-block:: bash

   git clone https://github.com/fossasia/eventyay.git
   cd eventyay
   git switch dev

Install external dependencies on Debian or Ubuntu:

.. code-block:: bash

   xargs -a deb-packages.txt sudo apt install

For Nushell:

.. code-block:: nu

   open deb-packages.txt | lines | sudo apt install ...$in

If you are using another Linux distribution, install the corresponding packages from ``deb-packages.txt``.

Install `uv <https://docs.astral.sh/uv/getting-started/installation/>`_.

Install and run Redis according to your distribution.

Create a PostgreSQL database. The default local database name is:

.. code-block:: text

   eventyay-db

On Linux, the simplest local development setup is PostgreSQL peer mode. Create a PostgreSQL user with the same name as your Linux user:

.. code-block:: bash

   sudo -u postgres createuser -s "$USER"

Then create a database owned by your user:

.. code-block:: bash

   createdb eventyay-db

You can then access the database without specifying a password, host, or port:

.. code-block:: bash

   psql eventyay-db

If you cannot use PostgreSQL peer mode, create ``app/eventyay.local.toml`` with database connection values:

.. code-block:: toml

   postgres_user = "your_db_user"
   postgres_password = "your_db_password"
   postgres_host = "localhost"
   postgres_port = 5432

Enter the app directory:

.. code-block:: bash

   cd app

Install Python dependencies:

.. code-block:: bash

   uv sync --all-extras --all-groups

Activate the virtual environment:

.. code-block:: bash

   . .venv/bin/activate

Run migrations:

.. code-block:: bash

   python manage.py migrate

Create an admin user:

.. code-block:: bash

   python manage.py create_admin_user

Build frontend and static assets:

.. code-block:: bash

   make npminstall
   python manage.py collectstatic --noinput
   python manage.py compress --force

Run the development server:

.. code-block:: bash

   python manage.py runserver

Open:

.. code-block:: text

   http://localhost:8000

Run Celery locally when working on background tasks:

.. code-block:: bash

   celery -A eventyay worker -l info

Mobile testing note
~~~~~~~~~~~~~~~~~~~


If you want to test the site from an Android emulator, use:

.. code-block:: text

   http://10.0.2.2:8000/

This is Android's alias for the host machine's localhost.

Permission note
~~~~~~~~~~~~~~~

If you get permission errors for ``eventyay/static/CACHE``, make sure that the directory and all files below it are owned by your user.

Frontend development
--------------------

The repository contains several frontend applications under ``app/eventyay/webapp/``:

.. code-block:: text

   app/eventyay/webapp/
   ├── schedule/              Schedule display web component
   ├── schedule-editor/       Schedule editor frontend
   ├── video/                 Online event video frontend
   └── webcheckin/            Web check in frontend

The root app ``Makefile`` installs and builds these frontend applications through npm and places compiled assets into the Django app data directory.

By default, Docker serves prebuilt frontend assets. To enable hot module replacement for frontend development, set this in ``.env.dev``:

.. code-block:: bash

   EVY_NPM_DEV=1

When enabled, Vite dev servers start automatically inside the container for the frontend webapps.

- ``schedule-editor`` runs on port ``8080``.
- ``video`` runs on port ``8880``.
- ``webcheckin`` runs on port ``8081``.
- ``schedule`` runs on port ``8082``.

You do not normally need to visit these ports directly. The frontend works alongside ``http://localhost:8000`` with hot module replacement.

The container must be recreated, not only restarted, for the environment change to take effect:

.. code-block:: bash

   docker compose up -d web

The default is:

.. code-block:: bash

   EVY_NPM_DEV=0

Before submitting frontend changes, always verify that the production asset build still works with the default value:

.. code-block:: bash

   docker exec -ti eventyay-next-web make npminstall
   docker exec -ti eventyay-next-web python manage.py collectstatic --noinput

Configuration
-------------

The Eventyay configuration is based on TOML files, environment variables, dotenv files, and secret files. To see possible configuration keys and default values, check the ``BaseSettings`` class in ``app/eventyay/config/settings.py``.

The configuration is divided into three running environments:

- ``development``: Uses default values from ``eventyay.development.toml``.
- ``production``: Uses default values from ``eventyay.production.toml``.
- ``testing``: Uses default values from ``eventyay.testing.toml``.

The values in these files override values defined in ``BaseSettings``.

The running environment is selected via the ``EVY_RUNNING_ENVIRONMENT`` environment variable. It is pre-set in ``manage.py``, ``wsgi.py``, and ``asgi.py``.

For example, to run a command in the production environment:

.. code-block:: bash

   EVY_RUNNING_ENVIRONMENT=production ./manage.py command

Configuration sources are loaded with the following precedence:

1. Secret files in ``.secrets/``
2. Environment variables with the ``EVY_`` prefix
3. ``.env`` in the current working directory
4. ``eventyay.local.toml``
5. Environment specific TOML files such as ``eventyay.development.toml``, ``eventyay.production.toml``, or ``eventyay.testing.toml``

How to override configuration values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a file named ``eventyay.local.toml`` in the same folder as the ``manage.py`` file.

Add only the values you want to override. For example, to override the ``debug`` value, add:

.. code-block:: toml

   debug = true

For database connection values, a local override can look like this:

.. code-block:: toml

   postgres_user = "your_db_user"
   postgres_password = "your_db_password"
   postgres_host = "localhost"
   postgres_port = 5432

For complex values such as lists, prefer TOML files over environment variables.

You can also override values via environment variables. Environment variable names are the uppercase versions of the setting keys, prefixed by ``EVY_``.

For example, to override the ``debug`` value:

.. code-block:: bash

   export EVY_DEBUG=true

A dotenv file, ``.env``, is also supported. Values from ``.env`` are overridden by environment variables.

Sensitive data such as passwords and API keys should be provided via files in the ``.secrets`` directory, one file per key. The file name follows the same pattern as environment variable names with the ``EVY_`` prefix. The file content is the value.

For example, to provide a value for the ``secret_key`` setting, create this file:

.. code-block:: text

   .secrets/EVY_SECRET_KEY

If you deploy the app via Docker containers, you can provide secret data through `Docker secrets <https://docs.docker.com/engine/swarm/secrets/>`_.

Email configuration for testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


By default, emails are printed to the terminal logs through the console backend.

To test email related features with real delivery, configure a mail server such as SendGrid, Gmail SMTP, or another SMTP provider.

For Gmail SMTP, use:

.. code-block:: text

   Host: smtp.gmail.com
   Port: 587
   TLS: enabled

If 2FA is enabled on the Google account, you may need to use an App Password.

Plugins and extensions
----------------------

Eventyay comes with several plugins that are part of the standard setup. These built in plugins provide common functionality for authentication, reports, badges, check in workflows, scheduled tasks, statistics, and ticket outputs.

Built in and standard plugin areas include:

- Authentication and social auth
- Bank transfer
- Badges
- Sendmail
- Statistics
- Reports
- Check in lists
- Manual payment
- Return URLs
- Scheduled tasks
- PDF ticket output
- Web check in

Eventyay also supports external plugin extensions. These plugins can be installed to add integrations or event specific functionality.

Available plugin extensions include:

- `eventyay-exhibition <https://github.com/fossasia/eventyay-exhibition>`_: Exhibition component
- `eventyay-interpretation <https://github.com/fossasia/eventyay-interpretation>`_: Integration with interpretation services such as Voxbento
- `eventyay-hubspot <https://github.com/fossasia/eventyay-hubspot>`_: HubSpot integration
- `eventyay-loungemesh <https://github.com/fossasia/eventyay-loungemesh>`_: Loungemesh integration
- `eventyay-socialmedia <https://github.com/fossasia/eventyay-socialmedia>`_: Social media sharing and publishing integration
- `eventyay-teamshifts <https://github.com/fossasia/eventyay-teamshifts>`_: Team shifts and volunteer shift management plugin

Available payment plugins are:

- `eventyay-bitpay <https://github.com/fossasia/eventyay-bitpay>`_: BitPay crypto payment integration
- `eventyay-paypal <https://github.com/fossasia/eventyay-paypal>`_: PayPal payment integration
- `eventyay-stripe <https://github.com/fossasia/eventyay-stripe>`_: Stripe payment integration

To create a new Eventyay plugin, use the `eventyay plugin cookiecutter template <https://github.com/fossasia/eventyay-plugin-cookiecutter>`_.

Eventyay discovers compatible plugins through installed Django apps and Python entry points. The platform can register plugin URL patterns automatically when plugin metadata and URL modules are available.

Developing plugins locally
~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are developing plugins, create a directory named ``plugins`` in the root of this repository. This directory is gitignored and can contain local plugin checkouts.

Example:

.. code-block:: text

   .
   └── eventyay/
       └── plugins/
           ├── eventyay-exhibitor/
           └── eventyay-loungemesh/

When using the Docker development setup, the startup script scans ``./plugins/`` and installs detected plugins in editable mode. Installation status is cached in ``/tmp/eventyay-plugin-stamps/`` to speed up container boot times.

Separate Eventyay components
----------------------------

Eventyay also provides separate components that can be used together with the main platform.

Eventyay Checkin
~~~~~~~~~~~~~~~~

`Eventyay Checkin <https://github.com/fossasia/eventyay-checkin>`_ is a separate check in component for kiosk stations. It enables organisers to check in attendees at dedicated check in stations during an event.

Common development commands
---------------------------

Run from ``app/`` unless stated otherwise.

Install dependencies:

.. code-block:: bash

   uv sync --all-extras --all-groups

Activate virtual environment:

.. code-block:: bash

   . .venv/bin/activate

Apply database migrations:

.. code-block:: bash

   python manage.py migrate

Run development server:

.. code-block:: bash

   python manage.py runserver

Run Celery worker:

.. code-block:: bash

   celery -A eventyay worker -l info

Build development static files:

.. code-block:: bash

   make staticfiles

Build production assets:

.. code-block:: bash

   make production

Run tests:

.. code-block:: bash

   pytest tests/

Compile translations:

.. code-block:: bash

   make localecompile

Regenerate translation files:

.. code-block:: bash

   make localegen

Build JavaScript translation catalogues and static files:

.. code-block:: bash

   make staticfiles

API and service endpoints
-------------------------

Important local endpoints include:

.. code-block:: text

   /                         Public start page
   /orga/                    Organiser area for talks and speakers configuration and setup
   /control/                 Ticketing control and organiser management area
   /admin/                   Platform admin interface
   /api/v1/                  REST API
   /healthcheck/             Health check
   /metrics/                 Metrics endpoint
   /accounts/                Account and authentication routes
   /<organizer>/             Organizer public routes
   /<organizer>/<event>/     Event public routes
   /<organizer>/<event>/cfp/ Call for Participation routes
   /<organizer>/<event>/video/ Online event video frontend

Repository layout
-----------------

Important paths:

.. code-block:: text

   .
   ├── app/
   │   ├── eventyay/          Main Eventyay application code
   │   ├── tests/             Backend and integration tests
   │   ├── tools/             App related helper tools
   │   ├── manage.py          Django management entry point
   │   ├── pyproject.toml     Python project metadata and dependencies
   │   └── Makefile           Asset, translation, and test helper commands
   ├── deployment/            Docker, deployment, environment, and nginx related files
   ├── doc/                   Project documentation sources
   ├── tools/                 Repository level tools
   ├── docker-compose.yml     Local Docker development stack
   ├── CONTRIBUTING.md        Contribution workflow
   ├── DEPLOYMENT.md          Deployment notes
   ├── CLA.md                 Contributor License Agreement information
   ├── LICENSE                Apache License 2.0
   └── NOTICE                 Attribution and upstream notices

Main backend modules are under ``app/eventyay/``. Important areas include:

.. code-block:: text

   app/eventyay/
   ├── agenda/                Public schedule and agenda functionality
   ├── api/                   API endpoints and OAuth models
   ├── base/                  Core user, auth, middleware, and shared base code
   ├── cfp/                   Call for Participation functionality
   ├── common/                Shared platform utilities
   ├── config/                Django settings, ASGI, WSGI, and URL configuration
   ├── control/               Ticketing control and organiser management area
   ├── event/                 Event domain logic
   ├── features/              Feature modules such as analytics, live, importers, social, integrations
   ├── mail/                  Email handling
   ├── multidomain/           Multi domain routing and middleware
   ├── orga/                  Talks and speakers organiser area
   ├── person/                User and person related functionality
   ├── plugins/               Built in plugins
   ├── presale/               Ticketing and public event registration
   ├── schedule/              Schedule related functionality
   ├── storage/               File and media storage handling
   ├── submission/            Submission handling
   └── webapp/                Vue/Vite frontend applications

Architecture rules for contributors
-----------------------------------

Important rules for changes:

- Product code belongs under ``app/eventyay/``.
- Tests belong under ``app/tests/``.
- Documentation belongs under ``doc/``.
- Event owned ORM queries must be scoped correctly with ``django_scopes.scope(event=event)``.
- Keep imports at the top of files unless a local import is required to avoid a circular import.
- Preserve specific exception types instead of replacing them with generic ``Exception``.
- Do not introduce new jQuery usage or inline scripts.
- Prefer external ES modules for JavaScript.
- Use ``select_related`` and ``prefetch_related`` where appropriate to avoid N+1 queries.

Contributing
------------

We welcome contributions.

Basic workflow:

1. Fork the repository.
2. Create a feature branch.
3. Make focused changes.
4. Add or update tests when behaviour changes.
5. Run tests and relevant build commands locally.
6. Open a pull request against the ``dev`` branch.

Pull request expectations:

- Link the PR to a GitHub issue.
- Use closing keywords such as ``Fixes #123`` in the PR description.
- Keep PRs small enough to review in less than a day where possible.
- Add screenshots or short videos for UI changes.
- Open draft PRs early for large or long running work.
- Respond to review comments and keep the branch up to date.
- Do not repeatedly tag reviewers.

See `CONTRIBUTING.md <CONTRIBUTING.md>`_ for the full contribution guidelines.

AI assisted development
~~~~~~~~~~~~~~~~~~~~~~~

This repository includes structured guidance for AI assisted development.

AI tools should consult:

- ``agents.md``
- ``.github/instructions/``
- ``.agents/skills/``

These files define repository specific coding, architecture, documentation, and pull request expectations.

Troubleshooting
---------------

CSS not loading or MIME type errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In some environments, for example Docker with WSL, pages may load without CSS or only some pages may load correctly.

Browser console errors may look like:

.. code-block:: text

   Refused to apply style because its MIME type is 'text/html'

This usually means a static asset was requested but an HTML response, such as a 404 page, was returned instead.

Rebuild static assets:

.. code-block:: bash
   docker exec -ti eventyay-next-redis redis-cli FLUSHDB
   docker exec -ti eventyay-next-web rm -rf /usr/src/app/eventyay/static.dist/CACHE/css/*
   docker exec -ti eventyay-next-web make npminstall
   docker exec -ti eventyay-next-web python manage.py collectstatic --noinput
   docker exec -ti eventyay-next-web python manage.py compress --force
   docker restart eventyay-next-web

Then hard refresh the browser with ``Ctrl + Shift + R``.

Database issues in Docker
~~~~~~~~~~~~~~~~~~~~~~~~~


The database in the development Docker setup is stored in the ``eventyay-next_postgres_data_dev`` Docker volume. If you see errors concerning login or other database related behaviour, you can completely reset the database.

You will lose all local configuration, organisers, events, users, tickets, and related database content.

You must stop the stack first so no container is using the volume. Otherwise, ``docker volume rm`` will fail. ``docker compose down`` stops and removes the containers but keeps named volumes by default.

.. code-block:: bash

   docker compose down
   docker volume rm eventyay-next_postgres_data_dev

Redis issues in Docker
~~~~~~~~~~~~~~~~~~~~~~

Redis data in the development Docker setup is stored in the ``eventyay-next_rd`` volume. This corresponds to the ``rd`` volume in ``docker-compose.yml``.

If you see connection, cache, broker, or background task related errors, you can reset Redis the same way: stop the stack, then remove the volume.

You will lose data held in Redis, such as cache or broker state.

.. code-block:: bash

   docker compose down
   docker volume rm eventyay-next_rd

Reset PostgreSQL and Redis together
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To wipe both PostgreSQL and Redis data in one go, you can run ``docker compose down -v`` instead of removing volumes individually. This removes all named volumes declared for this Compose project, including ``eventyay-next_postgres_data_dev`` and ``eventyay-next_rd``.

.. code-block:: bash

   docker compose down -v

After resetting PostgreSQL and/or Redis
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Bring the development stack back up in detached mode with a rebuild:

.. code-block:: bash

   docker compose up -d --build

Deployment
----------

See `DEPLOYMENT.md <DEPLOYMENT.md>`_.

The documented deployment path assumes an Ubuntu based server, Docker, Docker Compose, nginx, certbot, PostgreSQL data storage, static file handling, and a deployment specific ``.env`` file.

The deployment documentation is a starting point and should be reviewed before production use. Operators should adapt the setup to their infrastructure, backup, monitoring, TLS, mail delivery, and security requirements.

Future improvements
-------------------

Backend
~~~~~~~

Potential backend improvements include:

- Apply more Python type annotations.
- Add MyPy, ty, or another type checker.
- Improve IDE autocomplete and early bug detection through typing.
- Continue moving selected templating workflows toward Jinja where useful.
- Use djlint or another formatter to clean up template code.

Frontend
~~~~~~~~

Potential frontend improvements include:

- Remove remaining jQuery code.
- Convert older frontend behaviour to Vue or AlpineJS.
- Continue evaluating Single Page Application architecture where it makes sense.
- Use TypeScript more consistently where it improves maintainability.
- Consider HTMX and AlpineJS where Django rendered HTML remains the preferred approach.

Support
-------

Eventyay is free and open source software.

Professional support is available to customers of the hosted Eventyay service or Eventyay enterprise offerings.

For commercial support, hosting services, custom development, deployment support, integrations, or financial support of the project, visit `eventyay.com <https://eventyay.com>`_.

Legal and licensing
-------------------

Eventyay is published under the Apache License 2.0. See `LICENSE <LICENSE>`_ for the complete license text.

See `NOTICE <NOTICE>`_ for attribution and upstream project notices.

Contributions are accepted under the Apache License 2.0. See `CONTRIBUTING.md <CONTRIBUTING.md>`_ and `CLA.md <CLA.md>`_ for details.

This project is maintained by `FOSSASIA <https://fossasia.org>`_.
