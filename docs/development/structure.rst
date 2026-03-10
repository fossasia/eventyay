Directory structure
===================

All the source code lives in ``src/``, which has several subdirectories.

Eventyay/
    This directory contains nearly all source code that belongs to eventyay.

    base/
        This is the Django app containing all the models and methods which are
        essential to all of eventyay's features.

    control/
        This is the Django app containing the front end for organizers.

    presale/
        This is the Django app containing the front end for users buying tickets.

    api/
        This is the Django app containing all views and serializers for eventyay'
        :ref:`rest-api`.

    helpers/
        Helpers contain a very few modules providing workarounds for low-level flaws in
        Django or installed 3rd-party packages.

    locale/
        Contains translation file for eventyay

    multidomain/
        Additional code implementing our customized :ref:`URL handling <urlconf>`.

    static/
        Contains all static files (CSS/SASS, JavaScript, images) of eventyay' core
        We use libsass as a preprocessor for CSS. Our own sass code is built in the same
        step as Bootstrap and FontAwesome, so their mixins etc. are fully available.

    testutils/
        Contains helper methods that are useful to write the test suite for eventyay or test
        suites for eventyay plugins.

tests/
    This is the root directory for all test codes. It includes subdirectories ``api``, ``base``,
    ``control``, ``presale``, ``helpers`, ``multidomain`` and ``plugins`` to mirror the structure
    of the eventyay source code as well as ``testdummy``, which is a eventyay plugin used during
    testing.
