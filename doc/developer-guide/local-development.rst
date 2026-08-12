Local development setup
========================

Use one development environment for the unified Eventyay codebase. The
repository's Python baseline is 3.12 and application code lives under
``app/``.

Obtain the source and install all development dependencies::

   git clone https://github.com/fossasia/eventyay.git
   cd eventyay/app/
   uv sync --all-extras --all-groups

Prepare a local database and static assets::

   python manage.py migrate
   make staticfiles

Run the development server from ``app/``::

   python manage.py runserver

Run the test suite from ``app/``::

   pytest tests/

For backend structure, frontend details, testing conventions, translations,
and plugin development, continue with the pages in this Developer guide.
