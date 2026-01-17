eventyay-tickets (ENext)
========================

Project status & release cycle
------------------------------

Welcome to the **Eventyay** project! The ticketing component of the system provides options for **ticket sales and event-related items** such as T-shirts. Eventyay has been in development since **2014**. Its ticketing component is based on a fork of **Pretix**.

ENext is the new and updated version of Eventyay with a unified codebase for the Tickets, Talk, and Videos components.

External Dependencies
----------------------

The *deb-packages.txt* file lists Debian packages we need to install.
If you are using Debian / Ubuntu, you can install them quickly with this command:

For traditional shell:

.. code-block:: bash

  $ xargs -a deb-packages.txt sudo apt install

For Nushell:

.. code-block:: nu

  > open deb-packages.txt | lines | sudo apt install ...$in


If you are using other Linux distros, please guess the corresponding package names for that list.

Other than that, please install `uv`_, the Python package manager.

Getting Started
---------------

1. **Clone the repository**:

.. code-block:: bash

  git clone https://github.com/fossasia/eventyay.git

2. **Enter the project directory and app directory**:

.. code-block:: bash

  cd eventyay/app

3. **Switch to the `dev` branch**:

.. code-block:: bash

  git switch dev


4. **Install Python packages**

Use ``uv`` to create virtual environment and install Python packages at the same time.
**Make sure you are in app directory**

.. code-block:: sh

  uv sync --all-extras --all-groups


5. **Create a PostgreSQL database**

The default database name that the project needs is ``eventyay-db``. If you are using Linux, the simplest way
to work with database is to use its "peer" mode (no need to remember password).

Create a Postgres user with the same name as your Linux user:

.. code-block:: sh

  sudo -u postgres createuser -s $USER

(``-s`` means *superuser*)

Then just create a database owned by your user:

.. code-block:: sh

  createdb eventyay-db

From now on, you can do everything with the database without specifying password, host and port.

.. code-block:: sh

  psql eventyay-db

In case you cannot take advantage of PostgreSQL *peer* mode, you need to create a *eventyay.local.toml* file with these values:

.. code-block:: toml

  postgres_user = 'your_db_user'
  postgres_password = 'your_db_password'
  postgres_host = 'localhost'
  postgres_port = 5432

6. **Install and run Redis**

7. **Activate virtual environment**

After running ``uv sync```, activate a virtual environment

.. code-block:: sh

  . .venv/bin/activate

8. **Initialize the database**:

.. code-block:: bash

  python manage.py migrate

9. **Create a admin user account** (for accessing the admin panel):

.. code-block:: bash

  python manage.py create_admin_user

10. **Run the development server**:

.. code-block:: bash

  python manage.py runserver


Notes: If you get permission errors for eventyay/static/CACHE, make sure that the directory and
all below it are own by you.

Docker based development
------------------------

We assume your current working directory is the checkout of this repo.

1. **Create .env.dev**

   .. code-block:: bash

      cp deployment/env.sample .env.dev

2. **Edit .env.dev**

   Change <SERVER_NAME> and the value of `EVY_RUNNING_ENVIRONMENT=production`
   to `EVY_RUNNING_ENVIRONMENT=development`

3. **Make sure you don't have some old volumes hanging around**

   This is only necessary the first time, or if you have strange behaviour.
   This removes the database volume and triggers a complete reinitialization.
   After that, you have to run migrate and createsuperuser again!

   .. code-block:: bash

  docker volume rm eventyay_postgres_data_dev eventyay_static_volume

4. **Build and run the images**

   .. code-block:: bash

      docker compose up -d --build

5. **Create a superuser account** (for accessing the admin panel):

   This should be necessary only once, since the database is persisted
   as docker volume. If you see strange behaviour, see the point 3.
   on how to reset.

  .. code-block:: bash

  docker exec -ti eventyay-next-web python manage.py createsuperuser

6. **Visit the site**

  Open `http://localhost:8000` in a browser.

7. **Checking the logs**

  .. code-block:: bash

  docker compose logs -f


8. **Shut down**

   To shut down the development docker deployment, run

  .. code-block:: bash

  docker compose down

The directory `app/eventyay` is mounted into the docker, thus live editing is supported.

Configuration
-------------

Our configuration are based on TOML files. First of all, check the ``BaseSettings`` class in *app/eventyay/config/next_settings.py* for possible keys and original values.
Other than that, the configuration is divided to three running environments:

* ``development``: With default values in *eventyay.development.toml*.
* ``production``: With default values in *eventyay.production.toml*.
* ``testing``: With default values in *eventyay.testing.toml*.

The values in these files will override ones in ``BaseSettings``.

