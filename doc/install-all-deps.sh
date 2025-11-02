#!/bin/bash

set -e  # Exit on error

echo "Installing ALL dependencies from app/pyproject.toml for complete Django setup..."
echo "This will take several minutes..."
echo ""

# Install Sphinx and documentation tools first
echo "=== Installing Sphinx and documentation tools ==="
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    sphinx sphinx-rtd-theme sphinxcontrib-httpdomain sphinxcontrib-images sphinxemoji rich

# Install ALL standard PyPI dependencies from pyproject.toml
# Excluding git-based dependencies which need special handling
echo ""
echo "=== Installing ALL Python dependencies ==="
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    aiohappyeyeballs aiohttp aiosignal amqp annotated-types \
    arabic-reshaper argon2-cffi argon2-cffi-bindings asgiref asn1crypto attrs \
    autobahn automat babel beautifulsoup4 billiard bleach \
    cbor2 celery certifi cffi channels channels-redis chardet charset-normalizer \
    click click-didyoumean click-plugins click-repl constantly contourpy \
    coverage coveralls cron-descriptor cryptography css-inline csscompressor cssutils cycler \
    daphne defusedcsv defusedxml dj-static \
    "Django>=5.2.5" django-allauth django-appconf django-bootstrap3 \
    django-celery-beat django-compressor django-context-decorator django-cors-headers \
    django-countries django-csp django-filter django-formset-js-improved django-formtools \
    django-hierarkey django-hijack django-i18nfield django-jquery-js django-libsass \
    django-localflavor django-markup django-multifactor django-oauth-toolkit django-otp \
    django-pdb django-phonenumber-field django-redis django-scopes django-sso \
    django-statici18n django-timezone-field djangorestframework \
    docopt docutils elementpath emoji et-xmlfile \
    execnet faker fakeredis fido2 flake8 fonttools freezegun frozenlist \
    geoip2 gunicorn hyperlink \
    icalendar idna importlib-metadata incremental iniconfig isort isoweek \
    jinja2 jsonschema jsonschema-specifications jwcrypto \
    kiwisolver kombu libsass lxml \
    markdown markdownify matplotlib maxminddb mccabe more-itertools msgpack mt-940 multidict \
    nh3 numpy oauthlib openpyxl orjson packaging pandas \
    pdf2image pdfrw pep8-naming phonenumberslite pillow pluggy polib potypo \
    prompt-toolkit propcache protobuf "psycopg[binary,pool]" publicsuffixlist \
    pyasn1 pyasn1-modules pycodestyle pycountry pycparser pycryptodome \
    pydantic pydantic-core pyenchant pyflakes pygments pyjwt \
    pyopenssl pyotp pyparsing pypdf pypng \
    python-bidi python-creole python-crontab python-dateutil python-http-client \
    python-stdnum python-u2flib-server pytz pyuca pyvat pyyaml \
    qrcode rcssmin redis referencing reportlab requests \
    rjsmin rpds-py rules \
    sepaxml sendgrid sentry-sdk service-identity setuptools six slimit sortedcontainers sqlparse \
    static3 stripe text-unidecode tlds tqdm txaio twisted typing-extensions tzdata \
    u-msgpack-python ua-parser urlman vat-moss-forked vobject wcwidth webauthn webencodings \
    websockets werkzeug xmlschema yarl zipp zope-interface zxcvbn

echo ""
echo "=== Installing doc requirements ==="
if [ -f requirements.txt ]; then 
    pip install -r requirements.txt 2>/dev/null || echo "Some doc requirements skipped"
fi

echo ""
echo "✅ All dependencies installed successfully!"
echo ""
echo "You can now build documentation with:"
echo "  make clean && make html"

