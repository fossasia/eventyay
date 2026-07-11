import os, django
from django.conf import settings
from django.template import Template, Context

settings.configure(
    INSTALLED_APPS=['compressor'],
    COMPRESS_ENABLED=True,
    COMPRESS_OFFLINE=False,
    COMPRESS_PRECOMPILERS=[],
    STATIC_URL='/static/',
    STATIC_ROOT='/tmp/static',
)
django.setup()

tmpl = Template("""
{% load compress %}
{% compress js %}
<script type="module" src="/static/test.js"></script>
{% endcompress %}
""")

try:
    print(tmpl.render(Context({})))
except Exception as e:
    print("ERROR:", str(e))