Running environment is selected via the ``EVY_RUNNING_ENVIRONMENT`` environment variable. It is pre-set in *manage.py*, *wsgi.py* and *asgi.py*.
For example, if you want to run a command in production environment, you can do:

.. code-block:: bash

  EVY_RUNNING_ENVIRONMENT=production ./manage.py command

How to override the configuration values
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- Create a file named *eventyay.local.toml* in the same folder as *manage.py* file.
- Add only the values you want to override in this file. For example, to override the ``debug`` value in production environment, you only need to add one line:

  .. code-block:: toml

    debug = true

- You can also override values via environment variables. The environment variable names are the upper case versions of the setting keys, prefixed by ``EVY_``.
  For example, to override the ``debug`` value in production environment, you can set the environment variable ``EVY_DEBUG`` to ``true``.

  .. code-block:: bash

    export EVY_DEBUG=true

- Dotenv (*.env*) file is also supported, but please be aware that the values from *.env* file will be overriden by environment variables.

- Sensitive data like passwords, API keys should be provided via files in *.secrets* directory, each file for a key.
  The file name follows the pattern of environment variable names above (with prefix), the file content is the value.
  For example, to provide a value for the ``secret_key`` setting, you should create a file named ``EVY_SECRET_KEY`` and put the value inside.

- If you deployed the app via Docker containers, you can provide the secret data via `Docker secrets`_.

Why TOML?
~~~~~~~~~

TOML has rich data types. In comparison with *ini* format that this project used before, *ini* doesn't have "list" type, we had to define a convention to encode lists in strings.
This method is not portable, not understood by other tools and libraries, and error-prone.
TOML has dedicated syntax for lists, making it easier to read and write such configurations, and developers can use different tools and libraries without worrying about incompatibility.

Due to this reason, overriding configuration via environment variables are not encouraged. The environment variables only have one data type: string!


Deployment
----------

- copy all of the *deployment* directory onto the server into ``<TARGET_DIR>`` (e.g. as */home/fossasia/enext*)
- prepare the used volumes in docker-compose::

    <TARGET_DIR>/data/static
    <TARGET_DIR>/data/postgres
    <TARGET_DIR>/data/data

  and::

    chown 100:101 <TARGET_DIR>/data/data
    chmod a+x <TARGET_DIR>/data/static

- copy *env.sample* to *.env* in */home/fossasia/enext*, and edit it:

  + replace ``<SERVER_NAME>`` with your server, like *next.eventyay.com*
  + all the ``CHANGEME`` entries

- copy *nginx/enext-direct* to your system */etc/nginx/sites-available* and edit it:

  + replace ``<SERVER_NAME>`` with your server, like *next.eventyay.com*
  + replace ``<PATH_TO>`` with the ``<TARGET_DIR>`` you choose, like */home/fossasia/enext*
    The file needs to be adjusted if the *enext* dir is NOT in */home/fossasia*!

- Link the *enext-direct* file into */etc/nginx/sites-enabled*

- Restart nginx

- Run::

    docker compose up -d

Future improvement
------------------

Backend
~~~~~~~

- Apply type annotation for Python and MyPy (or ty) checking. Benefit: It improves IDE autocomplete and detect some bugs early.
- Use Jinja for templating (replacing Django template).
  Benefit: We can embed Python function to template and call. With Django template, we have to define filter, custom tags.
- Use djlint (or a better tool) to clean template code.

Frontend
~~~~~~~~

- Get rid of jQuery code, convert them to Vue or AlpineJS.
- Consider two options:
  +  Migrating to a Single Page Application, where we can use the full power of Vue and can apply TypeScript to improve IDE autocomplete and detect bugs early.
  +  HTMX + AlpineJS if we still want Django to produce HTML.


Support
-------

This project is **free and open-source software**. Professional support is available to customers of the **hosted Eventyay service** or **Eventyay enterprise offerings**. If you are interested in commercial support, hosting services, or supporting this project financially, please go to `eventyay.com`.

Legal & Licensing
-----------------

**License**: This project is published under the **Apache License 2.0**.
See the `LICENSE <LICENSE>`_ file for complete license text.

**Attribution**: See the `NOTICE <NOTICE>`_ file for information about upstream
projects and attribution.

**Contributing**: Contributions are accepted under the Apache License 2.0.
See `CONTRIBUTING.md <CONTRIBUTING.md>`_ and `CLA.md <CLA.md>`_ for details.

This project is maintained by **FOSSASIA**.

.. _uv: https://docs.astral.sh/uv/getting-started/installation/
.. _Docker secrets: https://docs.docker.com/engine/swarm/secrets/
.. _installation guide: https://docs.eventyay.com/en/latest/admin/installation/index.html
.. _eventyay.com: https://eventyay.com
.. _blog: https://blog.eventyay.com
